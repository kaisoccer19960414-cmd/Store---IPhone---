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

# 「1975年度」のような表記から西暦だけ取り出す
YEAR_PATTERN = re.compile(r'^(\d{4})年度?$')

# 「全国」の地域コード。CSV上は "0" として入っている(ゼロ埋めされていない)ため、
# 数値として比較する。prefecturesテーブルには存在しないので明示的に除外する
NATIONAL_CODE = 0


def fetch_prefecture_ids():
    """既存のprefecturesテーブルから 名前→id の対応表を取得する"""
    res = requests.get(
        f'{SUPABASE_URL}/rest/v1/prefectures',
        headers=SUPABASE_HEADERS,
        params={'select': 'id,name'}
    )
    res.raise_for_status()
    return {row['name']: row['id'] for row in res.json()}


def load_one_csv(csv_path, skiprows, column):
    df = pd.read_csv(csv_path, encoding='cp932', skiprows=skiprows)
    if column not in df.columns:
        raise SystemExit(
            f'{csv_path.name}: 列 {column!r} が見つかりません。\n'
            f'実際の列名の一部: {list(df.columns[:10])} ...'
        )
    if '地域 コード' not in df.columns or '調査年' not in df.columns:
        raise SystemExit(f'{csv_path.name}: 想定している「地域 コード」「調査年」列が見つかりません。')
    return df


def main():
    parser = argparse.ArgumentParser(
        description='社会・人口統計体系形式(1行=1年度×1都道府県)のCSVをprefecture_statsに取り込む'
    )
    parser.add_argument('--csv', required=True, action='append',
                         help='取り込むCSVファイル名(jp_analyzer/data/配下)。複数指定可: --csv a.csv --csv b.csv --csv c.csv')
    parser.add_argument('--skiprows', type=int, default=12)
    parser.add_argument('--column', default='A1101_総人口【人】', help='取り込む対象の列名')
    parser.add_argument('--indicator', required=True)
    parser.add_argument('--unit', default='人')
    parser.add_argument('--source', required=True)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    prefecture_ids = fetch_prefecture_ids()

    rows = []
    skipped_unmatched = []

    for csv_name in args.csv:
        csv_path = ROOT_DIR / 'jp_analyzer' / 'data' / csv_name
        df = load_one_csv(csv_path, args.skiprows, args.column)
        print(f'{csv_name}: {len(df)} 行を読み込みました')

        for _, row in df.iterrows():
            try:
                region_code = int(str(row['地域 コード']).strip())
            except ValueError:
                region_code = None
            if region_code == NATIONAL_CODE:
                continue  # 「全国」の集計行はスキップ

            name = row['地域']
            pref_id = prefecture_ids.get(name)
            if pref_id is None:
                skipped_unmatched.append((csv_name, region_code, name))
                continue

            year_str = str(row['調査年']).strip()
            m = YEAR_PATTERN.match(year_str)
            if not m:
                print(f'警告: {csv_name} - 年度の形式が不明: {year_str!r}。この行はスキップします。')
                continue
            year = int(m.group(1))

            value_str = str(row[args.column]).replace(',', '').strip()
            if value_str in ('', 'nan', '-', '***', 'X'):
                continue

            rows.append({
                'prefecture_id': pref_id,
                'indicator': args.indicator,
                'year': year,
                'value': float(value_str),
                'unit': args.unit,
                'source': args.source,
            })

    if skipped_unmatched:
        print(f'\n警告: prefecturesテーブルに見つからず、スキップした行が {len(skipped_unmatched)} 件あります。')
        print('地域コードが「00000」(全国)以外でここに出ている場合は、都道府県名の表記ゆれの可能性があるので確認してください。')
        for csv_name, code, name in skipped_unmatched[:10]:
            print(f'  {csv_name}: コード={code} 地域={name!r}')

    # 同じ(都道府県, 年度)が複数ファイルにまたがって重複していないか確認
    # (CSVの年度範囲が重なっていると、後勝ちで上書きされてしまうため)
    seen = {}
    for r in rows:
        key = (r['prefecture_id'], r['year'])
        seen.setdefault(key, []).append(r['value'])
    duplicated = {k: v for k, v in seen.items() if len(v) > 1}
    if duplicated:
        print(f'\n警告: 都道府県×年度の組み合わせが複数ファイルにまたがって重複しています({len(duplicated)}件)。')
        print('値が食い違っている場合、後から処理したファイルの値で上書きされます。')
        for k, v in list(duplicated.items())[:10]:
            print(f'  prefecture_id={k[0]}, year={k[1]}: {v}')

    print(f'\n{len(rows)} 件を投入します(重複分含む延べ件数)')

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