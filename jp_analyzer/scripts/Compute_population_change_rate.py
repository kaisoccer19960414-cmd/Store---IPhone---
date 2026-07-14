import argparse
import os
from pathlib import Path
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


def fetch_all_population():
    """population指標の全レコードを、1000件の上限に引っかからないようページングしながら取得する"""
    all_rows = []
    page_size = 1000
    offset = 0
    while True:
        res = requests.get(
            f'{SUPABASE_URL}/rest/v1/prefecture_stats',
            headers=SUPABASE_HEADERS,
            params={
                'select': 'prefecture_id,year,value',
                'indicator': 'eq.population',
                'order': 'prefecture_id.asc,year.asc',
                'limit': page_size,
                'offset': offset,
            }
        )
        res.raise_for_status()
        batch = res.json()
        all_rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return all_rows


def main():
    parser = argparse.ArgumentParser(
        description='populationの連続データ(前年比)から人口増減率(千人比、‰)を計算し、prefecture_statsに投入する'
    )
    parser.add_argument('--indicator', default='population_change_rate')
    parser.add_argument('--unit', default='‰')
    parser.add_argument('--source', default='calculated from population (A1101)')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    pop_rows = fetch_all_population()
    print(f'population指標を {len(pop_rows)} 件取得しました')

    # 都道府県ごとに { year: value } の対応表を作る
    by_pref = {}
    for row in pop_rows:
        by_pref.setdefault(row['prefecture_id'], {})[row['year']] = row['value']

    rows = []
    skipped_no_prev_year = 0
    for pref_id, year_values in by_pref.items():
        for y in sorted(year_values.keys()):
            prev_y = y - 1
            if prev_y not in year_values:
                skipped_no_prev_year += 1
                continue  # 前年のデータが無いと増減率は計算できない
            prev_value = year_values[prev_y]
            this_value = year_values[y]
            if not prev_value:
                continue
            rate = (this_value - prev_value) / prev_value * 1000
            rows.append({
                'prefecture_id': pref_id,
                'indicator': args.indicator,
                'year': y,
                'value': round(rate, 1),
                'unit': args.unit,
                'source': args.source,
            })

    print(f'{len(rows)} 件の増減率を計算しました(前年データが無く計算できなかった件数: {skipped_no_prev_year})')

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