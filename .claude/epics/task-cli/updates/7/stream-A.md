---
issue: 7
stream: 表示層
started: 2026-08-10T12:47:03Z
status: completed
---

## Scope

書き込んだファイルは 2 つだけ。

- `taskcli/render.py` — 実装
- `tests/test_render.py` — 単体テスト（47 件）

`taskcli/parser.py` は読み取りのみ。`store.py` / `cli.py` / `__init__.py` / `pyproject.toml` /
`README.md` には触れていない（#6 / #8 が同一 worktree で並行作業中）。

## Progress

**公開 API**（Issue #9 が結線する際のシグネチャ）

```python
OVERDUE   = "OVERDUE"
DUE_TODAY = "DUE TODAY"

sort_tasks(tasks: list[Task]) -> list[Task]
due_state(task: Task, today: date | None = None) -> str | None
render_task(task: Task, today: date | None = None) -> str
render_list(tasks: list[Task], today: date | None = None) -> str
```

**並び替え（US-3）.** キーを 1 本のタプル
`(priority.sort_rank, due is None, due or date.min)` にまとめ、`sorted` を**一度だけ**呼ぶ。
`sort_rank` は parser 側で high=0 / mid=1 / low=2 と定義済みなので、昇順ソートがそのまま
優先度降順になる。`due is None` は False < True なので期限ありが先・なしが後。
`sorted` は安定なので、キーが完全に一致する 2 件は入力順を保つ。
複数回 `sort` を重ねると安定性の意味が変わるため、意図的に 1 回で済ませた。
入力リストは変更しない（新しいリストを返す）。

**期限状態（US-4 / AD-5）.** 既定値の解決は関数本体で `today = today or date.today()`。
シグネチャに `today: date = date.today()` と書くと **import 時に評価されて固定される**ため、
そこは踏まなかった。`OVERDUE` は `due < today` かつ `not done`、`DUE TODAY` は
`due == today` かつ `not done`。完了済みは期限を過ぎていても印を付けない。

**整形.** 1 タスク 1 行のプレーンテキスト。

```
[ ] #3 リファクタする !high @docs @refactor ~2026-08-20 << OVERDUE
[x] #1 README を書く !mid
```

ID・チェック状態・本文・優先度は常に出す（`Task.priority` は必ず値を持つ）。
タグと期限は持つものだけ。期限状態は `<<` で区切って行末に置く。
保存形式（`parser.format_line`）とは別物 — あちらは Markdown チェックリストとして
成立させる必要があるが、こちらは端末で読むための表示なので記号を減らしてある。

**`render_list([])` は空文字を返す。** 例外は投げない。「タスクなし」のメッセージ表示は
UX の判断なので、コマンド層（#8）の裁量として空けた。

**テスト.** 47 件。すべて `today=date(2026, 8, 20)` のような固定日付を渡しており、
実行日が変わっても結果は変化しない。境界（前日 / 当日 / 翌日）、完了済みの除外、
安定ソート、期限なしが「全体の末尾」ではなく「同一優先度グループの末尾」に来ること、
ANSI エスケープ非混入を個別に確認している。
既定値が呼び出し時に解決されることは、実行日そのものに依存しない形（1970-01-01 は必ず過去、
9999-12-31 は必ず未来）で検証した。

`python3 -m pytest -q` はリポジトリ全体で **146 passed / 0 failed**（うち表示層 47 件）。
既存のパーサ層テストは壊していない。

## Notes

- フィルタリング（`--all` / `--priority` / `--tag` / `--overdue`）は実装していない。
  #8 の責務である。`--overdue` は `due_state(task) == render.OVERDUE` で判定できるよう、
  `due_state` を公開関数として切り出してある。
- ファイル I/O は一切なし。import しているのは `datetime.date` と `.parser.Task` のみ（NFR-1）。
- カラー出力・TTY 判定は PRD の Out of Scope。`sys.stdout.isatty()` は参照していない。
- git: 自分の 3 ファイルのみを明示パスで `git add`。`git add -A` は使っていない。
  コミット時点で `git status` には #6 / #8 の作業中ファイルが見えていたが、巻き込んでいない。
