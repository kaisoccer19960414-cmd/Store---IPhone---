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

YEAR_PATTERN = re.compile(r'^\d{4}年$')


def load_csv(csv_path, skiprows):
    df = pd.read_csv(csv_path, encoding='cp932', skiprows=skiprows)

    # Excel経由の破損などで「�」(置き換え文字)が混ざっていないかチェックする
    sample = ''.join(str(c) for c in df.columns) + ''.join(df.head(20).astype(str).values.flatten())
    if '\ufffd' in sample:
        raise SystemExit(
            '警告: ファイルの中に文字化け(�)が含まれています。\n'
            'CSVがExcel等で一度開かれて壊れた可能性が高いです。e-Statから再ダウンロードしてください。'
        )
    return df


def inspect(df):
    """絞り込みに使えそうな列(「〇〇 コード」列)と、対応するラベルを自動で洗い出して表示する"""
    year_columns = [c for c in df.columns if YEAR_PATTERN.match(str(c).strip())]
    print(f'=== 検出した年度列 ===\n{year_columns}\n')

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

    year_columns = [c for c in df.columns if YEAR_PATTERN.match(str(c).strip())]
    if not year_columns:
        raise SystemExit('年度の列が見つかりません。--filterや列名を確認してください。')
    print(f'検出した年度列: {year_columns}')

    prefecture_ids = fetch_prefecture_ids()
    rows = []
    for _, row in df.iterrows():
        name = row[args.pref_column]
        pref_id = prefecture_ids.get(name)
        if pref_id is None:
            print(f'警告: {name} が見つかりません。スキップします。')
            continue
        for year_col in year_columns:
            value_str = str(row[year_col]).replace(',', '').strip()
            if value_str in ('', 'nan', '-', '***'):
                continue
            rows.append({
                'prefecture_id': pref_id,
                'indicator': args.indicator,
                'year': int(year_col.replace('年', '')),
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