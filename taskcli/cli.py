"""コマンド層: argparse のサブコマンド定義と終了コードの決定（Issue #8）。

この層が扱うのは「引数をどう解釈し、どの終了コードを返すか」までである。
ファイルの読み書き（ストア層）と一覧の整形（表示層）は、モジュール末端に置いた
**シーム**（``_load`` / ``_save`` / ``_tasks`` / ``_next_id`` / ``_append`` /
``_remove`` / ``_render``）越しに呼ぶ。

シームを挟む理由は 2 つある。第一に、``store.py`` と ``render.py`` は本タスクと
並行して実装されており、ここから直接 import すると未完成のモジュールに結合して
しまう。第二に、シームを差し替えれば引数解析・分岐・終了コードだけを単体で
検証できる。Issue #9 がシームの中身を実装呼び出しへ置き換える — そのとき
**シグネチャは変えない**ことが本タスクの契約である。

終了コードの規約（FR-9）::

    0  成功（0 件ヒットの list、完了済みへの done も成功である）
    1  利用者起因のエラー（存在しない ID）
    2  argparse が弾く入力（不正な choices、非整数の ID、不正な日付、未知の
       サブコマンド、サブコマンドの省略）

コマンド関数は ``sys.exit`` を呼ばず int を返す。終了処理は ``main()`` に集約する。
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Sequence

from taskcli import render, store
from taskcli.parser import DEFAULT_PRIORITY, Priority, Task, parse_due

__all__ = ["build_parser", "main", "resolve_path", "cmd_add", "cmd_list", "cmd_done", "cmd_rm"]

#: 環境変数が未設定のときに使うタスクファイル（FR-6）。
DEFAULT_TASK_FILE = "TASKS.md"

#: パスを差し替えるための環境変数名（FR-6）。
TASK_FILE_ENV = "TASK_CLI_FILE"

_PRIORITY_CHOICES = [priority.value for priority in Priority]


# --------------------------------------------------------------------------- #
# パス解決（FR-6）
# --------------------------------------------------------------------------- #


def resolve_path() -> Path:
    """タスクファイルのパスを決める。

    ``TASK_CLI_FILE`` が設定されていればそれを、さもなくば ``./TASKS.md`` を返す。
    空文字は「未設定」と同じに扱う — 空のパスで書き込みを試みても失敗するだけで、
    利用者の意図としては既定に戻したいはずである。
    """
    return Path(os.environ.get(TASK_FILE_ENV) or DEFAULT_TASK_FILE)


# --------------------------------------------------------------------------- #
# argparse の型（検証は「書き込みより前」に済ませる）
# --------------------------------------------------------------------------- #


def _due_arg(value: str) -> date:
    """``--due`` の値を ``date`` にする。不正なら argparse に弾かせる。

    検証を ``type=`` に置くのが US-4 の要（かなめ）である。argparse は解析段階で
    非ゼロ終了するため、コマンド関数へ到達しない = ファイルに触れようがない。
    """
    parsed = parse_due(value)
    if parsed is None:
        raise argparse.ArgumentTypeError(f"不正な日付です: {value!r}（YYYY-MM-DD 形式で指定してください）")
    return parsed


# --------------------------------------------------------------------------- #
# パーサ
# --------------------------------------------------------------------------- #


def build_parser() -> argparse.ArgumentParser:
    """``add`` / ``list`` / ``done`` / ``rm`` を持つパーサを返す。"""
    parser = argparse.ArgumentParser(
        prog="taskcli",
        description="Markdown ファイルを唯一のデータストアとするタスク管理 CLI。",
    )
    # required=True にはしない。サブコマンド省略時は main() が
    # ヘルプ全文を stderr に出して終了する（argparse 既定の 1 行 usage より親切）。
    subparsers = parser.add_subparsers(dest="command", metavar="{add,list,done,rm}")

    add = subparsers.add_parser("add", help="タスクを追加する")
    add.add_argument("text", help="タスクの本文")
    add.add_argument(
        "--priority",
        choices=_PRIORITY_CHOICES,
        default=DEFAULT_PRIORITY.value,
        help=f"優先度（既定: {DEFAULT_PRIORITY.value}）",
    )
    add.add_argument("--tag", action="append", metavar="TAG", help="タグ（繰り返し指定可）")
    add.add_argument("--due", type=_due_arg, metavar="YYYY-MM-DD", help="期限")
    add.set_defaults(func=cmd_add)

    listing = subparsers.add_parser("list", help="タスクを一覧する")
    listing.add_argument("--all", action="store_true", help="完了済みも含める")
    listing.add_argument("--priority", choices=_PRIORITY_CHOICES, help="優先度で絞り込む")
    listing.add_argument("--tag", action="append", metavar="TAG", help="タグで絞り込む（繰り返し指定可）")
    listing.add_argument("--overdue", action="store_true", help="期限切れのみ")
    listing.set_defaults(func=cmd_list)

    done = subparsers.add_parser("done", help="タスクを完了にする")
    done.add_argument("id", type=int, help="タスク ID")
    done.set_defaults(func=cmd_done)

    remove = subparsers.add_parser("rm", help="タスクを削除する")
    remove.add_argument("id", type=int, help="タスク ID")
    remove.set_defaults(func=cmd_rm)

    return parser


# --------------------------------------------------------------------------- #
# コマンド
# --------------------------------------------------------------------------- #


def cmd_add(args: argparse.Namespace) -> int:
    """タスクを 1 件追加する（FR-1、US-1）。"""
    path = resolve_path()
    doc = _load(path)
    task = Task(
        id=_next_id(doc),
        text=args.text,
        done=False,
        # argparse が choices で保証しているので Priority() は必ず成功する。
        priority=Priority(args.priority),
        # action="append" の既定は None。ここで正規化し、下流へ漏らさない。
        tags=list(args.tag or []),
        due=args.due,
    )
    _append(doc, task)
    _save(path, doc)
    print(f"追加しました: #{task.id} {task.text}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """条件に合うタスクを一覧する（FR-2、US-3）。

    フィルタは AND で結合する。0 件はエラーではないので常に 0 を返す。
    """
    path = resolve_path()
    doc = _load(path)
    tags = list(args.tag or [])
    today = date.today()
    selected = [
        task
        for task in _tasks(doc)
        if _matches(
            task,
            show_all=args.all,
            priority=args.priority,
            tags=tags,
            overdue=args.overdue,
            today=today,
        )
    ]
    output = _render(selected)
    if output:
        print(output)
    return 0


def _matches(
    task: Task,
    *,
    show_all: bool,
    priority: str | None,
    tags: Sequence[str],
    overdue: bool,
    today: date,
) -> bool:
    """1 件のタスクがフィルタ条件をすべて満たすか。

    ``today`` を引数で受けるのは AD-5 と同じ理由である。判定を日付に依存させない。
    """
    if not show_all and task.done:
        return False
    if priority is not None and task.priority.value != priority:
        return False
    # --tag を複数指定した場合も AND。「両方のタグを持つタスク」が直感に合う。
    if tags and not all(tag in task.tags for tag in tags):
        return False
    # 期限切れの定義は表示層に一本化する（US-4）。完了済みは期限を過ぎていても
    # 期限切れとして扱わない、という判断が render.due_state 側にあるため、ここで
    # 独自に task.due < today と書くと --all と併用したときに定義がずれる。
    if overdue and render.due_state(task, today) != render.OVERDUE:
        return False
    return True


def cmd_done(args: argparse.Namespace) -> int:
    """タスクを完了にする（FR-3、US-5）。行は削除しない。"""
    path = resolve_path()
    doc = _load(path)
    task = _find(_tasks(doc), args.id)
    if task is None:
        print(f"エラー: タスク #{args.id} は存在しません", file=sys.stderr)
        return 1
    if task.done:
        # 冪等。すでに目的の状態なので書き込みもしない（ファイルは 1 バイトも変わらない）。
        print(f"警告: タスク #{args.id} はすでに完了しています", file=sys.stderr)
        return 0
    task.done = True
    _save(path, doc)
    print(f"完了しました: #{task.id} {task.text}")
    return 0


def cmd_rm(args: argparse.Namespace) -> int:
    """タスクを行ごと削除する（FR-4、US-5）。"""
    path = resolve_path()
    doc = _load(path)
    if not _remove(doc, args.id):
        print(f"エラー: タスク #{args.id} は存在しません", file=sys.stderr)
        return 1
    _save(path, doc)
    print(f"削除しました: #{args.id}")
    return 0


def _find(tasks: Iterable[Task], task_id: int) -> Task | None:
    for task in tasks:
        if task.id == task_id:
            return task
    return None


# --------------------------------------------------------------------------- #
# シーム — Issue #8 が置いた間接層を、Issue #9 で実装へ結線した。
#
# シグネチャは #8 のテストが monkeypatch で差し替える契約なので変更していない。
# 中身だけが taskcli.store / taskcli.render の呼び出しに置き換わっている。
# --------------------------------------------------------------------------- #


def _load(path: Path) -> Any:
    """ドキュメントを読み込む（``store.load``）。

    ファイルが存在しない場合、``store.load`` は空の ``Document`` を返す。
    ここで例外にしないことが US-1 の「初期化コマンドを別途叩かなくてよい」を支えている。
    """
    return store.load(path)


def _save(path: Path, doc: Any) -> None:
    """ドキュメントを書き戻す（``store.save``、AD-4 の原子的置換）。"""
    store.save(path, doc)


def _tasks(doc: Any) -> list[Task]:
    """ドキュメント内のタスクを出現順に返す（``Document.tasks``）。

    返るのは ``Document`` が保持しているのと同一の ``Task`` オブジェクトである。
    ``cmd_done`` はこれを直接書き換えてから ``_save`` するため、その同一性に依存する。
    """
    return doc.tasks


def _next_id(doc: Any) -> int:
    """次に割り当てる ID を返す（``store.next_id``、AD-2）。"""
    return store.next_id(doc)


def _append(doc: Any, task: Task) -> None:
    """ドキュメント末尾にタスクを追加する（``Document.add``）。"""
    doc.add(task)


def _remove(doc: Any, task_id: int) -> bool:
    """ID に一致するタスクを取り除く。取り除けたら ``True``（``Document.remove``）。"""
    return doc.remove(task_id) is not None


def _render(tasks: Sequence[Task]) -> str:
    """一覧の表示文字列を組み立てる（``render.render_list``）。

    並び替えは ``render_list`` の内部で ``sort_tasks`` により行われる。
    """
    return render.render_list(list(tasks))


# --------------------------------------------------------------------------- #
# エントリポイント
# --------------------------------------------------------------------------- #


def main(argv: Sequence[str] | None = None) -> None:
    """引数を解析し、コマンド関数の戻り値を終了コードにする（FR-9）。"""
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "func", None)
    if handler is None:
        # サブコマンドの省略。無言で成功させず、ヘルプを stderr に出して非ゼロ終了する。
        parser.print_help(sys.stderr)
        sys.exit(2)
    sys.exit(handler(args))
