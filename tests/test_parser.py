"""Issue #5: パーサ層のテスト。

PRD の US-2（AI エージェントが読める形式）と、エピックの Success Criteria
「parse_line と format_line の往復でタスク情報が保存される」に対応する。
"""

from datetime import date

import pytest

from taskcli.parser import DEFAULT_PRIORITY, Priority, Task, format_line, parse_due, parse_line


class TestParseLine:
    def test_full_metadata(self):
        line = "- [ ] リファクタする `#3` `!high` `@docs` `@refactor` `~2026-08-20`"
        task = parse_line(line)
        assert task == Task(
            id=3,
            text="リファクタする",
            done=False,
            priority=Priority.HIGH,
            tags=["docs", "refactor"],
            due=date(2026, 8, 20),
        )

    def test_checked_box(self):
        assert parse_line("- [x] 済 `#1` `!mid`").done is True

    def test_checked_box_uppercase(self):
        assert parse_line("- [X] 済 `#1` `!mid`").done is True

    def test_metadata_only_id_uses_default_priority(self):
        task = parse_line("- [ ] メモを書く `#7`")
        assert task.priority is DEFAULT_PRIORITY
        assert task.priority is Priority.MID
        assert task.tags == []
        assert task.due is None

    def test_tags_preserve_declaration_order(self):
        task = parse_line("- [ ] x `#1` `@b` `@a` `@c`")
        assert task.tags == ["b", "a", "c"]

    def test_text_is_trimmed_and_metadata_removed(self):
        task = parse_line("- [ ]   前後に空白   `#2` `!low`")
        assert task.text == "前後に空白"

    def test_hash_and_at_in_body_stay_in_text(self):
        task = parse_line("- [ ] issue #42 を @alice に聞く `#5`")
        assert task.text == "issue #42 を @alice に聞く"
        assert task.id == 5
        assert task.tags == []

    @pytest.mark.parametrize(
        "line",
        [
            "## 今週",
            "",
            "ふつうの段落テキスト",
            "- ふつうの項目",
            "- [ ] ID がない `!high`",
            "- [ ] 不正な優先度 `#1` `!urgent`",
            "- [ ] 未知のトークン `#1` `?foo`",
            "- [ ] 範囲外の日付 `#1` `~2026-13-45`",
            "- [ ] 存在しない日 `#1` `~2026-02-30`",
            "- [ ] 日付でない `#1` `~tomorrow`",
            "- [ ] 区切りが違う `#1` `~2026/08/20`",
            "- [ ] 桁数が違う `#1` `~26-08-20`",
            "- [ ] ID が数値でない `#abc`",
        ],
    )
    def test_unparseable_lines_return_none(self, line):
        assert parse_line(line) is None

    def test_does_not_raise_on_garbage(self):
        # 例外を投げないこと自体が仕様（AD-3）。
        for line in ["```", "| a | b |", "- [ ] `#`", "- [ ] `` "]:
            assert parse_line(line) is None


class TestParseDue:
    def test_valid(self):
        assert parse_due("2026-08-20") == date(2026, 8, 20)

    @pytest.mark.parametrize(
        "token", ["2026-13-45", "2026-02-30", "tomorrow", "2026/08/20", "26-08-20", "2026-8-20"]
    )
    def test_invalid(self, token):
        assert parse_due(token) is None


class TestFormatLine:
    def test_metadata_order_is_fixed(self):
        task = Task(
            id=3,
            text="やる",
            priority=Priority.HIGH,
            tags=["a", "b"],
            due=date(2026, 8, 20),
        )
        assert format_line(task) == "- [ ] やる `#3` `!high` `@a` `@b` `~2026-08-20`"

    def test_omits_absent_metadata(self):
        assert format_line(Task(id=1, text="x")) == "- [ ] x `#1` `!mid`"

    def test_priority_always_emitted_even_when_default(self):
        assert "`!mid`" in format_line(Task(id=1, text="x", priority=Priority.MID))

    def test_done_renders_checked_box(self):
        assert format_line(Task(id=1, text="x", done=True)).startswith("- [x] ")

    def test_no_newline_in_output(self):
        assert "\n" not in format_line(Task(id=1, text="x", due=date(2026, 1, 1)))


ROUND_TRIP_CASES = [
    Task(1, "全部入り", True, Priority.HIGH, ["a", "b", "c"], date(2026, 8, 20)),
    Task(2, "タグなし", False, Priority.LOW, [], date(2026, 1, 1)),
    Task(3, "期限なし", False, Priority.MID, ["x"], None),
    Task(4, "メタデータ最小", False, Priority.MID, [], None),
    Task(5, "日本語の本文をそのまま保つ", False, Priority.HIGH, [], None),
    Task(6, "記号 !? * & % 混じり", False, Priority.LOW, ["sym"], None),
    Task(7, "完了済み", True, Priority.MID, [], date(2026, 12, 31)),
]


class TestRoundTrip:
    @pytest.mark.parametrize("task", ROUND_TRIP_CASES, ids=lambda t: f"id{t.id}")
    def test_parse_of_format_returns_equal_task(self, task):
        assert parse_line(format_line(task)) == task

    def test_format_of_parse_returns_canonical_input(self):
        line = "- [x] やる `#9` `!low` `@ops` `~2026-03-04`"
        assert format_line(parse_line(line)) == line

    def test_tag_order_survives_round_trip(self):
        task = Task(id=1, text="x", tags=["z", "a", "m"])
        assert parse_line(format_line(task)).tags == ["z", "a", "m"]


class TestPriority:
    def test_sort_rank_orders_high_first(self):
        ranks = [Priority.HIGH.sort_rank, Priority.MID.sort_rank, Priority.LOW.sort_rank]
        assert ranks == sorted(ranks)
        assert Priority.HIGH.sort_rank < Priority.LOW.sort_rank

    def test_from_token_rejects_unknown(self):
        assert Priority.from_token("urgent") is None
        assert Priority.from_token("high") is Priority.HIGH
