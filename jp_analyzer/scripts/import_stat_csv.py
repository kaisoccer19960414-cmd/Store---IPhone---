import argparse
import os
import re
from pathlib import Path
import pandas as pd
import requests
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / '.env')

SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_KEY')

SUPABASE_HEADERS = {
    'apikey': SUPABASE_SERVICE_KEY,
    'Authorization': f'Bearer {SUPABASE_SERVICE_KEY}',
    'Content-Type': 'application/json',
}

YEAR_PATTERN = re.compile(r'^(\d{4})年$')
# 「1995年10月〜1996年9月」のような期間形式の列。波ダッシュの表記ゆれ(〜/～/~)に対応
YEAR_RANGE_PATTERN = re.compile(r'^(\d{4})年\d{1,2}月[〜～~](\d{4})年\d{1,2}月$')


def extract_year_columns(df):
    """年度を表す列を検出し、(列の位置インデックス, 年) のリストを返す。
    「YYYY年」の単純な形式と、「YYYY年M月〜YYYY年M月」のような期間形式の両方に対応する。
    期間形式は終了年を代表年として扱う(例: 1995年10月〜1996年9月 → 1996年としてDBに保存)。
    列名ではなく位置で返すのは、e-StatのCSVでは同じ期間の列名が複数回出てくることがあり、
    列名だけで参照すると意図しない列と混同する恐れがあるため。"""
    year_columns = []
    for idx, col in enumerate(df.columns):
        col_str = str(col).strip()
        m = YEAR_PATTERN.match(col_str)
        if m:
            year_columns.append((idx, int(m.group(1))))
            continue
        m = YEAR_RANGE_PATTERN.match(col_str)
        if m:
            year_columns.append((idx, int(m.group(2))))
    return year_columns


def load_csv(csv_path, skiprows):
    df = pd.read_csv(csv_path, encoding='cp932', skiprows=skiprows)

    # Excel経由の破損などで「�」(置き換え文字)が混ざっていないかチェックする
    sample_parts = [str(c) for c in df.columns]
    for row in df.head(20).itertuples(index=False):
        sample_parts.extend(str(v) for v in row)
    sample = ''.join(sample_parts)
    if '\ufffd' in sample:
        raise SystemExit(
            '警告: ファイルの中に文字化け(�)が含まれています。\n'
            'CSVがExcel等で一度開かれて壊れた可能性が高いです。e-Statから再ダウンロードしてください。'
        )
    return df


def inspect(df):
    """絞り込みに使えそうな列(「〇〇 コード」列)と、対応するラベルを自動で洗い出して表示する"""
    year_columns = extract_year_columns(df)
    print('=== 検出した年度列 ===')
    for idx, year in year_columns:
        print(f'  {df.columns[idx]!r} (列位置 {idx}) -> {year}年として扱います')
    print()

    print('=== 絞り込みに使えそうな列(--filter の候補) ===')
    for col in df.columns:
        if not col.endswith(' コード'):
            continue
        label_col = col.replace(' コード', '')
        if label_col not in df.columns:
            continue
        pairs = df[[col, label_col]].drop_duplicates().values.tolist()
        print(f'\n{col}:')
        for code, label in pairs[:15]:
            print(f'  {code} -> {label}')
        if len(pairs) > 15:
            print(f'  ...ほか{len(pairs) - 15}件')


def parse_filters(filter_args):
    filters = {}
    for f in filter_args or []:
        col, _, value = f.partition('=')
        col, value = col.strip(), value.strip()
        if value.lstrip('-').isdigit():
            value = int(value)
        filters[col] = value
    return filters


def fetch_prefecture_ids():
    res = requests.get(
        f'{SUPABASE_URL}/rest/v1/prefectures',
        headers=SUPABASE_HEADERS,
        params={'select': 'id,name'}
    )
    res.raise_for_status()
    return {row['name']: row['id'] for row in res.json()}


def main():
    parser = argparse.ArgumentParser(description='e-StatのCSVをprefecture_statsテーブルに取り込む汎用スクリプト')
    parser.add_argument('--csv', required=True)
    parser.add_argument('--skiprows', type=int, default=11)
    parser.add_argument('--indicator')
    parser.add_argument('--unit', default=None)
    parser.add_argument('--source')
    parser.add_argument('--pref-column', default='全国・都道府県')
    parser.add_argument('--filter', action='append')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--inspect', action='store_true', help='絞り込み条件を考える前に、列の中身を確認するモード')
    parser.add_argument('--allow-duplicate-years', action='store_true',
                         help='同じ年に対応する列が複数あっても止めずに投入する(後勝ちで上書きされる)')
    args = parser.parse_args()

    csv_path = ROOT_DIR / 'jp_analyzer' / 'data' / args.csv
    df = load_csv(csv_path, args.skiprows)

    if args.inspect:
        inspect(df)
        return

    if not args.indicator or not args.source:
        raise SystemExit('--indicator と --source は必須です(先に --inspect で中身を確認してください)')

    for col, value in parse_filters(args.filter).items():
        df = df[df[col] == value]
    df = df[df[args.pref_column] != '全国']

    year_columns = extract_year_columns(df)
    if not year_columns:
        raise SystemExit('年度の列が見つかりません。--filterや列名を確認してください。')
    print(f'検出した年度列: {[(df.columns[idx], year) for idx, year in year_columns]}')

    # 同じ年が複数回検出された場合、列名が同じでも実際は違う意味のデータ
    # (男女別・自然増減/社会増減など)が混ざっている可能性が高い。
    # (prefecture_id, indicator, year)でUPSERTする都合上、片方が
    # サイレントに上書きされてしまうため、ここで止めて確認を促す。
    seen_years = {}
    for idx, year in year_columns:
        seen_years.setdefault(year, []).append(idx)
    duplicated = {y: idxs for y, idxs in seen_years.items() if len(idxs) > 1}
    if duplicated and not args.allow_duplicate_years:
        print('\n警告: 同じ年に対応する列が複数見つかりました。')
        for year, idxs in duplicated.items():
            cols = [df.columns[i] for i in idxs]
            print(f'  {year}年: {cols} (列位置 {idxs})')
        raise SystemExit(
            '列名が同じでも、実際は違う意味のデータ(男女別・自然増減/社会増減など)が\n'
            '混ざっている可能性があります。--filter で対象を1つに絞り込んでください\n'
            '(--inspect で「--filter の候補」を確認できます)。\n'
            '意図的に両方まとめて投入したい場合は --allow-duplicate-years を付けてください\n'
            '(この場合、後勝ちで上書きされる点に注意)。'
        )

    prefecture_ids = fetch_prefecture_ids()
    rows = []
    for _, row in df.iterrows():
        name = row[args.pref_column]
        pref_id = prefecture_ids.get(name)
        if pref_id is None:
            print(f'警告: {name} が見つかりません。スキップします。')
            continue
        for idx, year in year_columns:
            value_str = str(row.iloc[idx]).replace(',', '').strip()
            if value_str in ('', 'nan', '-', '***'):
                continue
            rows.append({
                'prefecture_id': pref_id,
                'indicator': args.indicator,
                'year': year,
                'value': float(value_str),
                'unit': args.unit,
                'source': args.source,
            })

    print(f'{len(rows)} 件を投入します')
    if args.dry_run:
        for r in rows[:10]:
            print(r)
        print('(--dry-run のため実際には投入していません)')
        return

    res = requests.post(
        f'{SUPABASE_URL}/rest/v1/prefecture_stats?on_conflict=prefecture_id,indicator,year',
        headers={**SUPABASE_HEADERS, 'Prefer': 'return=representation,resolution=merge-duplicates'},
        json=rows
    )
    print(res.status_code, res.text[:500])


if __name__ == '__main__':
    main()