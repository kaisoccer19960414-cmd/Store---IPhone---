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
        description='統計ダッシュボードの「地域別」表示形式(1行目=タイトル、2行目=見出し、'
                    '行=年度・列=都道府県)のCSVをprefecture_statsに取り込む'
    )
    parser.add_argument('--csv', required=True, help='jp_analyzer/data/配下のファイル名')
    parser.add_argument('--skiprows', type=int, default=1, help='先頭の捨て行(タイトル行)の数')
    parser.add_argument('--time-column', default='時点')
    parser.add_argument('--indicator', help='--inspect以外では必須')
    parser.add_argument('--unit', default='人')
    parser.add_argument('--source', help='--inspect以外では必須')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--inspect', action='store_true', help='列名と年度の検出状況だけ確認するモード')
    args = parser.parse_args()

    csv_path = ROOT_DIR / 'jp_analyzer' / 'data' / args.csv
    df = pd.read_csv(csv_path, encoding='utf-8-sig', skiprows=args.skiprows)

    if args.time_column not in df.columns:
        raise SystemExit(f'時点列 {args.time_column!r} が見つかりません。実際の列: {list(df.columns)}')

    pref_columns = [c for c in df.columns if c != args.time_column]

    if args.inspect:
        print('=== 列一覧(都道府県とみなす列) ===')
        print(pref_columns)
        mask = df[args.time_column].astype(str).str.match(r'^\d{4}年$')
        print(f'\n=== 年度の行として検出した件数: {mask.sum()} / {len(df)} ===')
        print(sorted(df.loc[mask, args.time_column].astype(str).unique()))
        return

    if not args.indicator or not args.source:
        raise SystemExit('--indicator と --source は必須です(先に --inspect で中身を確認してください)')

    prefecture_ids = fetch_prefecture_ids()

    rows = []
    skipped_unmatched = set()
    for _, row in df.iterrows():
        time_str = str(row[args.time_column]).strip()
        m = YEAR_PATTERN.match(time_str)
        if not m:
            continue
        year = int(m.group(1))

        for pref_name in pref_columns:
            pref_id = prefecture_ids.get(pref_name)
            if pref_id is None:
                skipped_unmatched.add(pref_name)
                continue

            value_str = str(row[pref_name]).replace(',', '').strip()
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
        print(f'警告: prefecturesテーブルに見つからず、スキップした列名: {sorted(skipped_unmatched)}')

    print(f'{len(rows)} 件を投入します')

    if args.dry_run:
        rows.sort(key=lambda r: (r['prefecture_id'], r['year']))
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