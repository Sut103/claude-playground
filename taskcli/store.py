"""ストア層: ファイルの読み書き、原子的置換、ID 採番。

この層は Markdown ファイルと :class:`Document` の間の入出力だけを担う。設計の中心は
AD-3 である — タスクファイルは CLI の専有物ではなく、人間が見出しやメモを書き足す
場所でもある。したがって :class:`Document` は「パース済みのタスク行」と「原文のまま
維持する非タスク行」を **順序を保ったまま単一のリストで** 保持する。タスクだけの
リストと非タスク行だけのリストを別に持って後で合成する設計は採らない（行番号の管理
が必要になり、往復の保証が脆くなる）。

公開 API::

    load(path) -> Document
    save(path, document) -> None
    next_id(document) -> int
    Document

エンコーディングは読み書きとも UTF-8 を明示する。改行は読み取り時に LF へ正規化し、
書き出し時に ``"\\n".join(...) + "\\n"`` で再構成する。
"""

from __future__ import annotations

import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Iterable, Iterator, Union

from .parser import Task, format_line, parse_line

__all__ = ["Document", "Line", "load", "save", "next_id"]

#: ``Document`` の 1 要素。``Task``（解釈できたタスク行）か ``str``（原文のまま保持
#: する非タスク行）のいずれか。
Line = Union[Task, str]

# 「タスク行のつもりで書かれたが解釈できなかった行」を検出するための緩い判定。
# パーサ本体（`- [ ] ` / `- [x] `）より広く取り、`- [?] x` や `-[ ] x` のような
# 打ち間違いも警告の対象にする。見出し・段落・チェックボックスのない箇条書きは
# ここに掛からないため、警告で騒がしくならない。
_TASKISH_RE = re.compile(r"^\s*[-*]\s*\[[^\]]*\]")

#: 保存先が存在しないときに新規作成するファイルのパーミッション。既存ファイルを
#: 置換する場合は、そのファイルのモードを引き継ぐ。
_NEW_FILE_MODE = 0o644


class Document:
    """ファイル 1 つ分の内容を、行の出現順のまま保持する。

    要素は :class:`~taskcli.parser.Task` か ``str`` の混在である。``str`` の要素は
    見出し・空行・段落・箇条書き・解釈できなかったタスク行など「CLI が触らない行」で
    あり、改行を含まない原文そのものを保持する。
    """

    __slots__ = ("lines",)

    def __init__(self, lines: Iterable[Line] | None = None) -> None:
        self.lines: list[Line] = list(lines) if lines is not None else []

    # -- 参照 ---------------------------------------------------------------

    @property
    def tasks(self) -> list[Task]:
        """タスクだけをファイル内の出現順で返す。"""
        return [line for line in self.lines if isinstance(line, Task)]

    def find(self, task_id: int) -> Task | None:
        """ID でタスクを引く。見つからなければ ``None``。

        同じ ID が複数ある（人間の手編集で起こりうる）場合は最初の 1 件を返す。
        """
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None

    def __iter__(self) -> Iterator[Line]:
        return iter(self.lines)

    def __len__(self) -> int:
        return len(self.lines)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Document):
            return NotImplemented
        return self.lines == other.lines

    def __repr__(self) -> str:
        return f"Document(lines={self.lines!r})"

    # -- 更新 ---------------------------------------------------------------

    def add(self, task: Task) -> Task:
        """タスクを末尾に追加する。既存行の位置関係は変わらない。"""
        self.lines.append(task)
        return task

    def complete(self, task_id: int) -> Task | None:
        """ID のタスクを完了にする。対象が無ければ ``None``。

        行の位置は変えない — チェックボックスだけが ``[x]`` になる。
        """
        task = self.find(task_id)
        if task is None:
            return None
        task.done = True
        return task

    def remove(self, task_id: int) -> Task | None:
        """ID のタスクを削除する。対象が無ければ ``None``。

        消えるのはその 1 行だけであり、他の行（タスク・非タスクとも）の内容も
        相対位置も変わらない。他タスクの ID を振り直すことはしない（FR-5）。
        """
        for index, line in enumerate(self.lines):
            if isinstance(line, Task) and line.id == task_id:
                del self.lines[index]
                return line
        return None

    # -- 直列化 -------------------------------------------------------------

    def to_lines(self) -> list[str]:
        """書き出す文字列の行リストを、元の順序のまま組み立てる。"""
        return [format_line(line) if isinstance(line, Task) else line for line in self.lines]

    def to_text(self) -> str:
        """ファイルに書き出す全文。末尾に改行を 1 つ持つ（空なら空文字列）。"""
        lines = self.to_lines()
        if not lines:
            return ""
        return "\n".join(lines) + "\n"


def next_id(document: Document) -> int:
    """次に採番すべき ID を返す（AD-2）。

    既存タスクの ID の最大値 + 1。タスクが 1 件もなければ ``1``。採番は毎回
    ``Document`` から導出され、状態ファイルは作らない。

    この方式には既知の限界がある — 最大 ID のタスクを削除すると、その ID が次の
    採番で再利用される。中間の ID（1, 2, 3 のうち 2）を削除した場合は再利用され
    ないが、末尾は戻る。状態ファイルを持たないという AD-2 の決定の帰結であり、
    単一利用者のローカル CLI という前提では許容する。
    """
    ids = [task.id for task in document.tasks]
    return max(ids) + 1 if ids else 1


def load(path: str | os.PathLike[str]) -> Document:
    """ファイルを読み込んで :class:`Document` を返す。

    - タスクとして解釈できた行は :class:`~taskcli.parser.Task` になる
    - それ以外の行は原文の ``str`` のまま保持される
    - **ファイルが存在しなければ空の ``Document`` を返す**（例外は送出しない）。
      US-1 のとおり、利用者が初期化コマンドを別途叩く必要をなくすためである
    - タスク行のつもりに見えて解釈できない行は、stderr に行番号つきの警告を出した
      うえで非タスク行として原文のまま保持し、処理を継続する（FR-8）
    - ID の重複は警告するだけで失敗しない。ファイルは人間が手編集しうるため、
      読み取り時点で異常終了させない（検証は上位層の責務）

    警告は **stderr にのみ** 出す。``list`` の出力をパイプで扱えるよう、stdout は
    汚さない。
    """
    file_path = Path(path)
    try:
        # newline 既定（ユニバーサル改行）により CRLF は読み取り時点で LF になる。
        text = file_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return Document()

    document = Document()
    seen_ids: set[int] = set()

    for lineno, raw in enumerate(_split_lines(text), start=1):
        task = parse_line(raw)
        if task is None:
            if _TASKISH_RE.match(raw):
                _warn(f"{file_path}:{lineno}: タスク行として解釈できません（原文のまま保持します）: {raw}")
            document.lines.append(raw)
            continue
        if task.id in seen_ids:
            _warn(f"{file_path}:{lineno}: ID {task.id} が重複しています")
        seen_ids.add(task.id)
        document.lines.append(task)

    return document


def save(path: str | os.PathLike[str], document: Document) -> None:
    """``Document`` をファイルへ原子的に書き出す（AD-4 / NFR-3）。

    一時ファイルを **保存先と同一ディレクトリ** に作り、書き込み・``flush`` ・
    ``os.fsync`` の後に :func:`os.replace` で目的パスへ置換する。``os.replace`` の
    原子性は同一ファイルシステム内でのみ保証されるため、``/tmp`` などに一時ファイルを
    置くことはしない。``shutil.move`` も跨ファイルシステム時にコピーへフォールバック
    して原子性を失うため使わない。

    途中で中断・例外が起きた場合、目的パスは従前の内容のまま残り、一時ファイルは
    後始末される。

    保存先の親ディレクトリが存在しない場合は :class:`FileNotFoundError` を送出する
    （ディレクトリを暗黙に作りはしない）。``TASK_CLI_FILE`` の打ち間違いで思わぬ場所に
    ディレクトリ階層が生えるのを避けるためである。
    """
    file_path = Path(path)
    directory = file_path.parent
    if not directory.is_dir():
        raise FileNotFoundError(f"保存先のディレクトリがありません: {directory}")

    text = document.to_text()
    mode = file_path.stat().st_mode & 0o777 if file_path.exists() else _NEW_FILE_MODE

    fd, tmp_name = tempfile.mkstemp(dir=str(directory), prefix=f".{file_path.name}.", suffix=".tmp")
    try:
        with open(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp_name, mode)
        os.replace(tmp_name, file_path)
    except BaseException:
        # 残骸を残さない。置換に成功した後なら tmp_name は既に存在しない。
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _split_lines(text: str) -> list[str]:
    """全文を行に分解する。行末の改行は保持しない。

    ``str.splitlines`` は ``\\x0b`` や ``\\u2028`` でも分割してしまい、本文に含まれた
    それらの文字でファイルの行数が変わる。ここでは LF だけを行区切りとして扱う
    （CRLF は読み取り時に LF へ正規化済み）。
    """
    if text == "":
        return []
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def _warn(message: str) -> None:
    """警告を stderr に出す。

    ``sys.stderr`` は呼び出しのたびに参照する — テストが
    ``contextlib.redirect_stderr`` で差し替えられるようにするためである。
    """
    print(message, file=sys.stderr)
