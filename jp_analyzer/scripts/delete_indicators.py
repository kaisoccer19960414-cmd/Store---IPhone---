"""
指定したindicator(指標)のデータをprefecture_stats(と、参照が無くなったindicators本体)から削除する。

使い方:
  # まず対象を確認するだけ(--dry-run)
  python delete_indicators.py --indicator "きまって支給する現金給与額（女）（～2019）" --dry-run

  # 部分一致(ILIKEパターン、%を自分で入れる)で一気に対象を絞る
  python delete_indicators.py --pattern "%（第11回改定産業分類）%" --dry-run

  # Excelでフィルターした指標名をテキストファイルに貼り付けて、まとめて指定する
  # (1行に1つの指標名。indicators_list.csvのA列をコピペしてメモ帳等に保存すればOK)
  python delete_indicators.py --indicator-file to_delete.txt --dry-run

  # 複数指定・混在もOK
  python delete_indicators.py --indicator "電話加入数" --pattern "％所有数量%" --dry-run

  # 確認できたら --dry-run を外して本番削除
  python delete_indicators.py --indicator-file to_delete.txt
"""
import argparse
import stats_db


def read_indicator_file(path):
    with open(path, encoding='utf-8-sig') as f:
        return [line.strip() for line in f if line.strip()]


def main():
    parser = argparse.ArgumentParser(description='指定したindicatorのデータを削除する')
    parser.add_argument('--indicator', action='append', help='完全一致で削除したい指標名。複数指定可')
    parser.add_argument('--pattern', action='append',
                         help='部分一致(ILIKE)で削除したい指標名パターン。%%を含めて指定する。複数指定可')
    parser.add_argument('--indicator-file',
                         help='1行に1つの指標名を書いたテキストファイル。Excelでフィルターした列を'
                              'そのまま貼り付けて使う想定')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--yes', action='store_true', help='確認プロンプトをスキップする')
    args = parser.parse_args()

    indicator_names = list(args.indicator or [])
    if args.indicator_file:
        indicator_names.extend(read_indicator_file(args.indicator_file))

    if not indicator_names and not args.pattern:
        raise SystemExit('--indicator / --indicator-file / --pattern のいずれかを指定してください')

    matches = stats_db.find_indicators(exact=indicator_names, patterns=args.pattern)
    if not matches:
        print('該当するindicatorが見つかりませんでした。')
        return

    print(f'=== 該当したindicator: {len(matches)}件 ===')
    for m in matches:
        print(f"  {m['id']}: {m['name']!r}")

    if indicator_names:
        not_found = set(indicator_names) - {m['name'] for m in matches}
        if not_found:
            print(f'\n警告: ファイル/指定の中でDBに見つからなかった名前が {len(not_found)} 件あります(表記ゆれ等の可能性):')
            for name in list(not_found)[:10]:
                print(f'  {name!r}')

    if not args.dry_run and not args.yes:
        answer = input(f'\n上記 {len(matches)} 件のindicatorに紐づくデータを削除します。よろしいですか? (yes/no): ')
        if answer.strip().lower() != 'yes':
            print('中止しました。')
            return

    total = stats_db.delete_indicators([m['id'] for m in matches], dry_run=args.dry_run)

    if args.dry_run:
        print(f'\n{total} 件が削除対象です(--dry-run のため実際には削除していません)')
    else:
        print(f'\n合計 {total} 件を削除しました')


if __name__ == '__main__':
    main()