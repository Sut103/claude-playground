"""Issue #9: 結線後の E2E テスト。

CLI をサブプロセスとして起動し、実ファイルに対する一連の操作が期待どおりの
標準出力・終了コード・ファイル内容を生むことを確認する。モックは使わない。

層内部の単体テストでは捕まえられない結線ミス（引数の受け渡し、``None`` の扱い、
終了コードの取りこぼし）を検出することが目的である。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def cli(*args, cwd: Path, tasks_file: Path) -> subprocess.CompletedProcess:
    """``python -m taskcli`` をサブプロセスで実行する。

    ``sys.executable`` を使うことで、テストを走らせている処理系と同じ Python が
    確実に選ばれる。``TASK_CLI_FILE`` で保存先を一時ディレクトリへ固定するため、
    リポジトリ直下に ``TASKS.md`` を作らない。
    """
    env = os.environ.copy()
    env["TASK_CLI_FILE"] = str(tasks_file)
    env["PYTHONPATH"] = str(REPO_ROOT)
    return subprocess.run(
        [sys.executable, "-m", "taskcli", *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def workspace(tmp_path):
    """空の作業ディレクトリと、まだ存在しないタスクファイルのパス。"""
    tasks = tmp_path / "TASKS.md"
    return tmp_path, tasks


def test_help_runs(workspace):
    cwd, tasks = workspace
    result = cli("--help", cwd=cwd, tasks_file=tasks)
    assert result.returncode == 0
    assert "add" in result.stdout and "list" in result.stdout


class TestMainFlow:
    """add → list → done → list → list --all → rm の通し（Success Criteria 2）。"""

    def test_full_lifecycle(self, workspace):
        cwd, tasks = workspace

        # --- add: ファイルが自動生成され、ID が表示される（US-1） ---
        added = cli("add", "リファクタする", "--priority", "high", "--tag", "refactor",
                    cwd=cwd, tasks_file=tasks)
        assert added.returncode == 0
        assert "1" in added.stdout
        assert tasks.exists(), "add でタスクファイルが自動生成されること（US-1）"

        # --- list: 追加したタスクが現れる ---
        listed = cli("list", cwd=cwd, tasks_file=tasks)
        assert listed.returncode == 0
        assert "リファクタする" in listed.stdout

        # --- done: 行は残り、チェックだけが付く（US-5） ---
        done = cli("done", "1", cwd=cwd, tasks_file=tasks)
        assert done.returncode == 0
        content = tasks.read_text(encoding="utf-8")
        assert "- [x]" in content
        assert "リファクタする" in content, "done は行を削除しない"

        # --- list: 既定では完了済みを出さない ---
        after_done = cli("list", cwd=cwd, tasks_file=tasks)
        assert after_done.returncode == 0
        assert "リファクタする" not in after_done.stdout

        # --- list --all: 完了済みも出す ---
        all_listed = cli("list", "--all", cwd=cwd, tasks_file=tasks)
        assert all_listed.returncode == 0
        assert "リファクタする" in all_listed.stdout

        # --- rm: 行が消える ---
        removed = cli("rm", "1", cwd=cwd, tasks_file=tasks)
        assert removed.returncode == 0
        assert "リファクタする" not in tasks.read_text(encoding="utf-8")

    def test_ids_do_not_get_reused_after_delete(self, workspace):
        """FR-5 / AD-2: 削除しても他タスクの ID は変わらず、番号も再利用しない。"""
        cwd, tasks = workspace
        for text in ("一つ目", "二つ目", "三つ目"):
            assert cli("add", text, cwd=cwd, tasks_file=tasks).returncode == 0
        assert cli("rm", "2", cwd=cwd, tasks_file=tasks).returncode == 0

        content = tasks.read_text(encoding="utf-8")
        assert "`#1`" in content and "`#3`" in content and "`#2`" not in content

        cli("add", "四つ目", cwd=cwd, tasks_file=tasks)
        assert "`#4`" in tasks.read_text(encoding="utf-8")


class TestErrorPaths:
    """異常系。いずれもファイルをバイト単位で変えないこと。"""

    @pytest.fixture
    def seeded(self, workspace):
        cwd, tasks = workspace
        cli("add", "既存のタスク", cwd=cwd, tasks_file=tasks)
        return cwd, tasks, tasks.read_bytes()

    def test_done_on_missing_id(self, seeded):
        cwd, tasks, before = seeded
        result = cli("done", "999", cwd=cwd, tasks_file=tasks)
        assert result.returncode != 0
        assert result.stderr.strip()
        assert tasks.read_bytes() == before

    def test_rm_on_missing_id(self, seeded):
        cwd, tasks, before = seeded
        result = cli("rm", "999", cwd=cwd, tasks_file=tasks)
        assert result.returncode != 0
        assert result.stderr.strip()
        assert tasks.read_bytes() == before

    def test_done_is_idempotent(self, seeded):
        """すでに完了しているタスクへの done は警告のみで成功（US-5）。"""
        cwd, tasks, _ = seeded
        assert cli("done", "1", cwd=cwd, tasks_file=tasks).returncode == 0
        after_first = tasks.read_bytes()

        second = cli("done", "1", cwd=cwd, tasks_file=tasks)
        assert second.returncode == 0, "冪等なので成功する"
        assert second.stderr.strip(), "警告は出す"
        assert second.stdout == "", "警告を stdout に出さない"
        assert tasks.read_bytes() == after_first

    @pytest.mark.parametrize("bad", ["2026-13-45", "tomorrow", "2026/08/20"])
    def test_invalid_due_rejected_without_touching_file(self, seeded, bad):
        cwd, tasks, before = seeded
        result = cli("add", "だめな期限", "--due", bad, cwd=cwd, tasks_file=tasks)
        assert result.returncode != 0
        assert tasks.read_bytes() == before

    def test_missing_file_list_is_not_an_error(self, workspace):
        """ファイルが無い状態の list は 0 で終わり、ファイルも作らない。"""
        cwd, tasks = workspace
        result = cli("list", cwd=cwd, tasks_file=tasks)
        assert result.returncode == 0
        assert not tasks.exists()


class TestHandEditRoundTrip:
    """手編集との往復（Success Criteria 4、AD-3）。"""

    HEADING = "## 今週"
    NOTE = "メモ: 仕様は要確認"

    def _seed_and_hand_edit(self, cwd: Path, tasks: Path) -> None:
        for text in ("一つ目", "二つ目", "三つ目"):
            cli("add", text, cwd=cwd, tasks_file=tasks)

        lines = tasks.read_text(encoding="utf-8").splitlines()
        task_lines = [line for line in lines if line.startswith("- [")]
        assert len(task_lines) == 3

        # 見出しを挿入し、自由記述行を挟み、タスクの順序を入れ替える。
        rewritten = [
            self.HEADING,
            task_lines[2],
            task_lines[0],
            self.NOTE,
            task_lines[1],
        ]
        tasks.write_text("\n".join(rewritten) + "\n", encoding="utf-8")

    def test_list_still_reads_every_task_after_hand_edit(self, workspace):
        cwd, tasks = workspace
        self._seed_and_hand_edit(cwd, tasks)

        result = cli("list", cwd=cwd, tasks_file=tasks)
        assert result.returncode == 0
        for text in ("一つ目", "二つ目", "三つ目"):
            assert text in result.stdout

    def test_hand_written_lines_survive_cli_operations(self, workspace):
        cwd, tasks = workspace
        self._seed_and_hand_edit(cwd, tasks)

        assert cli("add", "四つ目", cwd=cwd, tasks_file=tasks).returncode == 0
        assert cli("done", "1", cwd=cwd, tasks_file=tasks).returncode == 0
        assert cli("rm", "2", cwd=cwd, tasks_file=tasks).returncode == 0

        content = tasks.read_text(encoding="utf-8")
        assert self.HEADING in content, "手書きの見出しが残ること（AD-3）"
        assert self.NOTE in content, "手書きのメモが残ること（AD-3）"
        assert "四つ目" in content
        assert "二つ目" not in content, "rm した行だけが消えること"

    def test_broken_line_warns_but_does_not_abort(self, workspace):
        """パース不能行があっても list は落ちない（US-2、FR-8）。"""
        cwd, tasks = workspace
        cli("add", "正常なタスク", cwd=cwd, tasks_file=tasks)
        original = tasks.read_text(encoding="utf-8")
        tasks.write_text(original + "- [?] 壊れた行 `#99`\n", encoding="utf-8")

        result = cli("list", cwd=cwd, tasks_file=tasks)
        assert result.returncode == 0, "異常終了しない"
        assert "正常なタスク" in result.stdout, "残りのタスクは表示される"

        # 警告は stderr に出し、stdout を汚さない。
        assert "壊れた行" not in result.stdout

    def test_broken_line_is_preserved_verbatim(self, workspace):
        cwd, tasks = workspace
        cli("add", "正常なタスク", cwd=cwd, tasks_file=tasks)
        broken = "- [?] 壊れた行 `#99`"
        tasks.write_text(tasks.read_text(encoding="utf-8") + broken + "\n", encoding="utf-8")

        assert cli("add", "もう一件", cwd=cwd, tasks_file=tasks).returncode == 0
        assert broken in tasks.read_text(encoding="utf-8"), "壊れた行も原文のまま残る（AD-3）"


class TestGeneratedMarkdown:
    """生成される Markdown が人間にとって妥当であること（US-2、NFR-5）。"""

    def test_lines_are_gfm_checklist_items(self, workspace):
        cwd, tasks = workspace
        cli("add", "やること", "--priority", "high", "--tag", "docs",
            "--due", "2026-08-20", cwd=cwd, tasks_file=tasks)

        line = tasks.read_text(encoding="utf-8").strip()
        assert line == "- [ ] やること `#1` `!high` `@docs` `~2026-08-20`"

    def test_file_ends_with_exactly_one_newline(self, workspace):
        cwd, tasks = workspace
        cli("add", "やること", cwd=cwd, tasks_file=tasks)
        content = tasks.read_text(encoding="utf-8")
        assert content.endswith("\n") and not content.endswith("\n\n")
