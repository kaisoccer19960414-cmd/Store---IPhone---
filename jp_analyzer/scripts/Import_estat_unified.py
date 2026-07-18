"""
e-Stat / 統計ダッシュボードから落としてきたCSVを、prefecture_statsに取り込むための統合スクリプト。

これまで形式ごとにバラバラに作っていた
  - import_stat_csv.py            (行=都道府県、列=年度。「〇〇 コード」列でフィルタ)
  - import_social_demographics.py  (行=年度×都道府県、列=指標が大量。社会・人口統計体系)
  - import_estat_timeseries_csv.py (時点/地域コード/地域/値、月次+年計混在)
  - import_estat_regional_csv.py   (行=年度、列=都道府県)
を、--shape で切り替えて1本にまとめたもの。

使い方の概要:
  1. --inspect で列名・年度の検出状況を確認する
  2. --dry-run で投入内容を確認する
  3. 問題なければ --dry-run を外して本番投入する
"""
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

YEAR_PATTERN = re.compile(r'^(\d{4})年度?$')
# 「1995年10月〜1996年9月」のような期間形式。終了年を代表年として扱う
YEAR_RANGE_PATTERN = re.compile(r'^(\d{4})年\d{1,2}月[〜～~](\d{4})年\d{1,2}月$')
UNIT_PATTERN = re.compile(r'[【\[](.+?)[】\]]')


def fetch_prefecture_ids():
    res = requests.get(
        f'{SUPABASE_URL}/rest/v1/prefectures',
        headers=SUPABASE_HEADERS,
        params={'select': 'id,name'}
    )
    res.raise_for_status()
    return {row['name']: row['id'] for row in res.json()}


def parse_year(value):
    """「2024年」「2024年度」「1995年10月〜1996年9月」等から代表年(int)を取り出す。該当しなければNone"""
    s = str(value).strip()
    m = YEAR_PATTERN.match(s)
    if m:
        return int(m.group(1))
    m = YEAR_RANGE_PATTERN.match(s)
    if m:
        return int(m.group(2))
    return None


def parse_number(value):
    s = str(value).replace(',', '').strip()
    if s in ('', 'nan', '-', '***', 'X', 'nan%'):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def extract_unit(col_name):
    m = UNIT_PATTERN.search(str(col_name))
    return m.group(1) if m else None


def strip_unit(col_name):
    return UNIT_PATTERN.sub('', str(col_name)).strip()


def parse_column_map(column_args):
    """--column '列名=indicator名' のリストを {列名: indicator名} の辞書にする。
    '=indicator名' を省略した場合は、列名から単位表記を除いたものをindicator名に使う。"""
    mapping = {}
    for c in column_args or []:
        if '=' in c:
            col, indicator = c.split('=', 1)
        else:
            col, indicator = c, strip_unit(c)
        mapping[col.strip()] = indicator.strip()
    return mapping


def parse_filters(filter_args):
    filters = {}
    for f in filter_args or []:
        col, _, value = f.partition('=')
        col, value = col.strip(), value.strip()
        if value.lstrip('-').isdigit():
            value = int(value)
        filters[col] = value
    return filters


# ---------------------------------------------------------------------------
# shape: long  (時点/地域/値(+注記) の縦持ち。1列でも複数列でも対応)
# ---------------------------------------------------------------------------
def handle_long(df, args, prefecture_ids):
    time_col = args.time_column
    pref_col = args.pref_column
    if time_col not in df.columns or pref_col not in df.columns:
        raise SystemExit(f'{time_col!r} または {pref_col!r} 列が見つかりません。実際の列: {list(df.columns)}')

    column_map = parse_column_map(args.column)
    if not column_map:
        # 指定がなければ、時点・地域・地域コード・注記系以外の列を全部対象にする
        ignore = {time_col, pref_col, '地域コード', '地域 コード'}
        column_map = {
            c: strip_unit(c) for c in df.columns
            if c not in ignore and not str(c).startswith('注記')
        }

    rows = []
    skipped_unmatched = set()
    for _, row in df.iterrows():
        name = row[pref_col]
        if name == '全国':
            continue
        pref_id = prefecture_ids.get(name)
        if pref_id is None:
            skipped_unmatched.add(name)
            continue

        year = parse_year(row[time_col])
        if year is None:
            continue

        for col, indicator_name in column_map.items():
            if col not in df.columns:
                continue
            value = parse_number(row[col])
            if value is None:
                continue
            indicator = args.indicator or indicator_name
            unit = args.unit or extract_unit(col) or ''
            rows.append({
                'prefecture_id': pref_id,
                'indicator': indicator,
                'year': year,
                'value': value,
                'unit': unit,
                'source': args.source,
            })
    return rows, skipped_unmatched


# ---------------------------------------------------------------------------
# shape: wide-year-rows  (行=年度、列=都道府県。統計ダッシュボード「地域別」形式)
# ---------------------------------------------------------------------------
def handle_wide_year_rows(df, args, prefecture_ids):
    time_col = args.time_column
    if time_col not in df.columns:
        raise SystemExit(f'{time_col!r} 列が見つかりません。実際の列: {list(df.columns)}')

    pref_columns = [c for c in df.columns if c != time_col and c != '全国']

    rows = []
    skipped_unmatched = set()
    for _, row in df.iterrows():
        year = parse_year(row[time_col])
        if year is None:
            continue
        for pref_name in pref_columns:
            pref_id = prefecture_ids.get(pref_name)
            if pref_id is None:
                skipped_unmatched.add(pref_name)
                continue
            value = parse_number(row[pref_name])
            if value is None:
                continue
            rows.append({
                'prefecture_id': pref_id,
                'indicator': args.indicator,
                'year': year,
                'value': value,
                'unit': args.unit or '',
                'source': args.source,
            })
    return rows, skipped_unmatched


# ---------------------------------------------------------------------------
# shape: wide-pref-rows  (行=都道府県、列=年度。従来のFEH/社会・人口統計体系形式)
# ---------------------------------------------------------------------------
def extract_year_columns(df):
    """年度を表す列を(位置インデックス, 年)のリストで返す(重複列名対策で位置ベース)"""
    year_columns = []
    for idx, col in enumerate(df.columns):
        year = parse_year(col)
        if year is not None:
            year_columns.append((idx, year))
    return year_columns


def handle_wide_pref_rows(df, args, prefecture_ids):
    for col, value in parse_filters(args.filter).items():
        df = df[df[col] == value]
    df = df[df[args.pref_column] != '全国']

    if args.value_column:
        # 特定の1列だけを対象にする(社会・人口統計体系のA1101など)場合は、
        # 「年度列」ではなくこの列1本だけを見る(年度は別の時点列から取る)
        if args.value_column not in df.columns:
            raise SystemExit(f'列 {args.value_column!r} が見つかりません。')
        rows = []
        skipped_unmatched = set()
        for _, row in df.iterrows():
            name = row[args.pref_column]
            pref_id = prefecture_ids.get(name)
            if pref_id is None:
                skipped_unmatched.add(name)
                continue
            year = parse_year(row[args.time_column]) if args.time_column in df.columns else None
            if year is None:
                continue
            value = parse_number(row[args.value_column])
            if value is None:
                continue
            rows.append({
                'prefecture_id': pref_id,
                'indicator': args.indicator,
                'year': year,
                'value': value,
                'unit': args.unit or extract_unit(args.value_column) or '',
                'source': args.source,
            })
        return rows, skipped_unmatched

    # 年度が列に展開されているケース(FEHの標準形式)
    year_columns = extract_year_columns(df)
    if not year_columns:
        raise SystemExit('年度の列が見つかりません。--filterや列名、または--value-columnの指定を確認してください。')

    rows = []
    skipped_unmatched = set()
    for _, row in df.iterrows():
        name = row[args.pref_column]
        pref_id = prefecture_ids.get(name)
        if pref_id is None:
            skipped_unmatched.add(name)
            continue
        for idx, year in year_columns:
            value = parse_number(row.iloc[idx])
            if value is None:
                continue
            rows.append({
                'prefecture_id': pref_id,
                'indicator': args.indicator,
                'year': year,
                'value': value,
                'unit': args.unit or '',
                'source': args.source,
            })
    return rows, skipped_unmatched


SHAPE_HANDLERS = {
    'long': handle_long,
    'wide-year-rows': handle_wide_year_rows,
    'wide-pref-rows': handle_wide_pref_rows,
}


def load_csv(csv_path, encoding, skiprows):
    return pd.read_csv(csv_path, encoding=encoding, skiprows=skiprows)


def main():
    parser = argparse.ArgumentParser(description='e-Stat/統計ダッシュボードの各種CSV形式を統合的に取り込むスクリプト')
    parser.add_argument('--csv', required=True, action='append', help='jp_analyzer/data/配下のファイル名。複数指定可')
    parser.add_argument('--shape', required=True, choices=list(SHAPE_HANDLERS.keys()))
    parser.add_argument('--encoding', default='utf-8-sig', help='wide-pref-rowsは大抵cp932')
    parser.add_argument('--skiprows', type=int, default=0)
    parser.add_argument('--time-column', default='時点')
    parser.add_argument('--pref-column', default='地域')
    parser.add_argument('--value-column', help='wide-pref-rowsで特定の1列だけ使う場合の列名')
    parser.add_argument('--column', action='append',
                         help='shape=longで使う列(複数指定可)。"列名" または "列名=indicator名"')
    parser.add_argument('--filter', action='append', help='shape=wide-pref-rowsの絞り込み。"列名=値"')
    parser.add_argument('--indicator', help='単一指標として投入する場合の名前。shape=longで--columnにindicator名を'
                                             '含めた場合は省略可')
    parser.add_argument('--unit')
    parser.add_argument('--source')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--inspect', action='store_true', help='列名・検出状況だけ確認するモード')
    args = parser.parse_args()

    all_rows = []
    all_skipped = set()

    for csv_name in args.csv:
        csv_path = ROOT_DIR / 'jp_analyzer' / 'data' / csv_name
        df = load_csv(csv_path, args.encoding, args.skiprows)

        if args.inspect:
            print(f'=== {csv_name} ===')
            print('列一覧:', list(df.columns))
            if args.time_column in df.columns:
                mask = df[args.time_column].apply(lambda v: parse_year(v) is not None)
                print(f'年度として検出できた行: {mask.sum()} / {len(df)}')
                print('検出された年度:', sorted({parse_year(v) for v in df.loc[mask, args.time_column]}))
            continue

        if not args.source:
            raise SystemExit('--source は必須です(--inspect以外)')
        if args.shape == 'long' and not args.column and not args.indicator:
            print('注意: --column も --indicator も指定されていません。'
                  '検出した全列をそれぞれ列名ベースのindicatorとして投入します。')

        prefecture_ids = fetch_prefecture_ids()
        rows, skipped = SHAPE_HANDLERS[args.shape](df, args, prefecture_ids)
        all_rows.extend(rows)
        all_skipped |= skipped

    if args.inspect:
        return

    if all_skipped:
        print(f'警告: prefecturesテーブルに見つからず、スキップした名前: {sorted(all_skipped)}')

    print(f'{len(all_rows)} 件を投入します')

    if args.dry_run:
        all_rows.sort(key=lambda r: (r['indicator'], r['prefecture_id'], r['year']))
        for r in all_rows[:10]:
            print(r)
        print('(--dry-run のため実際には投入していません)')
        return

    if not all_rows:
        print('投入するデータがありません。')
        return

    res = requests.post(
        f'{SUPABASE_URL}/rest/v1/prefecture_stats?on_conflict=prefecture_id,indicator,year',
        headers={**SUPABASE_HEADERS, 'Prefer': 'return=representation,resolution=merge-duplicates'},
        json=all_rows
    )
    print(res.status_code, res.text[:500])


if __name__ == '__main__':
    main()