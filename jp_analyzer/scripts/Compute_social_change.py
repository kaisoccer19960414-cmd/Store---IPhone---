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
        description='社会増減数 = (人口の前年比増減) - 自然増減数 を計算し、prefecture_statsに投入する'
        '(populationとnatural_changeの集計基準が異なるため、あくまで近似値)'
    )
    parser.add_argument('--population-indicator', default='population')
    parser.add_argument('--natural-change-indicator', default='natural_change')
    parser.add_argument('--indicator', default='social_change')
    parser.add_argument('--unit', default='人')
    parser.add_argument(
        '--source',
        default='calculated: (population year-over-year change) - natural_change (近似値)'
    )
    parser.add_argument(
        '--skip-census-years', action='store_true', default=True,
        help='国勢調査の年(西暦が5で割り切れる年)は、populationが実地調査に切り替わりnatural_changeとの'
             '差分計算が大きく歪むため、デフォルトでスキップする'
    )
    parser.add_argument(
        '--include-census-years', action='store_false', dest='skip_census_years',
        help='--skip-census-yearsを無効化し、国勢調査の年も計算対象に含める'
    )
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    population_rows = fetch_all(args.population_indicator)
    natural_change_rows = fetch_all(args.natural_change_indicator)
    print(f'{args.population_indicator}: {len(population_rows)} 件、'
          f'{args.natural_change_indicator}: {len(natural_change_rows)} 件 取得しました')

    population = {}
    for r in population_rows:
        population.setdefault(r['prefecture_id'], {})[r['year']] = r['value']
    natural_change = {(r['prefecture_id'], r['year']): r['value'] for r in natural_change_rows}

    rows = []
    skipped_no_prev_population = 0
    skipped_census_year = 0
    for (pref_id, year), nc_value in natural_change.items():
        if args.skip_census_years and year % 5 == 0:
            skipped_census_year += 1
            continue
        prev_year = year - 1
        pref_population = population.get(pref_id, {})
        if year not in pref_population or prev_year not in pref_population:
            skipped_no_prev_population += 1
            continue

        population_change = pref_population[year] - pref_population[prev_year]
        social_change = population_change - nc_value

        rows.append({
            'prefecture_id': pref_id,
            'indicator': args.indicator,
            'year': year,
            'value': social_change,
            'unit': args.unit,
            'source': args.source,
        })

    print(f'{len(rows)} 件を計算しました'
          f'(前年/当年のpopulationが無く計算できなかった件数: {skipped_no_prev_population}、'
          f'国勢調査の年としてスキップした件数: {skipped_census_year})')

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