"""
DB内の指標(indicator)から、「名前は違うけど中身が同じ(重複してそう)」な候補を見つけて、
実際の値を突き合わせて検証するスクリプト。

名前が似てるだけで即「重複」と決めつけるのは危険(同じような名前でも、集計方法が違って
年度範囲や値が別モノということが過去に何度もあった)ため、以下の2段階で判定する:
  1. 末尾の「（社会・人口統計体系）」「（国勢調査）」「（～20XX年）」のような
     "出典・バージョン違い"を示す決まったパターンを取り除いて、同じ土台の名前になる
     指標をグループ化する(候補探し)
  2. 候補同士で、都道府県・年度が重なってる部分の値を実際に突き合わせて、
     どれくらい一致してるかを計算する(裏取り)

使い方:
  python find_duplicate_indicators.py
  → jp_analyzer/duplicate_candidates.csv に候補一覧を書き出す
"""
import csv
import re
from collections import defaultdict

import requests
import stats_db

# 末尾に付いてる「出典・バージョン違い」を示す典型的なパターン。
# これに一致する部分を取り除いた残りが同じなら、同じ内容の別バージョンである可能性が高い。
VARIANT_SUFFIX_PATTERN = re.compile(
    r'('
    r'（社会・人口統計体系）'
    r'|（国勢調査）'
    r'|（人口推計）'
    r'|（全国消費実態調査）'
    r'|（全国家計構造調査）'
    r'|（第１１回改定産業分類）'
    r'|（第12回～改定産業分類）'
    r'|（第11回改定産業分類）'
    r'|（～\d{4}年?）'
    r')$'
)


def base_name(name):
    """末尾の出典違いパターンを1個取り除いた名前を返す。何も取り除けなければNoneを返す
    (=そもそも「バージョン違い」の候補ではない、という意味)"""
    m = VARIANT_SUFFIX_PATTERN.search(name)
    if not m:
        return None
    return name[:m.start()]


def fetch_stats_meta_all():
    all_rows = []
    page_size = 1000
    offset = 0
    while True:
        res = requests.get(
            f'{stats_db.SUPABASE_URL}/rest/v1/stats_meta',
            headers=stats_db.SUPABASE_HEADERS,
            params={'select': 'indicator,unit,years', 'order': 'indicator.asc',
                     'limit': page_size, 'offset': offset}
        )
        res.raise_for_status()
        batch = res.json()
        all_rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return all_rows


def fetch_indicator_id_map():
    res = requests.get(
        f'{stats_db.SUPABASE_URL}/rest/v1/indicators',
        headers=stats_db.SUPABASE_HEADERS,
        params={'select': 'id,name'}
    )
    res.raise_for_status()
    return {row['name']: row['id'] for row in res.json()}


def fetch_values(indicator_id):
    """(prefecture_id, year) -> value の辞書を返す"""
    rows = []
    page_size = 1000
    offset = 0
    while True:
        res = requests.get(
            f'{stats_db.SUPABASE_URL}/rest/v1/prefecture_stats',
            headers=stats_db.SUPABASE_HEADERS,
            params={
                'select': 'prefecture_id,year,value',
                'indicator_id': f'eq.{indicator_id}',
                'limit': page_size,
                'offset': offset,
            }
        )
        res.raise_for_status()
        batch = res.json()
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return {(r['prefecture_id'], r['year']): r['value'] for r in rows}


def compare_pair(id_a, id_b):
    """2つのindicator_idの値を突き合わせて、一致率を返す"""
    values_a = fetch_values(id_a)
    values_b = fetch_values(id_b)
    common_keys = set(values_a) & set(values_b)
    if not common_keys:
        return None, 0

    matches = 0
    for k in common_keys:
        va, vb = values_a[k], values_b[k]
        if va is None or vb is None:
            continue
        # 数値の丸め誤差くらいは許容する(1%以内なら一致とみなす)
        if va == vb or (va != 0 and abs(va - vb) / abs(va) < 0.01):
            matches += 1

    match_rate = matches / len(common_keys)
    return match_rate, len(common_keys)


def main():
    meta = fetch_stats_meta_all()
    print(f'{len(meta)} 件のindicatorを確認します')

    groups = defaultdict(list)
    for row in meta:
        name = row['indicator']
        base = base_name(name)
        if base is None:
            continue
        groups[base].append(row)
        # base名そのもの(接尾辞が付いてないもの)も同じグループに入るか、後で照合する

    # base名そのままの指標も同じグループに合流させる
    name_to_row = {row['indicator']: row for row in meta}
    for base in list(groups.keys()):
        if base in name_to_row:
            groups[base].append(name_to_row[base])

    # 2件以上あるグループだけが「重複候補」
    candidate_groups = {base: rows for base, rows in groups.items() if len(rows) >= 2}
    print(f'名前パターンから見つかった候補グループ: {len(candidate_groups)}件')

    indicator_ids = fetch_indicator_id_map()

    output_rows = []
    for i, (base, rows) in enumerate(candidate_groups.items(), 1):
        names = [r['indicator'] for r in rows]
        print(f'[{i}/{len(candidate_groups)}] 検証中: {base!r} ({len(names)}候補)')

        # 総当たりで突き合わせ(候補グループは大抵2〜3件なので現実的な件数)
        for a in range(len(rows)):
            for b in range(a + 1, len(rows)):
                name_a, name_b = names[a], names[b]
                id_a = indicator_ids.get(name_a)
                id_b = indicator_ids.get(name_b)
                if id_a is None or id_b is None:
                    continue

                match_rate, common_count = compare_pair(id_a, id_b)
                if match_rate is None:
                    verdict = '年度・都道府県が重ならない(別データの可能性)'
                elif match_rate > 0.95:
                    verdict = '重複の可能性が高い(値がほぼ一致)'
                elif match_rate > 0.5:
                    verdict = '部分的に近い値(要確認)'
                else:
                    verdict = '別データ(値が一致しない)'

                output_rows.append({
                    'base_name': base,
                    'indicator_a': name_a,
                    'years_a': f"{min(rows[a]['years'])}-{max(rows[a]['years'])}" if rows[a]['years'] else '',
                    'indicator_b': name_b,
                    'years_b': f"{min(rows[b]['years'])}-{max(rows[b]['years'])}" if rows[b]['years'] else '',
                    'common_year_pref_pairs': common_count,
                    'match_rate': f'{match_rate:.1%}' if match_rate is not None else '',
                    'verdict': verdict,
                })

    output_path = 'duplicate_candidates.csv'
    with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'base_name', 'indicator_a', 'years_a', 'indicator_b', 'years_b',
            'common_year_pref_pairs', 'match_rate', 'verdict'
        ])
        writer.writeheader()
        writer.writerows(output_rows)

    print(f'\n{output_path} に {len(output_rows)} 件の比較結果を書き出しました。')
    print('verdict列でExcelフィルターをかければ、「重複の可能性が高い」ものだけ絞り込めます。')


if __name__ == '__main__':
    main()