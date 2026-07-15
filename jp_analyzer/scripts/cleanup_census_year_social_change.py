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

CENSUS_YEARS = [1995, 2000, 2005, 2010, 2015, 2020, 2025]


def main():
    parser = argparse.ArgumentParser(
        description='social_change(または指定したindicator)のうち、国勢調査の年(1995,2000,...,2025)の'
                    'データを削除する(populationが実地調査に切り替わる年で、近似計算が歪むため)'
    )
    parser.add_argument('--indicator', default='social_change')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    years_param = ','.join(str(y) for y in CENSUS_YEARS)

    # まず対象件数を確認する
    res = requests.get(
        f'{SUPABASE_URL}/rest/v1/prefecture_stats',
        headers=SUPABASE_HEADERS,
        params={
            'select': 'id,prefecture_id,year',
            'indicator': f'eq.{args.indicator}',
            'year': f'in.({years_param})',
        }
    )
    res.raise_for_status()
    target_rows = res.json()
    print(f'削除対象: indicator={args.indicator!r}, year in {CENSUS_YEARS} の {len(target_rows)} 件')

    if args.dry_run:
        for r in target_rows[:10]:
            print(r)
        print('(--dry-run のため実際には削除していません)')
        return

    if not target_rows:
        print('削除対象がありません。')
        return

    del_res = requests.delete(
        f'{SUPABASE_URL}/rest/v1/prefecture_stats',
        headers=SUPABASE_HEADERS,
        params={
            'indicator': f'eq.{args.indicator}',
            'year': f'in.({years_param})',
        }
    )
    print(del_res.status_code, del_res.text[:500])


if __name__ == '__main__':
    main()