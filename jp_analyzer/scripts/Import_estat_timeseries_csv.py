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

# 「1978年」のような、月が付いてない年計行だけを拾う
ANNUAL_PATTERN = re.compile(r'^(\d{4})年$')


def fetch_prefecture_ids():
    res = requests.get(
        f'{SUPABASE_URL}/rest/v1/prefectures',
        headers=SUPABASE_HEADERS,
        params={'select': 'id,name'}
    )
    res.raise_for_status()
    return {row['name']: row['id'] for row in res.json()}


def main():
    parser = argparse.ArgumentParser(
        description='e-Statの「時系列表示(TimeSeriesResult)」形式(月次+年計行が混在)のCSVから、'
                    '年計行だけを取り出してprefecture_statsに投入する'
    )
    parser.add_argument('--csv', required=True, help='jp_analyzer/data/配下のファイル名')
    parser.add_argument('--value-column', help='値の列名(例: "出生数【人】")。--inspect以外では必須')
    parser.add_argument('--indicator', help='--inspect以外では必須')
    parser.add_argument('--unit', default='人')
    parser.add_argument('--source', help='--inspect以外では必須')
    parser.add_argument('--pref-column', default='地域')
    parser.add_argument('--time-column', default='時点')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--inspect', action='store_true', help='列名・年計行の検出状況だけ確認するモード')
    args = parser.parse_args()

    csv_path = ROOT_DIR / 'jp_analyzer' / 'data' / args.csv
    df = pd.read_csv(csv_path, encoding='utf-8-sig')

    if args.inspect:
        print('=== 列一覧 ===')
        print(list(df.columns))
        print(f'\n=== {args.pref_column!r} のユニーク値 ===')
        print(sorted(df[args.pref_column].astype(str).unique()))
        annual_mask = df[args.time_column].astype(str).str.match(r'^\d{4}年$')
        print(f'\n=== 年計行(「YYYY年」形式、月無し)の検出数: {annual_mask.sum()}件 ===')
        print(sorted(df.loc[annual_mask, args.time_column].astype(str).unique()))
        return

    if not args.value_column or not args.indicator or not args.source:
        raise SystemExit('--value-column、--indicator、--source は必須です(先に --inspect で中身を確認してください)')

    if args.value_column not in df.columns:
        raise SystemExit(f'列 {args.value_column!r} が見つかりません。--inspect で列名を確認してください。')

    prefecture_ids = fetch_prefecture_ids()

    rows = []
    skipped_unmatched = set()
    for _, row in df.iterrows():
        time_str = str(row[args.time_column]).strip()
        m = ANNUAL_PATTERN.match(time_str)
        if not m:
            continue  # 月次の行はスキップし、年計行だけを使う
        year = int(m.group(1))

        name = row[args.pref_column]
        if name == '全国':
            continue
        pref_id = prefecture_ids.get(name)
        if pref_id is None:
            skipped_unmatched.add(name)
            continue

        value_str = str(row[args.value_column]).replace(',', '').strip()
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
        print(f'警告: prefecturesテーブルに見つからず、スキップした地域名: {sorted(skipped_unmatched)}')

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