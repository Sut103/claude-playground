"""表示層: 並び替え、期限状態の判定、整形（Issue #7 で実装）。

この層の責務は 3 つに限定される。

1. **並び替え** — US-3 の表示順（優先度降順 → 期限昇順 → 期限なしが末尾）
2. **期限状態の判定** — US-4 の ``OVERDUE`` / ``DUE TODAY``
3. **整形** — 1 タスクを 1 行のプレーンテキストへ変換する

フィルタリング（``--all`` / ``--priority`` / ``--tag`` / ``--overdue``）はコマンド層
（Issue #8）の責務である。ただし ``--overdue`` がフィルタ条件として使えるよう、
:func:`due_state` は単体で呼び出せる公開関数として切り出してある。

ファイル I/O は行わない。import するのは ``parser`` の ``Task`` 系だけで、
``store`` にも ``cli`` にも依存しない。

出力はプレーンテキストのみ。ANSI エスケープシーケンスは一切含めず、
``sys.stdout.isatty()`` も参照しない — カラー出力と TTY 判定は PRD の Out of Scope である。

表示行の書式（1 タスク 1 行）::

    [ ] #3 リファクタする !high @docs @refactor ~2026-08-20 << OVERDUE
    [x] #1 README を書く !mid

保存形式（``parser.format_line``）とは別物である点に注意。保存形式は Markdown の
チェックリストとして成立する必要があるため ``- [ ] `` で始まりメタデータをバッククォートで
囲むが、こちらは端末で読むための表示であり、記号の数を抑えてある。
"""

from __future__ import annotations

from datetime import date

from .parser import Task

__all__ = ["OVERDUE", "DUE_TODAY", "sort_tasks", "due_state", "render_task", "render_list"]

#: 期限が本日より前で、かつ未完了のタスクに付く印（US-4）。
OVERDUE = "OVERDUE"

#: 期限が本日で、かつ未完了のタスクに付く印（US-4）。
DUE_TODAY = "DUE TODAY"

#: 期限状態を行の他の要素から視覚的に切り離すための区切り。
_STATE_SEPARATOR = "<<"


def _sort_key(task: Task) -> tuple[int, bool, date]:
    """``sorted`` に渡すキー。昇順に並べるだけで US-3 の表示順になる向きに取る。

    - ``priority.sort_rank`` は high=0 / mid=1 / low=2 なので、昇順で high が先頭に来る
    - ``task.due is None`` は False < True なので、期限ありが先、なしが後になる
    - 期限なしの ``date.min`` は同グループ内の比較には影響しない（第 2 要素で既に分離済み）
    """
    return (
        task.priority.sort_rank,
        task.due is None,
        task.due if task.due is not None else date.min,
    )


def sort_tasks(tasks: list[Task]) -> list[Task]:
    """US-3 の表示順に並べ替えた**新しいリスト**を返す。入力は変更しない。

    優先度降順（high → mid → low）→ 同一優先度内では期限昇順 → 期限なしは同グループの末尾。

    キーを 1 本のタプルにまとめて ``sorted`` を**一度だけ**呼ぶ。Python の ``sorted`` は
    安定なので、優先度も期限も等しい 2 件は入力順を保つ。複数回 ``sort`` を重ねると
    この安定性の意味が変わるため、意図的に 1 回で済ませている。
    """
    return sorted(tasks, key=_sort_key)


def due_state(task: Task, today: date | None = None) -> str | None:
    """タスクの期限状態を返す。``OVERDUE`` / ``DUE TODAY`` / ``None`` のいずれか。

    ``today`` は**引数として受け取る**。既定値の解決は ``today or date.today()`` の形で
    この関数の本体で行う — シグネチャ側に ``today: date = date.today()`` と書くと
    **モジュール import 時に評価されて固定される**ため、長時間動くプロセスで日付がずれ、
    テストも実行日に依存してしまう（AD-5）。

    完了済みタスクは期限を過ぎていても印を付けない。US-4 の受け入れ基準が
    「期限が本日より前**かつ未完了**」と定めているためである。``DUE TODAY`` も同様に
    未完了のみを対象とする。

    コマンド層（Issue #8）の ``--overdue`` フィルタは、この関数の戻り値が
    ``OVERDUE`` かどうかで判定できる。
    """
    if task.due is None or task.done:
        return None
    today = today or date.today()
    if task.due < today:
        return OVERDUE
    if task.due == today:
        return DUE_TODAY
    return None


def render_task(task: Task, today: date | None = None) -> str:
    """1 件のタスクを 1 行のプレーンテキストにする。改行は含めない。

    ID・チェック状態・本文は常に出す。優先度は既定値であっても常に出す（``Task.priority``
    は必ず値を持つ）。タグと期限は持つものだけを出す。期限状態は行末に置く。
    """
    checkbox = "x" if task.done else " "
    parts = [f"[{checkbox}]", f"#{task.id}"]
    if task.text:
        parts.append(task.text)
    parts.append(f"!{task.priority.value}")
    parts.extend(f"@{tag}" for tag in task.tags)
    if task.due is not None:
        parts.append(f"~{task.due.isoformat()}")

    state = due_state(task, today)
    if state is not None:
        parts.append(f"{_STATE_SEPARATOR} {state}")

    return " ".join(parts)


def render_list(tasks: list[Task], today: date | None = None) -> str:
    """タスク列を並べ替えたうえで、各行を改行連結した 1 つの文字列にする。

    末尾に改行は付けない（``print`` に渡す前提）。0 件のときは**空文字**を返し、
    例外は投げない。「タスクがない」旨のメッセージ表示は UX の判断であり、
    コマンド層（Issue #8）の責務として空けてある。
    """
    return "\n".join(render_task(task, today) for task in sort_tasks(tasks))
