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

YEAR_PATTERN = re.compile(r'^\d{4}年$')  # "2024年"のような列名を自動検出する


def parse_filters(filter_args):
    """--filter '男女別 コード=0' のような文字列を {列名: 値} の辞書に変換する"""
    filters = {}
    for f in filter_args or []:
        col, _, value = f.partition('=')
        col, value = col.strip(), value.strip()
        if value.lstrip('-').isdigit():
            value = int(value)  # CSVのコード列は大体int64で読まれるので合わせる
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
    parser.add_argument('--csv', required=True, help='jp_analyzer/data/ からの相対ファイル名')
    parser.add_argument('--skiprows', type=int, default=11)
    parser.add_argument('--indicator', required=True, help='指標名(例: population, area)')
    parser.add_argument('--unit', default=None, help='単位(例: 千人, km2)')
    parser.add_argument('--source', required=True, help='出典メモ(例: "e-Stat 0004021102")')
    parser.add_argument('--pref-column', default='全国・都道府県')
    parser.add_argument('--filter', action='append', help='"列名=値" の形で絞り込み条件を複数指定可能')
    parser.add_argument('--dry-run', action='store_true', help='投入せず変換結果の確認だけ行う')
    args = parser.parse_args()

    csv_path = ROOT_DIR / 'jp_analyzer' / 'data' / args.csv
    df = pd.read_csv(csv_path, encoding='cp932', skiprows=args.skiprows)

    for col, value in parse_filters(args.filter).items():
        df = df[df[col] == value]
    df = df[df[args.pref_column] != '全国']

    year_columns = [c for c in df.columns if YEAR_PATTERN.match(str(c).strip())]
    if not year_columns:
        raise SystemExit('年度の列(例:"2024年")が見つかりません。--filterや列名を確認してください。')
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