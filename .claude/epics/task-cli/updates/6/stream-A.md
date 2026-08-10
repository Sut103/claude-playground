---
issue: 6
stream: ストア層
started: 2026-08-10T12:44:00Z
status: completed
---

## Scope

- `taskcli/store.py`（実装）
- `tests/test_store.py`（テスト）

他ストリームのファイル（`taskcli/render.py` / `taskcli/cli.py` とその専用テスト）には
一切触れていない。

## Progress

- `Document` を実装。行のリストを 1 本だけ持ち、各要素が `Task` か `str`（非タスク行の
  原文）である（AD-3）。`tasks` プロパティは出現順を保ってタスクだけを返す。更新系は
  `add` / `complete` / `remove` / `find` の 4 つで、いずれも非タスク行の位置を壊さない。
  直列化は `to_lines()` / `to_text()`。
- `load(path)` を実装。UTF-8 明示、CRLF は読み取り時に LF へ正規化。行分割は LF のみを
  区切りとして扱う（`splitlines()` は `\x0b` や `\u2028` でも切れてしまうため使わない）。
  - ファイルが存在しなければ例外を出さず空の `Document` を返し、ファイルも作らない。
  - タスク行に見えて解釈できない行は、`パス:行番号:` 付きの警告を **stderr** に出し、
    原文のまま保持して処理を継続する（FR-8）。stdout は汚さない。
  - 見出し・空行・段落・チェックボックスのない箇条書きは警告なしで原文保持。
  - ID 重複は警告のみで失敗しない（検証はストア層の責務外）。
- `save(path, document)` を実装（AD-4）。`tempfile.mkstemp(dir=<保存先と同じディレクトリ>)`
  → 書き込み → `flush()` → `os.fsync()` → `os.replace()`。`/tmp` も `shutil.move` も使わない。
  例外・中断時は一時ファイルを削除し、目的パスは従前の内容のまま残る。出力は LF 統一で
  末尾に改行 1 つ（空 `Document` は空ファイル）。既存ファイルのパーミッションを引き継ぐ。
  親ディレクトリが無い場合は `FileNotFoundError`（ディレクトリを暗黙に作らない）。
- `next_id(document)` を実装（AD-2）。最大 ID + 1、タスクが無ければ 1。状態ファイルなし。
- テスト 54 件を追加。全体で 146 件 passed（既存のパーサ 92 件を含め破壊なし）。

## Notes

- **設計上の限界を明示的にテストで固定した**: 最大 ID のタスクを削除すると、その ID が
  次の採番で再利用される（`test_deleting_the_highest_id_reuses_it`）。中間 ID の削除では
  再利用されない（FR-5、`test_deleting_a_middle_task_does_not_renumber_or_reuse`）。
  「ファイルから毎回導出する」という AD-2 の決定の帰結であり、単一利用者のローカル CLI
  という前提では許容する。
- **親ディレクトリが無い場合の挙動を「エラー」と決めた**。`TASK_CLI_FILE` の打ち間違いで
  思わぬ場所にディレクトリ階層が生えるのを避けるため。Issue #9（結線）でユーザ向けの
  メッセージに変換するのが望ましい。
- **警告対象の判定**は `^\s*[-*]\s*\[[^\]]*\]` という緩い正規表現で「タスク行のつもりの行」
  を拾う。パーサ本体より広く取ってあるので `- [?] x` のような打ち間違いも警告できる一方、
  見出しや通常の箇条書きは掛からず、警告で騒がしくならない。
- Issue #9 が使う公開 API は `load(path) -> Document` / `save(path, document) -> None` /
  `next_id(document) -> int` / `Document`（`tasks`・`find`・`add`・`complete`・`remove`）。
  `path` は `str` でも `os.PathLike` でも受ける。
