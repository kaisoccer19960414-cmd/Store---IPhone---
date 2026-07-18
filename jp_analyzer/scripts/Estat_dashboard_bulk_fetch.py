"""
統計ダッシュボードAPI(https://dashboard.e-stat.go.jp/static/api)を使って、
キーワードにマッチする系列を都道府県×年で一括取得するスクリプト。

UIの「データ検索」画面は系列を10件までしか同時に選べないが、
このAPIには利用登録不要で誰でもアクセスできるので、系列を1件ずつ
(サイトポリシーに配慮して間隔を空けながら)自動で取得する。

出力は import_estat_unified.py の --shape long でそのまま読み込める
「時点,地域コード,地域,{系列名}【単位】,注記」形式のCSVにする。

使い方:
  1. --search-word でキーワード検索し、--list-only でまず件数と系列名一覧だけ確認する
  2. 件数が多すぎないか確認してから、--out を指定して実際に取得する
  3. できたCSVを import_estat_unified.py --shape long --inspect で確認してから投入する

注意:
  - 本APIの利用にあたっては、統計ダッシュボードのサイトポリシーを守ること。
  - 「短時間における大量のアクセス」は禁止されているため、--sleep(既定1秒)を
    極端に短くしないこと。
  - このAPIを使ったサービスを公開する場合は、下記のクレジット表示が必要:
    「このサービスは、統計ダッシュボードのAPI機能を使用していますが、
      サービスの内容は国によって保証されたものではありません。」
"""
import argparse
import re
import time
from pathlib import Path

import pandas as pd
import requests

BASE_URL = 'https://dashboard.e-stat.go.jp/api/1.0'

# JIS都道府県コード(5桁、末尾000)→都道府県名。統計ダッシュボードのregionCodeと一致する。
REGION_CODE_TO_NAME = {
    '01000': '北海道', '02000': '青森県', '03000': '岩手県', '04000': '宮城県',
    '05000': '秋田県', '06000': '山形県', '07000': '福島県', '08000': '茨城県',
    '09000': '栃木県', '10000': '群馬県', '11000': '埼玉県', '12000': '千葉県',
    '13000': '東京都', '14000': '神奈川県', '15000': '新潟県', '16000': '富山県',
    '17000': '石川県', '18000': '福井県', '19000': '山梨県', '20000': '長野県',
    '21000': '岐阜県', '22000': '静岡県', '23000': '愛知県', '24000': '三重県',
    '25000': '滋賀県', '26000': '京都府', '27000': '大阪府', '28000': '兵庫県',
    '29000': '奈良県', '30000': '和歌山県', '31000': '鳥取県', '32000': '島根県',
    '33000': '岡山県', '34000': '広島県', '35000': '山口県', '36000': '徳島県',
    '37000': '香川県', '38000': '愛媛県', '39000': '高知県', '40000': '福岡県',
    '41000': '佐賀県', '42000': '長崎県', '43000': '熊本県', '44000': '大分県',
    '45000': '宮崎県', '46000': '鹿児島県', '47000': '沖縄県',
}

TIME_CODE_PATTERN = re.compile(r'^(\d{4})(CY|FY)\d{2}$')


def parse_time_code(code):
    """「2015CY00」→2015、「2015FY00」→2015(年度)。どちらもint年で返す"""
    m = TIME_CODE_PATTERN.match(str(code))
    if not m:
        return None
    return int(m.group(1))


def as_list(value):
    """このAPIは1件だけの場合dict、複数の場合listで返してくることがあるので統一する"""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def fetch_indicator_list(search_word, region_rank='3', cycle='3'):
    """キーワードにマッチする系列のうち、指定した地域階級(既定:都道府県)×
    データ周期(既定:年)の組み合わせを持つものだけを返す"""
    res = requests.get(f'{BASE_URL}/Json/getIndicatorInfo', params={
        'Lang': 'JP',
        'SearchIndicatorWord': search_word,
    }, timeout=30)
    res.raise_for_status()
    data = res.json()

    result = data.get('GET_META_INDICATOR_INF', {}).get('RESULT', {})
    if result.get('status') != '0':
        raise SystemExit(f'API検索エラー: {result.get("errorMsg")}')

    class_obj = data.get('GET_META_INDICATOR_INF', {}).get('METADATA_INF', {}).get('CLASS_INF', {}).get('CLASS_OBJ')
    matched = []
    for obj in as_list(class_obj):
        code = obj.get('@code')
        name = obj.get('@name')
        for c in as_list(obj.get('CLASS')):
            if c.get('cycle', {}).get('@code') == cycle and c.get('RegionalRank', {}).get('@code') == region_rank:
                matched.append({
                    'code': code,
                    'name': name,
                    'unit': c.get('@unit', ''),
                    'stat_name': c.get('@statName', ''),
                    'from_date': c.get('@fromDate'),
                    'to_date': c.get('@toDate'),
                })
                break  # 都道府県×年の組み合わせが1つ見つかれば十分
    return matched


def fetch_data_for_indicator(indicator_code, region_rank='3', cycle='3'):
    """1系列分の都道府県×年データを取得する。(region_code, year, value)のリストを返す"""
    res = requests.get(f'{BASE_URL}/Json/getData', params={
        'Lang': 'JP',
        'IndicatorCode': indicator_code,
        'RegionalRank': region_rank,
        'Cycle': cycle,
        'IsSeasonalAdjustment': '1',
        'MetaGetFlg': 'Y',
    }, timeout=30)
    res.raise_for_status()
    data = res.json()

    stats = data.get('GET_STATS', {})
    result = stats.get('RESULT', {})
    if result.get('status') != '0':
        return None, result.get('errorMsg')

    data_obj = stats.get('STATISTICAL_DATA', {}).get('DATA_INF', {}).get('DATA_OBJ')
    rows = []
    for obj in as_list(data_obj):
        v = obj.get('VALUE', {})
        year = parse_time_code(v.get('@time'))
        if year is None:
            continue
        region_code = v.get('@regionCode')
        value_str = v.get('$')
        if value_str in (None, '', '-', '***'):
            continue
        try:
            value = float(value_str)
        except ValueError:
            continue
        rows.append((region_code, year, value))
    return rows, None


def main():
    parser = argparse.ArgumentParser(description='統計ダッシュボードAPIで系列を一括取得する')
    parser.add_argument('--search-word', required=True, help='系列名の検索キーワード(例: "総人口")')
    parser.add_argument('--out', help='出力先CSVファイル名(jp_analyzer/data/配下)。--list-onlyの場合は不要')
    parser.add_argument('--sleep', type=float, default=1.0,
                         help='系列取得ごとの待機秒数(サイトポリシー配慮のため、極端に短くしないこと)')
    parser.add_argument('--limit', type=int, help='取得する系列数の上限(お試し用)')
    parser.add_argument('--list-only', action='store_true',
                         help='マッチする系列の一覧と件数だけ確認する(データは取得しない)')
    args = parser.parse_args()

    print(f'「{args.search_word}」にマッチする系列(都道府県×年)を検索中...')
    indicators = fetch_indicator_list(args.search_word)
    print(f'{len(indicators)} 件の系列が見つかりました\n')

    for ind in indicators:
        print(f"  {ind['code']}  {ind['name']}【{ind['unit']}】  "
              f"({ind['from_date']}〜{ind['to_date']})  出典: {ind['stat_name']}")

    if args.list_only:
        return

    if not args.out:
        raise SystemExit('--out を指定してください(--list-onlyでなければ必須)')

    if args.limit:
        indicators = indicators[:args.limit]

    ROOT_DIR = Path(__file__).resolve().parents[2]
    out_path = ROOT_DIR / 'jp_analyzer' / 'data' / args.out

    thin_rows = []  # 縦持ちでいったん集める。最後に横展開する

    print(f'\n=== データ取得開始({len(indicators)} 系列) ===')
    for i, ind in enumerate(indicators):
        print(f'[{i + 1}/{len(indicators)}] {ind["name"]} ({ind["code"]}) を取得中...')
        rows, err = fetch_data_for_indicator(ind['code'])
        if err:
            print(f'  エラー: {err}')
        else:
            column_name = f"{ind['name']}【{ind['unit']}】"
            for region_code, year, value in rows:
                pref_name = REGION_CODE_TO_NAME.get(region_code)
                if pref_name is None:
                    continue  # 都道府県以外(全国など)のコードはスキップ
                thin_rows.append({
                    '時点': f'{year}年',
                    '地域コード': region_code,
                    '地域': pref_name,
                    'column': column_name,
                    '値': value,
                })

        if i < len(indicators) - 1:
            time.sleep(args.sleep)  # サイトポリシー配慮の待機

    if not thin_rows:
        print('\n取得できたデータがありませんでした。')
        return

    # import_estat_unified.py --shape long がそのまま読める横持ち形式にピボットする
    # (時点,地域コード,地域 をキーに、系列ごとの列を横に並べる)
    df = pd.DataFrame(thin_rows)
    wide = df.pivot_table(
        index=['時点', '地域コード', '地域'],
        columns='column',
        values='値',
        aggfunc='first',
    ).reset_index()
    wide.columns.name = None

    wide.to_csv(out_path, index=False, encoding='utf-8-sig')

    print(f'\n{len(thin_rows)} 件(延べ)を {len(wide)} 行 × {len(wide.columns) - 3} 系列として')
    print(f'{out_path} に保存しました')
    print('\nこのファイルはそのまま import_estat_unified.py --shape long で読み込めます:')
    print(f'  python jp_analyzer/scripts/import_estat_unified.py --csv "{args.out}" --shape long --inspect')


if __name__ == '__main__':
    main()