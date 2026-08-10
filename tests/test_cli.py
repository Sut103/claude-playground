"""Issue #8: コマンド層のテスト。

ここで検証するのは「引数がどう解釈され、どの終了コードが返るか」である。
``cli`` のシーム（``_load`` / ``_save`` / ``_render``）を ``monkeypatch`` で
差し替え、コマンド関数がシームに何を渡し、何を返すかを見る。実ファイルに対する
通し確認は Issue #9 の E2E テストが受け持つ。

**Issue #9 での更新**: 当初このテストは、シームを流れるドキュメントとして
``list[Task]`` を渡していた。#8 の実装時点で ``store.Document`` がまだ存在せず、
シームの契約が「関数のシグネチャ」までしか定めていなかったためである。
結線後は本物の ``Document`` が流れるので、テストの差し替えも ``Document`` に
揃えた。シームの関数シグネチャ自体は #8 のまま変更していない。
"""

from datetime import date, timedelta

import pytest

from taskcli import cli
from taskcli.parser import Priority, Task
from taskcli.store import Document

TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)
TOMORROW = TODAY + timedelta(days=1)


def run(argv):
    """argparse で解析し、対応するコマンド関数を呼んで終了コードを返す。"""
    args = cli.build_parser().parse_args(argv)
    return args.func(args)


class Seam:
    """差し替えたシームが受け取った呼び出しの記録。"""

    def __init__(self, tasks):
        self.doc = Document(tasks)
        self.loaded = []
        self.saved = []
        self.rendered = []

    def load(self, path):
        self.loaded.append(path)
        return self.doc

    def save(self, path, doc):
        self.saved.append((path, list(doc)))

    def render(self, tasks):
        self.rendered.append(list(tasks))
        return "\n".join(f"#{task.id} {task.text}" for task in tasks)

    @property
    def rendered_ids(self):
        assert len(self.rendered) == 1
        return [task.id for task in self.rendered[0]]


@pytest.fixture
def seam(monkeypatch, tmp_path):
    """シームを差し替え、タスクファイルのパスも一時ディレクトリへ固定する。"""
    monkeypatch.setenv(cli.TASK_FILE_ENV, str(tmp_path / "TASKS.md"))

    def install(tasks=()):
        recorder = Seam(tasks)
        monkeypatch.setattr(cli, "_load", recorder.load)
        monkeypatch.setattr(cli, "_save", recorder.save)
        monkeypatch.setattr(cli, "_render", recorder.render)
        return recorder

    return install


def task(id, text="やること", *, done=False, priority=Priority.MID, tags=None, due=None):
    return Task(id=id, text=text, done=done, priority=priority, tags=list(tags or []), due=due)


# --------------------------------------------------------------------------- #
# パーサの骨格
# --------------------------------------------------------------------------- #


class TestParserSkeleton:
    @pytest.mark.parametrize(
        "argv, name",
        [
            (["add", "x"], "add"),
            (["list"], "list"),
            (["done", "1"], "done"),
            (["rm", "1"], "rm"),
        ],
    )
    def test_subcommand_exists(self, argv, name):
        args = cli.build_parser().parse_args(argv)
        assert args.command == name
        assert callable(args.func)

    def test_missing_subcommand_prints_help_and_exits_nonzero(self, capsys):
        with pytest.raises(SystemExit) as exc:
            cli.main([])
        assert exc.value.code != 0
        captured = capsys.readouterr()
        # ヘルプ相当は stderr へ。無言で成功してはならない。
        assert "add" in captured.err and "list" in captured.err
        assert captured.out == ""

    def test_unknown_subcommand_exits_nonzero(self):
        with pytest.raises(SystemExit) as exc:
            cli.build_parser().parse_args(["frobnicate"])
        assert exc.value.code == 2

    def test_main_passes_command_return_value_to_sys_exit(self, monkeypatch, seam):
        seam()
        monkeypatch.setattr(cli, "cmd_list", lambda args: 42)
        with pytest.raises(SystemExit) as exc:
            cli.main(["list"])
        assert exc.value.code == 42

    def test_main_exits_zero_on_success(self, seam):
        seam()
        with pytest.raises(SystemExit) as exc:
            cli.main(["list"])
        assert exc.value.code == 0


# --------------------------------------------------------------------------- #
# add（FR-1、US-1、US-4）
# --------------------------------------------------------------------------- #


class TestAdd:
    def test_text_is_required_positional(self):
        with pytest.raises(SystemExit) as exc:
            cli.build_parser().parse_args(["add"])
        assert exc.value.code == 2

    def test_default_priority_is_mid(self):
        assert cli.build_parser().parse_args(["add", "x"]).priority == "mid"

    def test_priority_choices_are_restricted(self):
        with pytest.raises(SystemExit) as exc:
            cli.build_parser().parse_args(["add", "x", "--priority", "urgent"])
        assert exc.value.code == 2

    def test_priority_is_converted_to_enum(self, seam):
        recorder = seam()
        assert run(["add", "x", "--priority", "high"]) == 0
        assert recorder.doc.tasks[-1].priority is Priority.HIGH

    def test_tag_appends(self, seam):
        recorder = seam()
        assert run(["add", "x", "--tag", "docs", "--tag", "refactor"]) == 0
        assert recorder.doc.tasks[-1].tags == ["docs", "refactor"]

    def test_tag_defaults_to_empty_list_not_none(self, seam):
        recorder = seam()
        run(["add", "x"])
        assert recorder.doc.tasks[-1].tags == []

    def test_due_is_parsed_into_date(self, seam):
        recorder = seam()
        run(["add", "x", "--due", "2026-08-20"])
        assert recorder.doc.tasks[-1].due == date(2026, 8, 20)

    @pytest.mark.parametrize("bad", ["2026-13-45", "tomorrow", "2026/08/20", "26-08-20", "2026-02-30"])
    def test_invalid_due_is_rejected_before_any_write(self, bad, seam, capsys):
        recorder = seam()
        with pytest.raises(SystemExit) as exc:
            cli.main(["add", "x", "--due", bad])
        assert exc.value.code == 2
        captured = capsys.readouterr()
        assert bad in captured.err
        # US-4: 検証は書き込みより前。ファイルに触れる経路へ到達していない。
        assert recorder.loaded == [] and recorder.saved == []

    def test_assigned_id_is_printed_and_exit_zero(self, seam, capsys):
        recorder = seam([task(1), task(4)])
        assert run(["add", "新しいこと"]) == 0
        assert "5" in capsys.readouterr().out
        assert recorder.doc.tasks[-1].id == 5

    def test_saves_to_resolved_path(self, seam, tmp_path):
        recorder = seam()
        run(["add", "x"])
        assert recorder.saved and recorder.saved[0][0] == tmp_path / "TASKS.md"

    def test_new_task_is_not_done(self, seam):
        recorder = seam()
        run(["add", "x"])
        assert recorder.doc.tasks[-1].done is False


# --------------------------------------------------------------------------- #
# list（FR-2、US-3）
# --------------------------------------------------------------------------- #


class TestList:
    def test_default_hides_done_tasks(self, seam):
        recorder = seam([task(1), task(2, done=True)])
        assert run(["list"]) == 0
        assert recorder.rendered_ids == [1]

    def test_all_includes_done_tasks(self, seam):
        recorder = seam([task(1), task(2, done=True)])
        assert run(["list", "--all"]) == 0
        assert recorder.rendered_ids == [1, 2]

    def test_priority_filter(self, seam):
        recorder = seam([task(1, priority=Priority.HIGH), task(2, priority=Priority.LOW)])
        run(["list", "--priority", "high"])
        assert recorder.rendered_ids == [1]

    def test_tag_filter(self, seam):
        recorder = seam([task(1, tags=["docs"]), task(2, tags=["code"])])
        run(["list", "--tag", "docs"])
        assert recorder.rendered_ids == [1]

    def test_overdue_filter(self, seam):
        recorder = seam([task(1, due=YESTERDAY), task(2, due=TOMORROW), task(3)])
        run(["list", "--overdue"])
        assert recorder.rendered_ids == [1]

    def test_filters_combine_with_and(self, seam):
        recorder = seam(
            [
                task(1, priority=Priority.HIGH, tags=["docs"]),
                task(2, priority=Priority.HIGH, tags=["code"]),
                task(3, priority=Priority.LOW, tags=["docs"]),
            ]
        )
        run(["list", "--priority", "high", "--tag", "docs"])
        assert recorder.rendered_ids == [1]

    def test_repeated_tags_combine_with_and(self, seam):
        recorder = seam([task(1, tags=["docs", "code"]), task(2, tags=["docs"])])
        run(["list", "--tag", "docs", "--tag", "code"])
        assert recorder.rendered_ids == [1]

    def test_zero_matches_still_exits_zero(self, seam, capsys):
        recorder = seam([task(1, priority=Priority.LOW)])
        assert run(["list", "--priority", "high"]) == 0
        assert recorder.rendered_ids == []
        assert capsys.readouterr().out == ""

    def test_output_goes_to_stdout(self, seam, capsys):
        seam([task(7, "レビューする")])
        run(["list"])
        captured = capsys.readouterr()
        assert "レビューする" in captured.out
        assert captured.err == ""

    def test_list_does_not_write(self, seam):
        recorder = seam([task(1)])
        run(["list", "--all"])
        assert recorder.saved == []

    def test_invalid_priority_choice_is_rejected(self):
        with pytest.raises(SystemExit) as exc:
            cli.build_parser().parse_args(["list", "--priority", "urgent"])
        assert exc.value.code == 2


# --------------------------------------------------------------------------- #
# done（FR-3、US-5）
# --------------------------------------------------------------------------- #


class TestDone:
    def test_marks_task_done_and_saves(self, seam):
        recorder = seam([task(1), task(2)])
        assert run(["done", "2"]) == 0
        assert recorder.doc.tasks[1].done is True
        assert len(recorder.saved) == 1

    def test_does_not_remove_the_task(self, seam):
        recorder = seam([task(1)])
        run(["done", "1"])
        assert [t.id for t in recorder.doc] == [1]

    def test_already_done_warns_to_stderr_and_exits_zero(self, seam, capsys):
        recorder = seam([task(1, done=True)])
        assert run(["done", "1"]) == 0
        captured = capsys.readouterr()
        assert "1" in captured.err
        assert captured.out == ""
        # 冪等: 状態が変わらないのでファイルにも書かない。
        assert recorder.saved == []

    def test_missing_id_exits_nonzero_without_writing(self, seam, capsys):
        recorder = seam([task(1)])
        assert run(["done", "99"]) == 1
        assert recorder.saved == []
        captured = capsys.readouterr()
        assert "99" in captured.err
        assert captured.out == ""

    def test_non_integer_id_is_rejected_by_argparse(self):
        with pytest.raises(SystemExit) as exc:
            cli.build_parser().parse_args(["done", "abc"])
        assert exc.value.code == 2


# --------------------------------------------------------------------------- #
# rm（FR-4、US-5）
# --------------------------------------------------------------------------- #


class TestRm:
    def test_removes_task_and_saves(self, seam):
        recorder = seam([task(1), task(2), task(3)])
        assert run(["rm", "2"]) == 0
        assert [t.id for t in recorder.doc] == [1, 3]
        assert len(recorder.saved) == 1

    def test_missing_id_exits_nonzero_without_writing(self, seam, capsys):
        recorder = seam([task(1)])
        assert run(["rm", "99"]) == 1
        assert recorder.saved == []
        assert [t.id for t in recorder.doc] == [1]
        captured = capsys.readouterr()
        assert "99" in captured.err
        assert captured.out == ""

    def test_non_integer_id_is_rejected_by_argparse(self):
        with pytest.raises(SystemExit) as exc:
            cli.build_parser().parse_args(["rm", "abc"])
        assert exc.value.code == 2


# --------------------------------------------------------------------------- #
# パス解決（FR-6）
# --------------------------------------------------------------------------- #


class TestResolvePath:
    def test_uses_env_var_when_set(self, monkeypatch):
        monkeypatch.setenv(cli.TASK_FILE_ENV, "/somewhere/else/MY_TASKS.md")
        assert str(cli.resolve_path()) == "/somewhere/else/MY_TASKS.md"

    def test_falls_back_to_tasks_md(self, monkeypatch):
        monkeypatch.delenv(cli.TASK_FILE_ENV, raising=False)
        assert str(cli.resolve_path()) == "TASKS.md"

    def test_empty_env_var_falls_back(self, monkeypatch):
        monkeypatch.setenv(cli.TASK_FILE_ENV, "")
        assert str(cli.resolve_path()) == "TASKS.md"


# --------------------------------------------------------------------------- #
# シームの契約（Issue #9 がここを実装呼び出しに置き換える）
# --------------------------------------------------------------------------- #


class TestSeam:
    @pytest.mark.parametrize(
        "name", ["_load", "_save", "_tasks", "_next_id", "_append", "_remove", "_render"]
    )
    def test_seam_functions_exist_at_module_level(self, name):
        assert callable(getattr(cli, name))

    def test_cli_does_not_import_store_or_render(self):
        source = (cli.__file__ or "")
        with open(source, encoding="utf-8") as handle:
            code = handle.read()
        assert "import taskcli.store" not in code
        assert "from taskcli.store" not in code
        assert "from taskcli.render" not in code
        assert "import taskcli.render" not in code
