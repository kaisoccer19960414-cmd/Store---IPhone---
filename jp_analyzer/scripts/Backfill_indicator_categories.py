"""
既存のindicatorsテーブルに「カテゴリ(大分類)」を後付けするスクリプト。

- 統計ダッシュボードAPI経由で投入した指標は、系列コードの先頭2桁(Category)から
  もう一度カタログを取得し直して、指標名でカテゴリを割り当てる。
- 手動で投入したslug系(population, births等)は、決め打ちの対応表で割り当てる。

事前にSupabaseのSQL Editorで add_category_column.sql を実行しておくこと。

使い方:
  python backfill_indicator_categories.py
"""
import requests
import bulk_import_dashboard_api as dash
import stats_db

CATEGORY_LABELS = {
    '01': '国土・気象',
    '02': '人口・世帯',
    '03': '労働・賃金',
    '04': '農林水産業',
    '05': '鉱工業',
    '06': '商業・サービス業',
    '07': '企業・家計・経済',
    '08': '住宅・土地・建設',
    '09': 'エネルギー・水',
    '10': '運輸・観光',
    '11': '情報通信・科学技術',
    '12': '教育・文化・スポーツ',
    '13': '行財政',
}

# 統計ダッシュボードAPI経由ではなく、手動で投入したslug系の指標の対応表
MANUAL_CATEGORY_OVERRIDES = {
    'population': '人口・世帯',
    'population_change_rate': '人口・世帯',
    'births': '人口・世帯',
    'deaths': '人口・世帯',
    'natural_change': '人口・世帯',
    'social_change': '人口・世帯',
    'divorces': '人口・世帯',
    'total_area': '国土・気象',
    'forest_area': '国土・気象',
    'avg_temperature': '国土・気象',
    'max_temperature': '国土・気象',
    'min_temperature': '国土・気象',
    'sunny_days': '国土・気象',
    'cloudy_days': '国土・気象',
    'rain_days': '国土・気象',
    'job_availability_ratio': '労働・賃金',
    'labor_force_population': '労働・賃金',
    'primary_industry_workers': '労働・賃金',
    'secondary_industry_workers': '労働・賃金',
    'tertiary_industry_workers': '労働・賃金',
}


def patch_category(name, category):
    """名前の完全一致(eq.)でPATCHする。indicator名には括弧やカンマが含まれることが多く、
    inフィルタでまとめて指定すると壊れやすいため、1件ずつ安全に処理する。"""
    res = requests.patch(
        f'{stats_db.SUPABASE_URL}/rest/v1/indicators',
        headers=stats_db.SUPABASE_HEADERS,
        params={'name': f'eq.{name}'},
        json={'category': category}
    )
    return res.status_code


def main():
    updated = 0
    not_found_in_db = []

    # ① 統計ダッシュボードAPI経由で投入した指標
    for prefix, label in CATEGORY_LABELS.items():
        print(f'=== {prefix} {label} を処理中... ===')
        info_df = dash.fetch_indicator_info(category=prefix)
        if info_df is None or len(info_df) == 0:
            print('  該当なし')
            continue
        names = sorted(set(info_df['indicatorNm'].tolist()))
        print(f'  {len(names)}件の名前を割り当てます')
        for name in names:
            status = patch_category(name, label)
            if status not in (200, 204):
                not_found_in_db.append((name, label, status))
            else:
                updated += 1

    # ② 手動で投入したslug系の指標
    print('=== 手動投入分を処理中... ===')
    for name, label in MANUAL_CATEGORY_OVERRIDES.items():
        status = patch_category(name, label)
        if status not in (200, 204):
            not_found_in_db.append((name, label, status))
        else:
            updated += 1

    print(f'\n{updated} 件のindicatorにカテゴリを割り当てました。')
    if not_found_in_db:
        print(f'警告: 更新に失敗した/見つからなかったもの: {len(not_found_in_db)}件')
        for name, label, status in not_found_in_db[:10]:
            print(f'  {name!r} ({label}) status={status}')

    stats_db.refresh_stats_meta()


if __name__ == '__main__':
    main()