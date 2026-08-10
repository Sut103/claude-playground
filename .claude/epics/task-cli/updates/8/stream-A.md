---
issue: 8
stream: コマンド層
started: 2026-08-10T12:42:31Z
status: completed
---

## Scope

触ったファイルは 2 つだけである。

- `taskcli/cli.py` — argparse の骨格、4 サブコマンド、パス解決、シーム
- `tests/test_cli.py` — 上記の単体テスト（53 件）

`taskcli/store.py`（Issue #6）と `taskcli/render.py`（Issue #7）は並行実装中のため、
読みも書きもしていない。`parser.py` / `__init__.py` / `__main__.py` / `pyproject.toml` /
`README.md` も未変更である。

## Progress

**パーサの骨格.** `build_parser() -> argparse.ArgumentParser` が `add` / `list` /
`done` / `rm` を持つ。サブコマンド省略時は `add_subparsers(required=True)` に頼らず、
`main()` がヘルプ全文を stderr に出して 2 で終了する（argparse 既定の 1 行 usage より
利用者に親切であり、「無言で成功しない」という受け入れ基準も満たす）。

**終了コード（FR-9）.** `cmd_add` / `cmd_list` / `cmd_done` / `cmd_rm` はいずれも int を
`return` するだけで `sys.exit` を呼ばない。終了処理は `main()` の 1 箇所に集約した。

**`--due` の検証位置（US-4）.** argparse の `type=_due_arg` に置いた。解析段階で
`argparse.ArgumentTypeError` を投げるため、不正な日付はコマンド関数に到達しない =
ファイルに触れる経路へ入りようがない。テストでは「シームの `_load` すら呼ばれない」
ことをアサートして、この構造を固定した。

**`--tag` の正規化.** `action="append"` の既定は `None`。`add` / `list` の入口で
`list(args.tag or [])` に正規化し、`None` を下流へ漏らさない。複数指定は AND で
結合する（`--tag docs --tag code` は両方を持つタスクのみ）。

**冪等な `done`（US-5）.** すでに完了しているタスクへの `done` は stderr に警告を出して
0 を返す。**このとき `_save` を呼ばない** — 状態が変わらないのだから書き込む理由がなく、
Issue #9 の「ファイルがバイト単位で変化しない」アサートもこれで自然に通る。

**パス解決（FR-6）.** `resolve_path() -> Path` に切り出した。`TASK_CLI_FILE` が設定されて
いればそれを、未設定なら `./TASKS.md` を返す。空文字は未設定と同じ扱いにした。
両分岐 + 空文字の 3 ケースをテストしている。

**テスト.** 53 件。`python3 -m pytest -q tests/test_cli.py tests/test_parser.py
tests/test_smoke.py` で 98 passed（既存のパーサテストは無傷）。並行作業中の
`tests/test_store.py` を含むリポジトリ全体でも 199 passed。

## Notes

**シームのシグネチャ（Issue #9 への契約）.** `cli.py` のモジュールレベルに次の 7 関数を
置き、コマンド関数はこれらだけを経由する。#9 は中身を差し替え、**シグネチャは変えない**。

| シーム | 置き換え先（想定） |
| --- | --- |
| `_load(path: Path) -> Any` | `store.load(path)` |
| `_save(path: Path, doc: Any) -> None` | `store.save(path, doc)` |
| `_tasks(doc: Any) -> list[Task]` | `doc.tasks` |
| `_next_id(doc: Any) -> int` | `store.next_id(doc)` |
| `_append(doc: Any, task: Task) -> None` | ドキュメント末尾への追加 |
| `_remove(doc: Any, task_id: int) -> bool` | ドキュメントからの行削除（成否を返す） |
| `_render(tasks: Sequence[Task]) -> str` | `render.render_list(tasks)` |

現段階のドキュメント表現は `list[Task]` である。`_tasks` / `_next_id` / `_append` /
`_remove` はその上の最小実装、`_load` は空ドキュメント、`_save` は no-op になっている。
#9 が `store.Document` に置き換えても、コマンド関数側は 1 行も変わらないはずである。

**`_remove` が bool を返す理由.** `done` は `_tasks` から対象を探して `task.done = True` と
その場で書き換えられる（`Task` は可変なので、ドキュメントが保持している同じオブジェクトを
触ることになる）が、`rm` はドキュメントの構造そのものを変える必要がある。「見つからなかった」
を例外ではなく戻り値で表すことで、コマンド層が終了コード 1 へ素直に落とせる。

**テストできることの範囲.** シームを差し替えている以上、ここで検証しているのは引数解析・
分岐・終了コード・stdout/stderr の出し分けまでである。実ファイルがどう書き換わるかは
#9 の E2E が受け持つ。これは設計どおりの状態であり、本タスク単体では E2E は完成しない。

**git.** `git add` は自分のファイル 3 本をパス指定で明示した。`index.lock` の競合は
発生せず、リトライ 0 回でコミットできた。
