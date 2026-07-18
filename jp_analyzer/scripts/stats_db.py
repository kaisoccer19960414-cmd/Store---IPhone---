"""
正規化された prefecture_stats(indicator_id / source_id を使う形)への
読み書きをまとめた共通モジュール。

既存の各インポートスクリプトは、これまで通り
  {'prefecture_id': ..., 'indicator': '人口', 'year': 2024, 'value': ..., 'unit': '人', 'source': '...'}
という「indicator/sourceが日本語文字列のままの行」を組み立てて、
最後にこのモジュールの upsert_rows() に渡すだけでよい。
indicator名・source名 → id への変換(無ければ新規作成)はここで面倒を見る。
"""
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

_indicator_cache = {}
_source_cache = {}


def _get_or_create_id(table, name, cache):
    if name in cache:
        return cache[name]

    res = requests.get(
        f'{SUPABASE_URL}/rest/v1/{table}',
        headers=SUPABASE_HEADERS,
        params={'select': 'id', 'name': f'eq.{name}'}
    )
    res.raise_for_status()
    rows = res.json()
    if rows:
        cache[name] = rows[0]['id']
        return cache[name]

    res = requests.post(
        f'{SUPABASE_URL}/rest/v1/{table}',
        headers={**SUPABASE_HEADERS, 'Prefer': 'return=representation'},
        json={'name': name}
    )
    res.raise_for_status()
    new_id = res.json()[0]['id']
    cache[name] = new_id
    return new_id


def get_indicator_id(name):
    return _get_or_create_id('indicators', name, _indicator_cache)


def get_source_id(name):
    return _get_or_create_id('sources', name, _source_cache)


def fetch_prefecture_ids():
    res = requests.get(
        f'{SUPABASE_URL}/rest/v1/prefectures',
        headers=SUPABASE_HEADERS,
        params={'select': 'id,name'}
    )
    res.raise_for_status()
    return {row['name']: row['id'] for row in res.json()}


def upsert_rows(rows, chunk_size=5000):
    """rows: [{'prefecture_id','indicator','year','value','unit','source'}, ...] の形を受け取り、
    indicator/sourceをIDに変換したうえでprefecture_statsにUPSERTする。
    戻り値: [(開始件数, 終了件数, ステータスコード), ...]"""
    payload = []
    for r in rows:
        payload.append({
            'prefecture_id': r['prefecture_id'],
            'indicator_id': get_indicator_id(r['indicator']),
            'year': r['year'],
            'value': r['value'],
            'unit': r.get('unit') or '',
            'source_id': get_source_id(r['source']) if r.get('source') else None,
        })

    results = []
    for start in range(0, len(payload), chunk_size):
        chunk = payload[start:start + chunk_size]
        try:
            res = requests.post(
                f'{SUPABASE_URL}/rest/v1/prefecture_stats?on_conflict=prefecture_id,indicator_id,year',
                headers={**SUPABASE_HEADERS, 'Prefer': 'return=representation,resolution=merge-duplicates'},
                json=chunk
            )
            results.append((start, start + len(chunk), res.status_code))
            print(f'{start}〜{start + len(chunk)}件目: {res.status_code}')
        except Exception as e:
            print(f'{start}〜{start + len(chunk)}件目: 例外({e})。スキップして続行します。')
            results.append((start, start + len(chunk), None))
    return results


def fetch_stats_by_indicator(indicator_name, select='prefecture_id,year,value'):
    """指定したindicator名の全レコードを、1000件の上限に引っかからないようページングして取得する。
    compute_*.py系のスクリプト(population_change_rateなど)が使う。"""
    indicator_id = get_indicator_id(indicator_name)
    all_rows = []
    page_size = 1000
    offset = 0
    while True:
        res = requests.get(
            f'{SUPABASE_URL}/rest/v1/prefecture_stats',
            headers=SUPABASE_HEADERS,
            params={
                'select': select,
                'indicator_id': f'eq.{indicator_id}',
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