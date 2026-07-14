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


def fetch_all(indicator):
    """指定indicatorの全レコードを、1000件の上限に引っかからないようページングしながら取得する"""
    all_rows = []
    page_size = 1000
    offset = 0
    while True:
        res = requests.get(
            f'{SUPABASE_URL}/rest/v1/prefecture_stats',
            headers=SUPABASE_HEADERS,
            params={
                'select': 'prefecture_id,year,value',
                'indicator': f'eq.{indicator}',
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
        description='births(出生数) - deaths(死亡数) を都道府県×年ごとに計算し、prefecture_statsに投入する'
    )
    parser.add_argument('--births-indicator', default='births')
    parser.add_argument('--deaths-indicator', default='deaths')
    parser.add_argument('--indicator', default='natural_change')
    parser.add_argument('--unit', default='人')
    parser.add_argument('--source', default='calculated from births - deaths')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    births_rows = fetch_all(args.births_indicator)
    deaths_rows = fetch_all(args.deaths_indicator)
    print(f'{args.births_indicator}: {len(births_rows)} 件、{args.deaths_indicator}: {len(deaths_rows)} 件 取得しました')

    births = {(r['prefecture_id'], r['year']): r['value'] for r in births_rows}
    deaths = {(r['prefecture_id'], r['year']): r['value'] for r in deaths_rows}

    common_keys = sorted(set(births.keys()) & set(deaths.keys()))
    only_births = set(births.keys()) - set(deaths.keys())
    only_deaths = set(deaths.keys()) - set(births.keys())

    if only_births:
        years = sorted({y for _, y in only_births})
        print(f'警告: birthsにしか無い(deathsが欠けてる)都道府県×年: {len(only_births)}件。年の範囲: {years}')
    if only_deaths:
        years = sorted({y for _, y in only_deaths})
        print(f'警告: deathsにしか無い(birthsが欠けてる)都道府県×年: {len(only_deaths)}件。年の範囲: {years}')

    rows = []
    for pref_id, year in common_keys:
        rate = births[(pref_id, year)] - deaths[(pref_id, year)]
        rows.append({
            'prefecture_id': pref_id,
            'indicator': args.indicator,
            'year': year,
            'value': rate,
            'unit': args.unit,
            'source': args.source,
        })

    print(f'\n{len(rows)} 件を計算しました')

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