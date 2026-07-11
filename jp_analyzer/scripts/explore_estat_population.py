# scripts/explore_estat_population.py
import os
import requests
from dotenv import load_dotenv
import pandas as pd

df = pd.read_csv('jp_analyzer/data/FEH_00200524_260712002121.csv', encoding='cp932', skiprows=11)

print(list(df.columns))
print(df.head(10))

load_dotenv()

APP_ID = os.environ.get('ESTAT_APP_ID')
STATS_DATA_ID = '0003448232'   # 都道府県、男女別人口－総人口、日本人人口（各年10月1日現在）

def main():
    if not APP_ID:
        raise SystemExit('ESTAT_APP_ID が .env に設定されていません')

    res = requests.get(
        'https://api.e-stat.go.jp/rest/3.0/app/json/getStatsData',
        params={
            'appId': APP_ID,
            'statsDataId': STATS_DATA_ID,
            'lang': 'J',
        }
    )
    res.raise_for_status()
    data = res.json()

    result = data['GET_STATS_DATA']['RESULT']
    if result['STATUS'] != 0:
        raise SystemExit(f"APIエラー: {result.get('ERROR_MSG', '不明なエラー')}")

    stat_data = data['GET_STATS_DATA']['STATISTICAL_DATA']
    class_objs = stat_data['CLASS_INF']['CLASS_OBJ']

    print('=== 分類(CLASS_OBJ)一覧 ===')
    for obj in class_objs:
        print(f"- {obj['@id']} : {obj['@name']}")
        classes = obj['CLASS']
        if isinstance(classes, dict):
            classes = [classes]
        for c in classes[:10]:  # 長いので先頭10件だけ表示
            print(f"    {c.get('@code')} -> {c.get('@name')}")

    values = stat_data['DATA_INF']['VALUE']
    print(f'\n=== データ件数: {len(values)} 件 ===')
    print('先頭5件のサンプル:')
    for v in values[:5]:
        print(v)

if __name__ == '__main__':
    main()