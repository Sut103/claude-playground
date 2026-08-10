"""Issue #6: ストア層のテスト。

AD-3（非タスク行の順序保存）、AD-4（同一ディレクトリの一時ファイル + ``os.replace``）、
AD-2（ID をファイルから毎回導出する採番）、FR-8（解釈できない行の警告と継続）に対応する。
"""

import io
import os
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from datetime import date
from pathlib import Path

import pytest

from taskcli.parser import Priority, Task
from taskcli.store import Document, load, next_id, save

MIXED_FILE = """\
## 今週

- [ ] リファクタする `#3` `!high` `@docs` `~2026-08-20`

メモ: 金曜までにレビューを回す
- ふつうの箇条書き
- [x] README を書く `#1` `!mid`
"""


def write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def capture_load(path: Path) -> tuple[Document, str]:
    """``load`` を stderr を捕捉しながら呼ぶ。"""
    err = io.StringIO()
    with redirect_stderr(err):
        document = load(path)
    return document, err.getvalue()


# --------------------------------------------------------------------------
# Document モデル
# --------------------------------------------------------------------------


class TestDocument:
    def test_holds_tasks_and_raw_lines_in_original_order(self, tmp_path):
        document = load(write(tmp_path / "TASKS.md", MIXED_FILE))
        kinds = [type(line).__name__ for line in document.lines]
        assert kinds == ["str", "str", "Task", "str", "str", "str", "Task"]
        assert document.lines[0] == "## 今週"
        assert document.lines[4] == "メモ: 金曜までにレビューを回す"

    def test_tasks_property_keeps_file_order(self, tmp_path):
        document = load(write(tmp_path / "TASKS.md", MIXED_FILE))
        assert [task.id for task in document.tasks] == [3, 1]

    def test_find_returns_task_by_id(self, tmp_path):
        document = load(write(tmp_path / "TASKS.md", MIXED_FILE))
        assert document.find(3).text == "リファクタする"
        assert document.find(999) is None

    def test_add_appends_without_disturbing_other_lines(self, tmp_path):
        document = load(write(tmp_path / "TASKS.md", MIXED_FILE))
        before = list(document.lines)
        document.add(Task(id=4, text="新しいタスク"))
        assert document.lines[:-1] == before
        assert document.tasks[-1].id == 4

    def test_complete_flips_checkbox_in_place(self, tmp_path):
        document = load(write(tmp_path / "TASKS.md", MIXED_FILE))
        position = document.lines.index(document.find(3))
        assert document.complete(3).done is True
        assert document.lines.index(document.find(3)) == position
        assert len(document.lines) == 7

    def test_complete_unknown_id_returns_none(self):
        assert Document().complete(1) is None

    def test_remove_deletes_only_that_line(self, tmp_path):
        document = load(write(tmp_path / "TASKS.md", MIXED_FILE))
        removed = document.remove(3)
        assert removed.id == 3
        assert [type(line).__name__ for line in document.lines] == [
            "str",
            "str",
            "str",
            "str",
            "str",
            "Task",
        ]
        assert document.lines[0] == "## 今週"
        assert document.lines[3] == "メモ: 金曜までにレビューを回す"

    def test_remove_unknown_id_returns_none(self):
        assert Document().remove(1) is None

    def test_empty_document_has_no_tasks(self):
        document = Document()
        assert document.tasks == []
        assert len(document) == 0
        assert list(document) == []


# --------------------------------------------------------------------------
# load
# --------------------------------------------------------------------------


class TestLoad:
    def test_parses_task_lines(self, tmp_path):
        document = load(write(tmp_path / "TASKS.md", MIXED_FILE))
        assert document.find(3) == Task(
            id=3,
            text="リファクタする",
            done=False,
            priority=Priority.HIGH,
            tags=["docs"],
            due=date(2026, 8, 20),
        )
        assert document.find(1).done is True

    def test_missing_file_returns_empty_document_without_raising(self, tmp_path):
        document = load(tmp_path / "存在しない.md")
        assert isinstance(document, Document)
        assert document.lines == []
        assert document.tasks == []

    def test_missing_file_is_not_created(self, tmp_path):
        path = tmp_path / "存在しない.md"
        load(path)
        assert not path.exists()

    def test_empty_file_returns_empty_document(self, tmp_path):
        document = load(write(tmp_path / "TASKS.md", ""))
        assert document.lines == []

    def test_non_task_lines_are_kept_verbatim(self, tmp_path):
        text = "## 今週\n\nふつうの段落\n- チェックボックスのない箇条書き\n"
        document = load(write(tmp_path / "TASKS.md", text))
        assert document.lines == [
            "## 今週",
            "",
            "ふつうの段落",
            "- チェックボックスのない箇条書き",
        ]

    def test_blank_lines_are_preserved_including_consecutive_ones(self, tmp_path):
        document = load(write(tmp_path / "TASKS.md", "a\n\n\nb\n"))
        assert document.lines == ["a", "", "", "b"]

    def test_crlf_is_normalised_to_lf(self, tmp_path):
        path = tmp_path / "TASKS.md"
        path.write_bytes("## 見出し\r\n- [ ] x `#1` `!mid`\r\n".encode("utf-8"))
        document = load(path)
        assert document.lines[0] == "## 見出し"
        assert document.find(1).text == "x"

    def test_utf8_is_explicit(self, tmp_path):
        path = write(tmp_path / "TASKS.md", "- [ ] 日本語の本文 `#1` `!high`\n")
        assert load(path).find(1).text == "日本語の本文"

    def test_file_without_trailing_newline(self, tmp_path):
        document = load(write(tmp_path / "TASKS.md", "- [ ] x `#1` `!mid`"))
        assert [task.id for task in document.tasks] == [1]
        assert len(document.lines) == 1


class TestLoadWarnings:
    UNPARSEABLE = "## 見出し\n- [ ] ID がない `!high`\n- [ ] 正常 `#2` `!mid`\n"

    def test_unparseable_task_line_is_kept_verbatim_and_processing_continues(self, tmp_path):
        document, _ = capture_load(write(tmp_path / "TASKS.md", self.UNPARSEABLE))
        assert document.lines[1] == "- [ ] ID がない `!high`"
        assert [task.id for task in document.tasks] == [2]

    def test_warning_includes_line_number(self, tmp_path):
        _, err = capture_load(write(tmp_path / "TASKS.md", self.UNPARSEABLE))
        assert ":2:" in err
        assert "- [ ] ID がない `!high`" in err

    def test_warning_goes_to_stderr_not_stdout(self, tmp_path):
        path = write(tmp_path / "TASKS.md", self.UNPARSEABLE)
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            load(path)
        assert out.getvalue() == ""
        assert err.getvalue() != ""

    def test_no_warning_for_ordinary_non_task_lines(self, tmp_path):
        text = "## 今週\n\nふつうの段落\n- ふつうの箇条書き\n- [ ] 正常 `#1` `!mid`\n"
        _, err = capture_load(write(tmp_path / "TASKS.md", text))
        assert err == ""

    def test_does_not_raise_on_unparseable_lines(self, tmp_path):
        text = "- [?] 壊れた\n- [ ] `#abc`\n- [ ] 不正な優先度 `#1` `!urgent`\n"
        document, err = capture_load(write(tmp_path / "TASKS.md", text))
        assert len(document.lines) == 3
        assert document.tasks == []
        assert err.count("\n") == 3

    def test_duplicate_ids_do_not_fail_the_load(self, tmp_path):
        text = "- [ ] 一つ目 `#1` `!mid`\n- [ ] 二つ目 `#1` `!high`\n"
        document, err = capture_load(write(tmp_path / "TASKS.md", text))
        assert [task.id for task in document.tasks] == [1, 1]
        assert "1" in err  # 警告は出してよい（失敗しないことが要件）


# --------------------------------------------------------------------------
# save
# --------------------------------------------------------------------------


class TestSave:
    def test_writes_lines_in_original_order(self, tmp_path):
        path = tmp_path / "TASKS.md"
        save(path, Document(["## 今週", "", Task(id=1, text="x"), "メモ"]))
        assert path.read_text(encoding="utf-8") == "## 今週\n\n- [ ] x `#1` `!mid`\nメモ\n"

    def test_output_ends_with_exactly_one_newline(self, tmp_path):
        path = tmp_path / "TASKS.md"
        save(path, Document([Task(id=1, text="x")]))
        text = path.read_text(encoding="utf-8")
        assert text.endswith("\n")
        assert not text.endswith("\n\n")

    def test_line_endings_are_lf_only(self, tmp_path):
        path = tmp_path / "TASKS.md"
        save(path, Document(["a", Task(id=1, text="b"), "c"]))
        assert b"\r" not in path.read_bytes()

    def test_empty_document_writes_empty_file(self, tmp_path):
        path = tmp_path / "TASKS.md"
        save(path, Document())
        assert path.read_text(encoding="utf-8") == ""

    def test_creates_file_when_absent(self, tmp_path):
        path = tmp_path / "TASKS.md"
        save(path, Document([Task(id=1, text="x")]))
        assert path.exists()

    def test_utf8_is_explicit(self, tmp_path):
        path = tmp_path / "TASKS.md"
        save(path, Document([Task(id=1, text="日本語")]))
        assert "日本語" in path.read_bytes().decode("utf-8")

    def test_accepts_str_path(self, tmp_path):
        path = tmp_path / "TASKS.md"
        save(str(path), Document([Task(id=1, text="x")]))
        assert path.exists()

    def test_leaves_no_temporary_files_behind(self, tmp_path):
        path = tmp_path / "TASKS.md"
        save(path, Document([Task(id=1, text="x")]))
        assert [p.name for p in tmp_path.iterdir()] == ["TASKS.md"]

    def test_missing_parent_directory_raises_and_creates_nothing(self, tmp_path):
        path = tmp_path / "無い階層" / "TASKS.md"
        with pytest.raises(FileNotFoundError):
            save(path, Document([Task(id=1, text="x")]))
        assert not path.parent.exists()

    def test_preserves_existing_file_permissions(self, tmp_path):
        path = write(tmp_path / "TASKS.md", "- [ ] x `#1` `!mid`\n")
        os.chmod(path, 0o600)
        save(path, Document([Task(id=1, text="y")]))
        assert path.stat().st_mode & 0o777 == 0o600


class TestSaveIsAtomic:
    def test_temp_file_is_created_in_the_destination_directory(self, tmp_path, monkeypatch):
        """AD-4: 一時ファイルは保存先と同一ディレクトリ（= 同一ファイルシステム）に作る。"""
        seen = {}
        real_mkstemp = tempfile.mkstemp

        def spy(*args, **kwargs):
            seen["dir"] = kwargs.get("dir")
            return real_mkstemp(*args, **kwargs)

        monkeypatch.setattr("taskcli.store.tempfile.mkstemp", spy)
        path = tmp_path / "TASKS.md"
        save(path, Document([Task(id=1, text="x")]))
        assert Path(seen["dir"]).resolve() == tmp_path.resolve()

    def test_uses_os_replace_on_the_destination(self, tmp_path, monkeypatch):
        calls = []
        real_replace = os.replace

        def spy(src, dst):
            calls.append((str(src), str(dst)))
            return real_replace(src, dst)

        monkeypatch.setattr("taskcli.store.os.replace", spy)
        path = tmp_path / "TASKS.md"
        save(path, Document([Task(id=1, text="x")]))
        assert len(calls) == 1
        assert calls[0][1] == str(path)
        assert Path(calls[0][0]).parent.resolve() == tmp_path.resolve()

    def test_interruption_before_replace_leaves_original_intact(self, tmp_path, monkeypatch):
        original = "## 元の内容\n- [ ] 元のタスク `#1` `!mid`\n"
        path = write(tmp_path / "TASKS.md", original)

        def boom(src, dst):
            raise KeyboardInterrupt("置換の直前で中断")

        monkeypatch.setattr("taskcli.store.os.replace", boom)
        with pytest.raises(KeyboardInterrupt):
            save(path, Document([Task(id=9, text="新しい内容")]))

        assert path.read_text(encoding="utf-8") == original
        assert [p.name for p in tmp_path.iterdir()] == ["TASKS.md"]

    def test_write_failure_cleans_up_the_temp_file(self, tmp_path, monkeypatch):
        path = write(tmp_path / "TASKS.md", "- [ ] 元 `#1` `!mid`\n")

        def boom(fd):
            raise OSError("書き込み中の失敗")

        monkeypatch.setattr("taskcli.store.os.fsync", boom)
        with pytest.raises(OSError):
            save(path, Document([Task(id=2, text="新")]))

        assert path.read_text(encoding="utf-8") == "- [ ] 元 `#1` `!mid`\n"
        assert [p.name for p in tmp_path.iterdir()] == ["TASKS.md"]

    def test_destination_never_holds_partial_content(self, tmp_path, monkeypatch):
        """置換は最後の 1 手なので、目的パスに中間状態は現れない。"""
        original = "- [ ] 元 `#1` `!mid`\n"
        path = write(tmp_path / "TASKS.md", original)
        observed = []
        real_replace = os.replace

        def spy(src, dst):
            observed.append(Path(dst).read_text(encoding="utf-8"))
            return real_replace(src, dst)

        monkeypatch.setattr("taskcli.store.os.replace", spy)
        save(path, Document([Task(id=1, text="更新後")]))
        assert observed == [original]  # 置換の瞬間まで従前の内容のまま


# --------------------------------------------------------------------------
# next_id
# --------------------------------------------------------------------------


class TestNextId:
    def test_empty_document_starts_at_one(self):
        assert next_id(Document()) == 1

    def test_document_without_tasks_starts_at_one(self):
        assert next_id(Document(["## 今週", "", "メモ"])) == 1

    def test_returns_max_plus_one(self):
        document = Document([Task(id=1, text="a"), "メモ", Task(id=7, text="b")])
        assert next_id(document) == 8

    def test_ignores_position_and_uses_maximum(self):
        document = Document([Task(id=9, text="a"), Task(id=2, text="b")])
        assert next_id(document) == 10

    def test_derived_from_document_every_time_without_a_state_file(self, tmp_path):
        path = tmp_path / "TASKS.md"
        save(path, Document([Task(id=5, text="a")]))
        assert [p.name for p in tmp_path.iterdir()] == ["TASKS.md"]
        assert next_id(load(path)) == 6

    def test_deleting_a_middle_task_does_not_renumber_or_reuse(self, tmp_path):
        """FR-5: ID 1,2,3 のうち 2 を削除しても 1 と 3 は不変、次は 4。"""
        path = tmp_path / "TASKS.md"
        save(
            path,
            Document([Task(id=1, text="a"), Task(id=2, text="b"), Task(id=3, text="c")]),
        )
        document = load(path)
        document.remove(2)
        save(path, document)

        reloaded = load(path)
        assert [task.id for task in reloaded.tasks] == [1, 3]
        assert [task.text for task in reloaded.tasks] == ["a", "c"]
        assert next_id(reloaded) == 4

    def test_deleting_the_highest_id_reuses_it(self):
        """AD-2 の既知の限界を現在の挙動として固定する。

        最大 ID を削除すると次の採番はその ID に戻る。ファイルから毎回導出し、
        状態ファイルを持たないという決定の帰結である。
        """
        document = Document([Task(id=1, text="a"), Task(id=2, text="b"), Task(id=3, text="c")])
        assert next_id(document) == 4
        document.remove(3)
        assert next_id(document) == 3


# --------------------------------------------------------------------------
# 往復（round-trip）
# --------------------------------------------------------------------------


class TestRoundTrip:
    def test_load_then_save_preserves_every_line_and_its_position(self, tmp_path):
        path = write(tmp_path / "TASKS.md", MIXED_FILE)
        save(path, load(path))
        assert path.read_text(encoding="utf-8") == MIXED_FILE

    def test_adding_a_task_does_not_move_existing_lines(self, tmp_path):
        path = write(tmp_path / "TASKS.md", MIXED_FILE)
        document = load(path)
        document.add(Task(id=next_id(document), text="追加分", priority=Priority.LOW))
        save(path, document)

        lines = path.read_text(encoding="utf-8").splitlines()
        assert lines[:-1] == MIXED_FILE.splitlines()
        assert lines[-1] == "- [ ] 追加分 `#4` `!low`"

    def test_completing_a_task_only_changes_its_checkbox(self, tmp_path):
        path = write(tmp_path / "TASKS.md", MIXED_FILE)
        document = load(path)
        document.complete(3)
        save(path, document)

        before = MIXED_FILE.splitlines()
        after = path.read_text(encoding="utf-8").splitlines()
        assert len(after) == len(before)
        differing = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
        assert differing == [2]
        assert after[2].startswith("- [x] ")

    def test_removing_a_task_deletes_only_that_line(self, tmp_path):
        path = write(tmp_path / "TASKS.md", MIXED_FILE)
        document = load(path)
        document.remove(3)
        save(path, document)

        before = MIXED_FILE.splitlines()
        after = path.read_text(encoding="utf-8").splitlines()
        assert after == [line for line in before if "`#3`" not in line]

    def test_unparseable_line_survives_in_place(self, tmp_path):
        text = "## 見出し\n- [ ] 壊れた行 `!high`\n- [ ] 正常 `#1` `!mid`\nメモ\n"
        path = write(tmp_path / "TASKS.md", text)
        err = io.StringIO()
        with redirect_stderr(err):
            document = load(path)
        save(path, document)
        assert path.read_text(encoding="utf-8") == text
        assert err.getvalue() != ""

    def test_round_trip_is_idempotent(self, tmp_path):
        path = write(tmp_path / "TASKS.md", MIXED_FILE)
        for _ in range(3):
            save(path, load(path))
        assert path.read_text(encoding="utf-8") == MIXED_FILE

    def test_round_trip_of_an_empty_file(self, tmp_path):
        path = write(tmp_path / "TASKS.md", "")
        save(path, load(path))
        assert path.read_text(encoding="utf-8") == ""

    def test_full_cycle_add_complete_remove(self, tmp_path):
        path = tmp_path / "TASKS.md"
        document = load(path)  # 存在しないファイル → 空の Document
        for text in ("一つ目", "二つ目", "三つ目"):
            document.add(Task(id=next_id(document), text=text))
        save(path, document)

        document = load(path)
        document.complete(2)
        document.remove(1)
        save(path, document)

        reloaded = load(path)
        assert [(t.id, t.text, t.done) for t in reloaded.tasks] == [
            (2, "二つ目", True),
            (3, "三つ目", False),
        ]
        assert next_id(reloaded) == 4
