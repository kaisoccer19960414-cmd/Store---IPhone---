import os
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

YEAR_COLUMNS = ['2005年', '2010年', '2015年', '2020年', '2021年', '2022年', '2023年', '2024年']

def fetch_prefecture_ids():
    """既存のprefecturesテーブルから 名前→id の対応表を取得する"""
    res = requests.get(
        f'{SUPABASE_URL}/rest/v1/prefectures',
        headers=SUPABASE_HEADERS,
        params={'select': 'id,name'}
    )
    res.raise_for_status()
    return {row['name']: row['id'] for row in res.json()}

def main():
    prefecture_ids = fetch_prefecture_ids()

    df = pd.read_csv(ROOT_DIR / 'jp_analyzer' / 'data' / 'FEH_00200524_260712002121.csv', encoding='cp932', skiprows=11)
    df = df[(df['男女別 コード'] == 0) & (df['人口 コード'] == 1)]
    df = df[df['全国・都道府県'] != '全国']

    rows = []
    for _, row in df.iterrows():
        name = row['全国・都道府県']
        pref_id = prefecture_ids.get(name)
        if pref_id is None:
            print(f'警告: {name} がprefecturesテーブルに見つかりません。スキップします。')
            continue

        for year_col in YEAR_COLUMNS:
            value_str = str(row[year_col]).replace(',', '')
            if value_str in ('', 'nan', '-', '***'):
                continue
            rows.append({
                'prefecture_id': pref_id,
                'indicator': 'population',
                'year': int(year_col.replace('年', '')),
                'value': float(value_str),
                'unit': '千人',
                'source': 'e-Stat 0003448232',
            })

    print(f'{len(rows)} 件を投入します')

    res = requests.post(
        f'{SUPABASE_URL}/rest/v1/prefecture_stats?on_conflict=prefecture_id,indicator,year',
        headers={**SUPABASE_HEADERS, 'Prefer': 'return=representation,resolution=merge-duplicates'},
        json=rows
    )
    print(res.status_code, res.text[:500])

if __name__ == '__main__':
    main()