"""
統計ダッシュボードAPI(https://dashboard.e-stat.go.jp/static/api)から、
都道府県レベル(regionalRank=3)の年次データ(cycle=3、無ければ4)を持つ系列を検索し、
まとめてprefecture_statsに投入するスクリプト。

10系列までしか選べないブラウザのUIと違い、APIには系列数の制限が無いため、
①統計メタ情報（系列）取得(getIndicatorInfo)で対象系列を検索し、
⑥統計データ取得(getData)を系列ごとに順番に呼び出して集める。

indicatorのラベルは、系列名(indicatorNm)をそのまま日本語で使う。
これによりprefecturesUI.jsのINDICATOR_LABELSへの手動追加が不要になる
(indicatorLabel()は対応表に無ければコードをそのまま表示するだけの安全設計なので、
 日本語をそのままindicatorに使っても表示は自然に成立する)。

使い方の例:
  # まず「人口・世帯」カテゴリ(indicatorCdが02始まり)で、対象系列がいくつあるか確認
  python bulk_import_dashboard_api.py --indicator-prefix 02 --list-only

  # 5件だけ試しに取得してみる(--dry-run)
  python bulk_import_dashboard_api.py --indicator-prefix 02 --limit 5 --dry-run

  # 本番投入(1系列ごとに1秒あける。系列数が多いとかなり時間がかかる)
  python bulk_import_dashboard_api.py --indicator-prefix 02 --sleep 1.0
"""
import argparse
import io
import re
import time

import pandas as pd
import requests
import stats_db  # jp_analyzer/scripts/stats_db.py (indicator/sourceの正規化を吸収する共通モジュール)

DASHBOARD_BASE = 'https://dashboard.e-stat.go.jp/api/1.0/Csv'

# JIS都道府県コード(01〜47)の順の都道府県名。統計ダッシュボードのregionCdはこの体系に準拠している。
JIS_PREF_NAMES = [
    '北海道', '青森県', '岩手県', '宮城県', '秋田県', '山形県', '福島県', '茨城県', '栃木県', '群馬県',
    '埼玉県', '千葉県', '東京都', '神奈川県', '新潟県', '富山県', '石川県', '福井県', '山梨県', '長野県',
    '岐阜県', '静岡県', '愛知県', '三重県', '滋賀県', '京都府', '大阪府', '兵庫県', '奈良県', '和歌山県',
    '鳥取県', '島根県', '岡山県', '広島県', '山口県', '徳島県', '香川県', '愛媛県', '高知県', '福岡県',
    '佐賀県', '長崎県', '熊本県', '大分県', '宮崎県', '鹿児島県', '沖縄県',
]


def region_name_from_code(region_cd):
    try:
        n = int(str(region_cd)) // 1000
    except ValueError:
        return None
    if 1 <= n <= 47:
        return JIS_PREF_NAMES[n - 1]
    return None


def fetch_prefecture_ids():
    return stats_db.fetch_prefecture_ids()


def get_status(text):
    for line in text.splitlines():
        if line.startswith('"STATUS"'):
            return line.split(',')[1].strip().strip('"')
    return None


def extract_table(text):
    """統計ダッシュボードAPIのCSVレスポンスは、前置きのメタ情報の後に実データの表が続く独自形式。
    "indicatorCd"から始まる行を表のヘッダとみなして、そこから読み込む。
    dtype=strで読むのは、系列コードや地域コードの先頭のゼロが消えるのを防ぐため。"""
    lines = text.splitlines()
    header_idx = None
    for i, line in enumerate(lines):
        if line.startswith('"indicatorCd"'):
            header_idx = i
            break
    if header_idx is None:
        return None
    csv_text = '\n'.join(lines[header_idx:])
    return pd.read_csv(io.StringIO(csv_text), dtype=str)


def fetch_indicator_info(search_word=None, category=None):
    params = {'Lang': 'JP'}
    if search_word:
        params['SearchIndicatorWord'] = search_word
    if category:
        params['Category'] = category
    res = requests.get(f'{DASHBOARD_BASE}/getIndicatorInfo', params=params, timeout=30)
    res.raise_for_status()
    if get_status(res.text) != '0':
        raise SystemExit(f'getIndicatorInfoが失敗しました: {res.text[:300]}')
    return extract_table(res.text)


def fetch_series_data(indicator_code, cycle, retries=3, pause=1.0):
    params = {
        'Lang': 'JP',
        'IndicatorCode': indicator_code,
        'RegionalRank': 3,          # 都道府県レベル
        'Cycle': cycle,             # 3=暦年、4=年度
        'IsSeasonalAdjustment': 1,  # 原数値のみ(季節調整値は除く)
        'MetaGetFlg': 'N',
        'SectionHeaderFlg': 1,
    }
    for attempt in range(retries):
        try:
            res = requests.get(f'{DASHBOARD_BASE}/getData', params=params, timeout=30)
        except requests.RequestException:
            time.sleep(pause * (attempt + 1))
            continue
        if res.status_code == 200:
            status = get_status(res.text)
            if status == '0':
                return extract_table(res.text)
            return None  # 該当データなし(この周期・地域階級の組み合わせが存在しない等)
        time.sleep(pause * (attempt + 1))
    raise RuntimeError(f'{indicator_code}: リトライしても取得できませんでした')


def clean_str(value, default=''):
    """NaN(pandasの欠損値)をJSONで扱えるよう空文字に変換する"""
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    return value


def main():
    parser = argparse.ArgumentParser(description='統計ダッシュボードAPIから都道府県別年次データを一括取得・投入する')
    parser.add_argument('--search-word', help='①統計メタ情報（系列）取得のSearchIndicatorWord')
    parser.add_argument('--category', help='①のCategoryパラメータ')
    parser.add_argument('--indicator', action='append',
                         help='indicatorCdを直接指定したい場合(複数指定可)。指定時は①の検索をスキップ')
    parser.add_argument('--indicator-prefix',
                         help='indicatorCdの先頭一致でさらに絞り込む(例: "02"で人口・世帯カテゴリのみ)')
    parser.add_argument('--limit', type=int, help='投入する系列数の上限(お試し用)')
    parser.add_argument('--sleep', type=float, default=1.0, help='系列ごとのリクエスト間隔(秒)')
    parser.add_argument('--source', default='統計ダッシュボードAPI')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--list-only', action='store_true', help='対象系列の一覧を表示するだけで、取得・投入はしない')
    args = parser.parse_args()

    indicator_cycle = {}
    indicator_names = {}
    indicator_units = {}

    if args.indicator:
        indicator_codes = args.indicator
        for code in indicator_codes:
            indicator_cycle[code] = '3'
            indicator_names[code] = code
            indicator_units[code] = ''
    else:
        info_df = fetch_indicator_info(search_word=args.search_word, category=args.category)
        if info_df is None or len(info_df) == 0:
            raise SystemExit('系列が見つかりませんでした。--search-wordや--categoryを見直してください。')

        # 都道府県レベル(regionalRank=3)のデータを持つ系列だけに絞る
        pref_level = info_df[info_df['regionalRank'] == '3'].copy()
        if args.indicator_prefix:
            pref_level = pref_level[pref_level['indicatorCd'].str.startswith(args.indicator_prefix)]

        # 系列ごとに使えるcycleを集約。3(暦年)を優先し、無ければ4(年度)
        grouped = {}
        for _, row in pref_level.iterrows():
            code = row['indicatorCd']
            grouped.setdefault(code, {
                'name': row['indicatorNm'],
                'unit': row.get('unitNm', ''),
                'cycles': set(),
            })
            grouped[code]['cycles'].add(row['cycle'])

        indicator_codes = []
        for code, info in grouped.items():
            cycle = '3' if '3' in info['cycles'] else ('4' if '4' in info['cycles'] else None)
            if cycle is None:
                continue
            indicator_codes.append(code)
            indicator_names[code] = info['name']
            indicator_units[code] = clean_str(info['unit'])
            indicator_cycle[code] = cycle

        print(f'都道府県×暦年(または年度)のデータを持つ系列: {len(indicator_codes)}件')

    if args.limit:
        indicator_codes = indicator_codes[:args.limit]

    if args.list_only:
        for code in indicator_codes:
            print(code, indicator_names.get(code, ''), indicator_units.get(code, ''), indicator_cycle.get(code, ''))
        return

    prefecture_ids = fetch_prefecture_ids()

    all_rows = []
    failed = []

    for i, code in enumerate(indicator_codes, 1):
        cycle = indicator_cycle.get(code, '3')
        name = indicator_names.get(code, code)
        print(f'[{i}/{len(indicator_codes)}] {code} ({name}) を取得中...')
        try:
            df = fetch_series_data(code, cycle)
        except RuntimeError as e:
            print(f'  失敗: {e}')
            failed.append(code)
            time.sleep(args.sleep)
            continue

        if df is None or len(df) == 0:
            time.sleep(args.sleep)
            continue

        for _, row in df.iterrows():
            m = re.match(r'^(\d{4})(CY|FY)\d+$', str(row['timeCd']))
            if not m:
                continue
            year = int(m.group(1))
            pref_name = region_name_from_code(row['regionCd'])
            if pref_name is None:
                continue
            pref_id = prefecture_ids.get(pref_name)
            if pref_id is None:
                continue
            value_str = str(row['value']).replace(',', '').strip()
            if value_str.lower() in ('', 'nan', 'none'):
                continue
            try:
                value = float(value_str)
            except ValueError:
                continue
            if value != value or value in (float('inf'), float('-inf')):
                continue  # NaN/infはJSONで送れないためスキップ

            all_rows.append({
                'prefecture_id': pref_id,
                'indicator': name,     # 日本語の系列名をそのままindicatorとして使う
                'year': year,
                'value': value,
                'unit': clean_str(indicator_units.get(code, '')),
                'source': args.source,
            })

        time.sleep(args.sleep)

    print(f'\n合計 {len(all_rows)} 件を投入します(系列数: {len(indicator_codes)}、失敗した系列: {len(failed)})')
    if failed:
        print('取得に失敗した系列コード:', failed)

    if args.dry_run:
        for r in all_rows[:10]:
            print(r)
        print('(--dry-run のため実際には投入していません)')
        return

    if not all_rows:
        print('投入するデータがありません。')
        return

    stats_db.upsert_rows(all_rows)


if __name__ == '__main__':
    main()