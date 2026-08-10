---
issue: 10
stream: 受け入れ確認
started: 2026-08-10T12:58:00Z
status: completed
---

# 受け入れ確認レポート — Epic task-cli

Epic の **Success Criteria (Technical)** と PRD の **US-1〜US-5** を 1 項目ずつ検証した。
本タスクの規定どおり、**プロダクションコードの修正は行っていない**（検証のみ）。

---

## 1. テスト全件パス

```
$ python3 -m pytest -q
215 passed in 2.64s
$ echo $?
0
```

**判定: 合格。** 失敗 0 件、エラー 0 件、skip 0 件。収集件数 215。

内訳: `test_parser.py` 45 / `test_store.py` 54 / `test_render.py` 47 / `test_cli.py` 53 /
`test_e2e.py` 16。

---

## 2. 受け入れ基準とテストの対応表

`ファイル::関数名` で対応付ける。多対多を許す。

### US-1: 開発者がターミナルを離れずにタスクを記録する

| 受け入れ基準 | 対応テスト | 判定 |
| --- | --- | --- |
| `add` でタスクが追加され ID が標準出力に出る | `test_cli.py::test_assigned_id_is_printed_and_exit_zero`、`test_e2e.py::test_full_lifecycle` | 合格 |
| オプション省略でも成功し、優先度は既定 `mid` | `test_cli.py::test_default_priority_is_mid`、`test_cli.py::test_tag_defaults_to_empty_list_not_none` | 合格 |
| 追加後もファイルが妥当なチェックリストのまま | `test_e2e.py::test_lines_are_gfm_checklist_items`、`test_e2e.py::test_file_ends_with_exactly_one_newline` | 合格 |
| ファイルが無ければ自動生成される | `test_store.py::test_creates_file_when_absent`、`test_e2e.py::test_full_lifecycle`（`tasks.exists()` を assert） | 合格 |

### US-2: AI エージェントが人間の作ったタスクを読む

| 受け入れ基準 | 対応テスト | 判定 |
| --- | --- | --- |
| 有効な Markdown であり GitHub 上でチェックリストとして表示される | `test_e2e.py::test_lines_are_gfm_checklist_items` | **部分的**（下記参照） |
| メタデータが可読性を壊さない | `test_e2e.py::test_lines_are_gfm_checklist_items` | **部分的**（下記参照） |
| 手編集したファイルを CLI が引き続き読める | `test_e2e.py::test_list_still_reads_every_task_after_hand_edit` | 合格 |
| 壊れた行は警告のみで、残りを処理する | `test_e2e.py::test_broken_line_warns_but_does_not_abort`、`test_store.py::test_unparseable_task_line_is_kept_verbatim_and_processing_continues`、`test_store.py::test_warning_goes_to_stderr_not_stdout` | 合格 |

**部分的と判定した理由。** 自動テストが検証しているのは「行が GFM チェックリストの
書式に一致すること」までである。**GitHub 上で実際にチェックボックスとして
レンダリングされることは、自動テストでは確認できない。** 「可読性を壊さない」も
本質的に人間の判断であり、テストにできる形をしていない。

この 2 項目は §4 の目視確認で補った。**判定を「合格」に繰り上げず、
自動テストの守備範囲外であることを記録として残す。**

### US-3: 今やるべきタスクだけを見る

| 受け入れ基準 | 対応テスト | 判定 |
| --- | --- | --- |
| `list` は未完了のみ | `test_cli.py::test_default_hides_done_tasks`、`test_e2e.py::test_full_lifecycle` | 合格 |
| `list --all` は完了済みも含む | `test_cli.py::test_all_includes_done_tasks`、`test_e2e.py::test_full_lifecycle` | 合格 |
| `list --priority high` | `test_cli.py::test_priority_filter` | 合格 |
| `list --tag docs` | `test_cli.py::test_tag_filter` | 合格 |
| 複数フィルタは AND | `test_cli.py::test_filters_combine_with_and`、`test_cli.py::test_repeated_tags_combine_with_and` | 合格 |
| 優先度降順 → 期限昇順 → 期限なしが末尾 | `test_render.py::test_priority_descending`、`test_render.py::test_due_ascending_within_same_priority`、`test_render.py::test_tasks_without_due_go_last_within_their_priority_group`、`test_render.py::test_full_scenario_matches_us3_and_us4` | 合格 |

### US-4: 期限切れを見落とさない

| 受け入れ基準 | 対応テスト | 判定 |
| --- | --- | --- |
| `--due 2026-08-20` の形式で設定できる | `test_cli.py::test_due_is_parsed_into_date` | 合格 |
| 期限切れかつ未完了は `OVERDUE` | `test_render.py::test_overdue_when_due_before_today_and_not_done`、`test_render.py::test_none_when_done_even_if_overdue` | 合格 |
| 本日が期限なら `DUE TODAY` | `test_render.py::test_due_today_when_due_equals_today`、`test_render.py::test_boundary_yesterday_today_tomorrow` | 合格 |
| 不正な日付はその場でエラー、ファイル不変 | `test_cli.py::test_invalid_due_is_rejected_before_any_write`、`test_e2e.py::test_invalid_due_rejected_without_touching_file`（`read_bytes()` 比較） | 合格 |
| `list --overdue` | `test_cli.py::test_overdue_filter` | 合格 |

### US-5: 完了と削除を取り違えない

| 受け入れ基準 | 対応テスト | 判定 |
| --- | --- | --- |
| `done` はチェックを付け、行は消さない | `test_cli.py::test_does_not_remove_the_task`、`test_store.py::test_complete_flips_checkbox_in_place`、`test_e2e.py::test_full_lifecycle` | 合格 |
| `rm` は行ごと削除する | `test_cli.py::test_removes_task_and_saves`、`test_store.py::test_remove_deletes_only_that_line` | 合格 |
| 存在しない ID は非ゼロ終了、ファイル不変 | `test_cli.py::test_missing_id_exits_nonzero_without_writing`、`test_e2e.py::test_done_on_missing_id`、`test_e2e.py::test_rm_on_missing_id`（いずれも `read_bytes()` 比較） | 合格 |
| 完了済みへの `done` は警告のみでエラーにしない | `test_cli.py::test_already_done_warns_to_stderr_and_exits_zero`、`test_e2e.py::test_done_is_idempotent` | 合格 |

**未カバーの受け入れ基準: 0 件。** US-2 の 2 項目のみ、自動テストの守備範囲外として
「部分的」と記録した（機能上の欠落ではない）。

---

## 3. 対応付けの妥当性

表に挙げたテストの中身を読み、名前だけでなく実際にその基準を検証しているか確認した。
特に注意して見た点を挙げる。

- **「ファイルを変更しない」系** — 行数や部分文字列ではなく `read_bytes()` の比較で
  検証されていることを確認した。末尾改行や空白の差異を見逃さない。
- **日付依存** — `test_render.py` のテストはすべて固定日付（`today=date(2026,8,20)` 等）を
  引数で渡している。`test_render.py::test_today_is_a_parameter_not_a_frozen_default` は、
  既定値が import 時に凍結されていないことを直接検証している（AD-5 の要点）。
- **冪等性** — `test_done_is_idempotent` は終了コード 0 だけでなく、stderr に警告が出ること、
  stdout が空であること、**ファイルが 1 バイトも変わらないこと**まで確認している。

名前は合っているが実質を検証していないテストは見つからなかった。

---

## 4. 実ターミナルでの通し実行

`mktemp -d` のクリーンなディレクトリで、`TASK_CLI_FILE` を設定してシェルから直接実行した。

```
$ python3 -m taskcli add リファクタする --priority high --tag refactor --due 2026-08-01
追加しました: #1 リファクタする                                    exit=0
$ python3 -m taskcli add README を書く --tag docs
追加しました: #2 README を書く                                     exit=0
$ python3 -m taskcli add 後回しでよい --priority low --due 2026-12-31
追加しました: #3 後回しでよい                                       exit=0
$ python3 -m taskcli list
[ ] #1 リファクタする !high @refactor ~2026-08-01 << OVERDUE
[ ] #2 README を書く !mid @docs
[ ] #3 後回しでよい !low ~2026-12-31                               exit=0
$ python3 -m taskcli done 2
完了しました: #2 README を書く                                      exit=0
$ python3 -m taskcli list
[ ] #1 リファクタする !high @refactor ~2026-08-01 << OVERDUE
[ ] #3 後回しでよい !low ~2026-12-31                               exit=0
$ python3 -m taskcli list --all
[ ] #1 リファクタする !high @refactor ~2026-08-01 << OVERDUE
[x] #2 README を書く !mid @docs
[ ] #3 後回しでよい !low ~2026-12-31                               exit=0
$ python3 -m taskcli list --overdue
[ ] #1 リファクタする !high @refactor ~2026-08-01 << OVERDUE       exit=0
$ python3 -m taskcli rm 3
削除しました: #3                                                    exit=0
```

**判定: 合格。** 全ステップで `$?` が 0。表示順は優先度降順（high → mid → low）、
`OVERDUE` は期限切れかつ未完了のタスクにのみ付き、`done` 後は既定の `list` から消えて
`--all` でのみ現れた。

### 生成された Markdown の目視確認

```markdown
- [ ] リファクタする `#1` `!high` `@refactor` `~2026-08-01`
- [x] README を書く `#2` `!mid` `@docs`
```

**判定: 合格。** `- [ ]` / `- [x]` の GFM チェックリスト行として妥当。メタデータは
バッククォートで囲まれてコード片として視覚的に分離され、本文の可読性を損なっていない。
人間がこの行を直接書き換えることに無理はない（US-2、NFR-5）。

---

## 5. 手編集との往復（実地）

上のファイルを手で書き換えた。見出しの挿入、自由記述行の挿入、タスク行の並べ替えの 3 種を含む。

```markdown
## 今週

- [x] README を書く `#2` `!mid` `@docs`

メモ: 期限は要相談

- [ ] リファクタする `#1` `!high` `@refactor` `~2026-08-01`
```

```
$ python3 -m taskcli list --all
[ ] #1 リファクタする !high @refactor ~2026-08-01 << OVERDUE
[x] #2 README を書く !mid @docs                                    exit=0
$ python3 -m taskcli add 手編集のあとに追加
追加しました: #3 手編集のあとに追加                                  exit=0
$ python3 -m taskcli done 1
完了しました: #1 リファクタする                                      exit=0
```

操作後のファイル:

```markdown
## 今週

- [x] README を書く `#2` `!mid` `@docs`

メモ: 期限は要相談

- [x] リファクタする `#1` `!high` `@refactor` `~2026-08-01`
- [ ] 手編集のあとに追加 `#3` `!mid`
```

**判定: 合格。** 手書きの見出し `## 今週`、空行、メモ行 `メモ: 期限は要相談` が
**すべて元の位置のまま残った**。並べ替えた順序も保存され、新規タスクは末尾に追加された。
`done 1` は該当行のチェックボックスだけを書き換え、他の行に触れていない（AD-3）。

---

## 6. 標準ライブラリのみであることの機械的確認

`ast` で `taskcli/` 配下の import 文を抽出し、`sys.stdlib_module_names` および内部
モジュールとの集合演算で判定した（grep の目視ではなく）。

```
taskcli/ が import しているトップレベルモジュール:
  __future__, argparse, dataclasses, datetime, enum, os, pathlib, re, sys,
  taskcli, tempfile, typing

標準ライブラリでも taskcli 内部でもないもの: 0 件
```

`pyproject.toml` の `dependencies = []` も併せて確認した。

**判定: 合格（NFR-1）。**

---

## 7. 往復テストの存在確認

- `test_parser.py::test_parse_of_format_returns_equal_task` — 7 ケースを parametrize。
  メタデータ全部入り / タグ 0 個 / タグ 3 個 / 期限なし / `done=True` / 各優先度 /
  日本語本文 / 記号混じり本文を含む
- `test_parser.py::test_format_of_parse_returns_canonical_input` — 逆方向
- `test_parser.py::test_tag_order_survives_round_trip` — 辞書順と異なる `["z","a","m"]`

**判定: 合格。** 優先度・タグ・期限を持つケースと持たないケースの両方をカバーしている。

---

## 8. NFR-4（性能）— 対応テストが無かったため実測した

PRD の NFR-4「タスク 1000 件のファイルに対し `list` が 1 秒以内」に対応する自動テストが
存在しなかった。**Epic の Success Criteria には含まれていない項目だが、未検証のまま
「合格」と report するのは誤りになるため、実測で埋めた。**

1000 件のタスクファイルを生成して計測（Python プロセスの起動時間を含む）:

```
run1: 0.069 秒
run2: 0.069 秒
run3: 0.069 秒
```

**判定: 合格（要求の約 1/14）。** ただし**回帰を防ぐ自動テストは存在しない。**
性能要求を継続的に守るなら、テストとして追加すべきである。**本タスクの範囲は検証で
あり修正ではないため、ここでは追加していない。**

---

## 9. Epic Success Criteria (Technical) の判定一覧

| # | 項目 | 判定 | 根拠 |
| --- | --- | --- | --- |
| 1 | `python -m pytest` が失敗 0 件で終了する | ✅ 合格 | §1 |
| 2 | US-1〜US-5 の全 Acceptance Criteria に対応するテストが存在する | ✅ 合格 | §2（未カバー 0 件。US-2 の 2 項目は自動テストの守備範囲外として「部分的」、§4 の目視で補完） |
| 3 | クリーンな一時ディレクトリでの通し実行が期待どおり | ✅ 合格 | §4 |
| 4 | `parse_line` / `format_line` の往復で情報が保存される | ✅ 合格 | §7 |
| 5 | 手編集で追加した非タスク行が CLI 操作後も残る | ✅ 合格 | §5 |
| 6 | 実行時 import に標準ライブラリ以外が現れない | ✅ 合格 | §6 |

**未判定の項目: 0 件。**

---

## 10. 未達項目と差し戻し

**プロダクションコードの未達: 0 件。** 差し戻すタスクはない。

記録として残す事項が 2 件ある。いずれも Epic の Success Criteria の未達ではないため、
本タスクでは修正しない。

| # | 内容 | 提案 |
| --- | --- | --- |
| 1 | NFR-4（1000 件 1 秒以内）に対応する自動テストが無い。実測では合格だが回帰を検出できない | 性能テストを 1 件追加する |
| 2 | US-2 の「GitHub 上でチェックリストとしてレンダリングされる」は自動検証できていない | 実際に GitHub 上へ貼って目視確認する運用手順を決める |
