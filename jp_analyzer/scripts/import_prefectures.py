import os
from pathlib import Path
import pandas as pd
import requests
from dotenv import load_dotenv

# このファイルから3階層上(プロジェクトのルート)の.envを明示的に指定して読み込む
ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / '.env')

SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_KEY')

SUPABASE_HEADERS = {
    'apikey': SUPABASE_SERVICE_KEY,
    'Authorization': f'Bearer {SUPABASE_SERVICE_KEY}',
    'Content-Type': 'application/json',
}

# 都道府県 → 地方ブロック(定番の8地方区分)
REGION_BLOCK = {
    '北海道': '北海道',
    '青森県': '東北', '岩手県': '東北', '宮城県': '東北', '秋田県': '東北', '山形県': '東北', '福島県': '東北',
    '茨城県': '関東', '栃木県': '関東', '群馬県': '関東', '埼玉県': '関東', '千葉県': '関東', '東京都': '関東', '神奈川県': '関東',
    '新潟県': '中部', '富山県': '中部', '石川県': '中部', '福井県': '中部', '山梨県': '中部', '長野県': '中部', '岐阜県': '中部', '静岡県': '中部', '愛知県': '中部',
    '三重県': '近畿', '滋賀県': '近畿', '京都府': '近畿', '大阪府': '近畿', '兵庫県': '近畿', '奈良県': '近畿', '和歌山県': '近畿',
    '鳥取県': '中国', '島根県': '中国', '岡山県': '中国', '広島県': '中国', '山口県': '中国',
    '徳島県': '四国', '香川県': '四国', '愛媛県': '四国', '高知県': '四国',
    '福岡県': '九州・沖縄', '佐賀県': '九州・沖縄', '長崎県': '九州・沖縄', '熊本県': '九州・沖縄',
    '大分県': '九州・沖縄', '宮崎県': '九州・沖縄', '鹿児島県': '九州・沖縄', '沖縄県': '九州・沖縄',
}

def main():
    df = pd.read_csv('jp_analyzer/data/FEH_00200524_260712002121.csv', encoding='cp932', skiprows=11)

    # 男女計(0)・総人口(1)の行だけに絞る
    df = df[(df['男女別 コード'] == 0) & (df['人口 コード'] == 1)]
    # 「全国」の行は都道府県ではないので除外
    df = df[df['全国・都道府県'] != '全国']

    rows = []
    for _, row in df.iterrows():
        name = row['全国・都道府県']
        population_str = str(row['2024年']).replace(',', '')
        if population_str in ('', 'nan', '-', '***'):
            continue

        rows.append({
            'name': name,
            'region_block': REGION_BLOCK.get(name, '不明'),
            'population': int(population_str),
            'population_year': 2024,
        })

    print(f'{len(rows)} 件を投入します')

    res = requests.post(
        f'{SUPABASE_URL}/rest/v1/prefectures',
        headers={**SUPABASE_HEADERS, 'Prefer': 'return=representation,resolution=merge-duplicates'},
        json=rows
    )
    print(res.status_code, res.text[:500])

if __name__ == '__main__':
    main()