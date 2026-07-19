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


def get_indicator_id(name, unit=None):
    """indicator名からIDを引く。新規作成時はunitもここで一緒に登録する
    (unitはindicatorsテーブル側に正規化してあり、prefecture_statsには持たせていない)。"""
    if name in _indicator_cache:
        return _indicator_cache[name]

    res = requests.get(
        f'{SUPABASE_URL}/rest/v1/indicators',
        headers=SUPABASE_HEADERS,
        params={'select': 'id', 'name': f'eq.{name}'}
    )
    res.raise_for_status()
    rows = res.json()
    if rows:
        _indicator_cache[name] = rows[0]['id']
        return _indicator_cache[name]

    res = requests.post(
        f'{SUPABASE_URL}/rest/v1/indicators',
        headers={**SUPABASE_HEADERS, 'Prefer': 'return=representation'},
        json={'name': name, 'unit': unit or ''}
    )
    res.raise_for_status()
    new_id = res.json()[0]['id']
    _indicator_cache[name] = new_id
    return new_id


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
    unitはindicatorsテーブル側に正規化してあるので、prefecture_stats自体には送らない。
    戻り値: [(開始件数, 終了件数, ステータスコード), ...]"""
    payload = []
    for r in rows:
        payload.append({
            'prefecture_id': r['prefecture_id'],
            'indicator_id': get_indicator_id(r['indicator'], unit=r.get('unit')),
            'year': r['year'],
            'value': r['value'],
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

    refresh_stats_meta()
    return results


def refresh_stats_meta():
    """指標一覧を集計済みで持っているマテリアライズドビュー(stats_meta)を再計算する。
    データ投入のたびに呼ぶことで、フロントの指標・年度セレクトが最新の状態に保たれる。
    (毎回全件集計し直すと重いクエリになるため、view ではなく materialized view + 手動更新にしている)"""
    try:
        res = requests.post(
            f'{SUPABASE_URL}/rest/v1/rpc/refresh_stats_meta',
            headers=SUPABASE_HEADERS,
            json={}
        )
        print(f'stats_metaの再計算: {res.status_code}')
    except Exception as e:
        print(f'stats_metaの再計算に失敗しました({e})。後で手動実行してください: select refresh_stats_meta();')


def find_indicators(exact=None, patterns=None):
    """indicatorsテーブルから、名前が一致する/部分一致するものを検索する(存在しなくても新規作成はしない)。
    exact: 完全一致させたい名前のリスト
    patterns: ILIKEパターン(%を含む)のリスト。例: ['%（女）', '就業者数%']
    戻り値: [{'id':.., 'name':..}, ...]"""
    found = {}
    for name in exact or []:
        res = requests.get(
            f'{SUPABASE_URL}/rest/v1/indicators',
            headers=SUPABASE_HEADERS,
            params={'select': 'id,name', 'name': f'eq.{name}'}
        )
        res.raise_for_status()
        for row in res.json():
            found[row['id']] = row

    for pattern in patterns or []:
        res = requests.get(
            f'{SUPABASE_URL}/rest/v1/indicators',
            headers=SUPABASE_HEADERS,
            params={'select': 'id,name', 'name': f'ilike.{pattern}'}
        )
        res.raise_for_status()
        for row in res.json():
            found[row['id']] = row

    return list(found.values())


def delete_indicators(indicator_ids, dry_run=False):
    """指定したindicator_idに紐づくprefecture_statsの行と、indicators自体の行を削除する。
    戻り値: 削除した(予定の)prefecture_stats行数の合計"""
    total = 0
    for indicator_id in indicator_ids:
        res = requests.get(
            f'{SUPABASE_URL}/rest/v1/prefecture_stats',
            headers=SUPABASE_HEADERS,
            params={'select': 'id', 'indicator_id': f'eq.{indicator_id}'}
        )
        res.raise_for_status()
        count = len(res.json())
        total += count

        if dry_run:
            continue

        del_res = requests.delete(
            f'{SUPABASE_URL}/rest/v1/prefecture_stats',
            headers=SUPABASE_HEADERS,
            params={'indicator_id': f'eq.{indicator_id}'}
        )
        print(f'  indicator_id={indicator_id}: {count}件削除 ({del_res.status_code})')

        # prefecture_stats側を消し終わったら、indicators本体の行も削除する
        requests.delete(
            f'{SUPABASE_URL}/rest/v1/indicators',
            headers=SUPABASE_HEADERS,
            params={'id': f'eq.{indicator_id}'}
        )

    if not dry_run:
        refresh_stats_meta()
    return total


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