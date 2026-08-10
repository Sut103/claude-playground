"""パーサ層: Markdown の 1 行と Task の相互変換。

行フォーマット（AD-1）::

    - [ ] リファクタする `#3` `!high` `@docs` `@refactor` `~2026-08-20`
    - [x] README を書く `#1` `!mid`

``#N`` が ID、``!`` が優先度、``@`` がタグ、``~`` が期限を表す。

この層はファイル I/O を行わず、他のどの層にも依存しない。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum

__all__ = ["Priority", "Task", "parse_line", "format_line", "parse_due"]


class Priority(Enum):
    """タスクの優先度。

    ``sort_rank`` は表示層（Issue #7）が昇順ソートに使う数値である。値が小さいほど
    優先度が高い — つまり ``sorted(tasks, key=lambda t: t.priority.sort_rank)`` で
    high が先頭に来る。表示層はこのプロパティに依存してよい。
    """

    HIGH = "high"
    MID = "mid"
    LOW = "low"

    @property
    def sort_rank(self) -> int:
        return _SORT_RANKS[self]

    @classmethod
    def from_token(cls, token: str) -> "Priority | None":
        """``high`` のような文字列を ``Priority`` にする。未知の値なら ``None``。"""
        try:
            return cls(token)
        except ValueError:
            return None


_SORT_RANKS = {Priority.HIGH: 0, Priority.MID: 1, Priority.LOW: 2}

#: 優先度を省略したタスクに与える既定値。
DEFAULT_PRIORITY = Priority.MID


@dataclass
class Task:
    """1 件のタスク。

    ``done`` はコマンド層（Issue #8）が書き換えるため、データクラスは可変とする。
    """

    id: int
    text: str
    done: bool = False
    priority: Priority = DEFAULT_PRIORITY
    tags: list[str] = field(default_factory=list)
    due: date | None = None


# `- [ ] ` / `- [x] ` / `- [X] ` の接頭辞。本文が空の行も許容する。
_CHECKBOX_RE = re.compile(r"^-\s\[([ xX])\]\s?(.*)$")

# 行末に並ぶバッククォート囲みトークンを右から 1 つずつ剥がす。
_TRAILING_TOKEN_RE = re.compile(r"\s*`([^`]+)`$")

# 日付は桁数まで厳密に見る。strptime だけでは `26-08-20` や `2026-8-20` を通してしまう。
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_due(token: str) -> date | None:
    """``YYYY-MM-DD`` を ``date`` にする。書式・値が不正なら ``None``。

    ``2026-13-45``（範囲外）、``2026-02-30``（存在しない日）、``2026/08/20``（区切り違い）、
    ``26-08-20``（桁数違い）、``tomorrow`` はいずれも ``None`` になる。
    """
    if not _DATE_RE.match(token):
        return None
    try:
        return datetime.strptime(token, "%Y-%m-%d").date()
    except ValueError:
        return None


def parse_line(line: str) -> Task | None:
    """1 行を ``Task`` として解釈する。解釈できなければ ``None`` を返す。

    **例外は送出しない**（AD-3）。ファイルには見出し・メモ・通常の箇条書きといった
    「タスク行ではない行」が当然に混ざっており、それらはエラーではない。``None`` は
    「この行は Task として解釈できなかった」という事実だけを伝え、それをどう扱うか
    （警告するか、原文のまま保持するか）の判断はストア層（Issue #6）に委ねる。
    """
    checkbox = _CHECKBOX_RE.match(line.rstrip("\n"))
    if checkbox is None:
        return None

    done = checkbox.group(1).lower() == "x"
    rest = checkbox.group(2)

    # 行末から順にトークンを剥がす。右から取るので、収集順は行内の並びと逆になる。
    tokens: list[str] = []
    while True:
        match = _TRAILING_TOKEN_RE.search(rest)
        if match is None:
            break
        tokens.append(match.group(1))
        rest = rest[: match.start()]
    tokens.reverse()

    task_id: int | None = None
    priority: Priority | None = None
    tags: list[str] = []
    due: date | None = None

    for token in tokens:
        marker, value = token[0], token[1:]
        if not value:
            return None
        if marker == "#":
            if task_id is not None or not value.isdigit():
                return None
            task_id = int(value)
        elif marker == "!":
            if priority is not None:
                return None
            priority = Priority.from_token(value)
            if priority is None:
                return None
        elif marker == "@":
            tags.append(value)
        elif marker == "~":
            if due is not None:
                return None
            due = parse_due(value)
            if due is None:
                return None
        else:
            # 未知の記号は「不正」として扱う。曖昧に受け流すと往復で情報が失われる。
            return None

    if task_id is None:
        # ID を持たない行はタスクとして識別できない。
        return None

    return Task(
        id=task_id,
        text=rest.strip(),
        done=done,
        priority=priority if priority is not None else DEFAULT_PRIORITY,
        tags=tags,
        due=due,
    )


def format_line(task: Task) -> str:
    """``Task`` を AD-1 の書式の 1 行に戻す。改行は含めない。

    メタデータの並びは ``#id`` → ``!priority`` → ``@tag...`` → ``~due`` に固定する。
    優先度は既定値であっても常に出力する — 往復を安定させ、手編集時に読み取れる
    ようにするためである。
    """
    checkbox = "x" if task.done else " "
    parts = [f"- [{checkbox}] {task.text}".rstrip(), f"`#{task.id}`", f"`!{task.priority.value}`"]
    parts.extend(f"`@{tag}`" for tag in task.tags)
    if task.due is not None:
        parts.append(f"`~{task.due.isoformat()}`")
    return " ".join(parts)
