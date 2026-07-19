"""
DBに登録されてる全indicator(指標)の一覧を、Excelで開けるCSVに書き出す。

今のサイトの<select>(プルダウン)は数千件あると流し見しかできんから、
一旦Excelに書き出して、フィルター・並び替えで「削除候補」を探しやすくするためのツール。

使い方:
  python export_indicators_csv.py
  → jp_analyzer/indicators_list.csv ができる。Excelで開いてフィルターをかければ、
    キーワードで絞り込んだり、年数(year_count)で並び替えたりできる。
"""
import csv
import requests
import stats_db


def fetch_stats_meta_all():
    """stats_metaビュー(indicator, unit, years)を全件ページングして取得する"""
    all_rows = []
    page_size = 1000
    offset = 0
    while True:
        res = requests.get(
            f'{stats_db.SUPABASE_URL}/rest/v1/stats_meta',
            headers=stats_db.SUPABASE_HEADERS,
            params={
                'select': 'indicator,unit,years',
                'order': 'indicator.asc',
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


def main():
    meta = fetch_stats_meta_all()
    print(f'{len(meta)} 件のindicatorを取得しました')

    output_path = 'indicators_list.csv'
    with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['indicator', 'unit', 'year_count', 'min_year', 'max_year', 'years'])
        for row in meta:
            years = row.get('years') or []
            year_count = len(years)
            min_year = min(years) if years else ''
            max_year = max(years) if years else ''
            writer.writerow([
                row['indicator'],
                row.get('unit', ''),
                year_count,
                min_year,
                max_year,
                ','.join(str(y) for y in sorted(years)),
            ])

    print(f'{output_path} に書き出しました。Excelで開いてフィルターをかけてみてください。')
    print('(year_countが少ない = データが薄い指標、というのが削除候補の目安の1つになります)')


if __name__ == '__main__':
    main()