"""Issue #7: 表示層のテスト。

PRD の US-3（表示順）と US-4（期限切れの明示）に対応する。

**日付はすべて固定値で渡す**（AD-5）。``today=date(2026, 8, 20)`` のように明示的に
与えるため、テストを走らせた日が変わってもパス・フェイルは変化しない。
``date.today()`` に依存するテストや、``datetime`` のモンキーパッチは一切使わない。
"""

from datetime import date

from taskcli.parser import Priority, Task
from taskcli.render import (
    DUE_TODAY,
    OVERDUE,
    due_state,
    render_list,
    render_task,
    sort_tasks,
)

#: すべてのテストが基準にする「本日」。実行日とは無関係の固定値。
TODAY = date(2026, 8, 20)


def make_task(
    id: int = 1,
    text: str = "タスク",
    done: bool = False,
    priority: Priority = Priority.MID,
    tags: list[str] | None = None,
    due: date | None = None,
) -> Task:
    return Task(
        id=id,
        text=text,
        done=done,
        priority=priority,
        tags=list(tags) if tags else [],
        due=due,
    )


class TestSortTasks:
    def test_priority_descending(self):
        low = make_task(id=1, priority=Priority.LOW)
        high = make_task(id=2, priority=Priority.HIGH)
        mid = make_task(id=3, priority=Priority.MID)
        assert [t.id for t in sort_tasks([low, high, mid])] == [2, 3, 1]

    def test_due_ascending_within_same_priority(self):
        later = make_task(id=1, priority=Priority.HIGH, due=date(2026, 9, 1))
        earlier = make_task(id=2, priority=Priority.HIGH, due=date(2026, 8, 1))
        middle = make_task(id=3, priority=Priority.HIGH, due=date(2026, 8, 15))
        assert [t.id for t in sort_tasks([later, earlier, middle])] == [2, 3, 1]

    def test_tasks_without_due_go_last_within_their_priority_group(self):
        no_due = make_task(id=1, priority=Priority.HIGH, due=None)
        with_due = make_task(id=2, priority=Priority.HIGH, due=date(2026, 12, 31))
        assert [t.id for t in sort_tasks([no_due, with_due])] == [2, 1]

    def test_no_due_stays_within_its_own_priority_group(self):
        """期限なしは「全体の末尾」ではなく「同一優先度グループの末尾」に来る。"""
        high_no_due = make_task(id=1, priority=Priority.HIGH, due=None)
        mid_with_due = make_task(id=2, priority=Priority.MID, due=date(2026, 1, 1))
        low_no_due = make_task(id=3, priority=Priority.LOW, due=None)
        high_with_due = make_task(id=4, priority=Priority.HIGH, due=date(2026, 8, 20))
        ordered = sort_tasks([high_no_due, mid_with_due, low_no_due, high_with_due])
        assert [t.id for t in ordered] == [4, 1, 2, 3]

    def test_priority_outranks_due_date(self):
        """優先度が第 1 キーである。low の古い期限より high の遠い期限が先に来る。"""
        low_urgent = make_task(id=1, priority=Priority.LOW, due=date(2020, 1, 1))
        high_distant = make_task(id=2, priority=Priority.HIGH, due=date(2099, 12, 31))
        assert [t.id for t in sort_tasks([low_urgent, high_distant])] == [2, 1]

    def test_stable_for_equal_keys(self):
        """優先度も期限も等しい 2 件は入力順を保つ。"""
        first = make_task(id=9, priority=Priority.MID, due=date(2026, 8, 20))
        second = make_task(id=4, priority=Priority.MID, due=date(2026, 8, 20))
        third = make_task(id=7, priority=Priority.MID, due=date(2026, 8, 20))
        assert [t.id for t in sort_tasks([first, second, third])] == [9, 4, 7]

    def test_stable_for_equal_keys_without_due(self):
        first = make_task(id=9, priority=Priority.LOW, due=None)
        second = make_task(id=4, priority=Priority.LOW, due=None)
        assert [t.id for t in sort_tasks([first, second])] == [9, 4]

    def test_does_not_mutate_input(self):
        original = [
            make_task(id=1, priority=Priority.LOW),
            make_task(id=2, priority=Priority.HIGH),
        ]
        sort_tasks(original)
        assert [t.id for t in original] == [1, 2]

    def test_returns_new_list(self):
        tasks = [make_task(id=1)]
        assert sort_tasks(tasks) is not tasks

    def test_empty_list(self):
        assert sort_tasks([]) == []

    def test_done_flag_does_not_affect_order(self):
        """並び順は優先度と期限だけで決まる。完了状態はキーに入らない。"""
        done_high = make_task(id=1, priority=Priority.HIGH, done=True)
        open_low = make_task(id=2, priority=Priority.LOW, done=False)
        assert [t.id for t in sort_tasks([open_low, done_high])] == [1, 2]


class TestDueState:
    def test_overdue_when_due_before_today_and_not_done(self):
        task = make_task(due=date(2026, 8, 19), done=False)
        assert due_state(task, today=TODAY) == OVERDUE
        assert due_state(task, today=TODAY) == "OVERDUE"

    def test_due_today_when_due_equals_today(self):
        task = make_task(due=TODAY, done=False)
        assert due_state(task, today=TODAY) == DUE_TODAY
        assert due_state(task, today=TODAY) == "DUE TODAY"

    def test_none_when_due_after_today(self):
        assert due_state(make_task(due=date(2026, 8, 21)), today=TODAY) is None

    def test_none_when_no_due(self):
        assert due_state(make_task(due=None), today=TODAY) is None

    def test_none_when_done_even_if_overdue(self):
        """完了済みは期限切れとして扱わない（US-4）。"""
        task = make_task(due=date(2020, 1, 1), done=True)
        assert due_state(task, today=TODAY) is None

    def test_none_when_done_even_if_due_today(self):
        assert due_state(make_task(due=TODAY, done=True), today=TODAY) is None

    def test_far_past_due_is_overdue(self):
        assert due_state(make_task(due=date(1999, 12, 31)), today=TODAY) == OVERDUE

    def test_boundary_yesterday_today_tomorrow(self):
        assert due_state(make_task(due=date(2026, 8, 19)), today=TODAY) == OVERDUE
        assert due_state(make_task(due=date(2026, 8, 20)), today=TODAY) == DUE_TODAY
        assert due_state(make_task(due=date(2026, 8, 21)), today=TODAY) is None

    def test_today_is_a_parameter_not_a_frozen_default(self):
        """同じタスクでも ``today`` を変えれば結果が変わる（AD-5）。

        既定値が import 時に固定されていると、この 3 つは同じ値を返してしまう。
        """
        task = make_task(due=date(2026, 8, 20))
        assert due_state(task, today=date(2026, 8, 21)) == OVERDUE
        assert due_state(task, today=date(2026, 8, 20)) == DUE_TODAY
        assert due_state(task, today=date(2026, 8, 19)) is None

    def test_today_accepted_positionally(self):
        task = make_task(due=date(2026, 8, 19))
        assert due_state(task, TODAY) == OVERDUE

    def test_default_today_resolves_at_call_time(self):
        """``today`` 省略時は呼び出し時点の ``date.today()`` が使われる。

        実行日そのものには依存させない。「実行日より確実に過去／未来」という関係だけを
        使って、既定値が呼び出し時に解決されていることを確認する。
        """
        assert due_state(make_task(due=date(1970, 1, 1))) == OVERDUE
        assert due_state(make_task(due=date(9999, 12, 31))) is None


class TestRenderTask:
    def test_full_line_format(self):
        task = Task(
            id=3,
            text="リファクタする",
            done=False,
            priority=Priority.HIGH,
            tags=["docs", "refactor"],
            due=date(2026, 8, 20),
        )
        assert (
            render_task(task, today=date(2026, 8, 10))
            == "[ ] #3 リファクタする !high @docs @refactor ~2026-08-20"
        )

    def test_done_task_uses_x_checkbox(self):
        task = make_task(id=1, text="README を書く", done=True, priority=Priority.MID)
        assert render_task(task, today=TODAY) == "[x] #1 README を書く !mid"

    def test_open_task_uses_blank_checkbox(self):
        task = make_task(id=1, text="README を書く", done=False, priority=Priority.MID)
        assert render_task(task, today=TODAY) == "[ ] #1 README を書く !mid"

    def test_priority_always_shown_even_when_default(self):
        assert "!mid" in render_task(make_task(priority=Priority.MID), today=TODAY)

    def test_tags_omitted_when_empty(self):
        line = render_task(make_task(id=5, text="メモ", tags=[]), today=TODAY)
        assert line == "[ ] #5 メモ !mid"
        assert "@" not in line

    def test_due_omitted_when_none(self):
        line = render_task(make_task(id=5, text="メモ", due=None), today=TODAY)
        assert "~" not in line

    def test_tags_preserve_order(self):
        line = render_task(make_task(tags=["zeta", "alpha"]), today=TODAY)
        assert line.index("@zeta") < line.index("@alpha")

    def test_overdue_marker_appended_at_end(self):
        task = make_task(id=2, text="遅れている", due=date(2026, 8, 19))
        line = render_task(task, today=TODAY)
        assert line == "[ ] #2 遅れている !mid ~2026-08-19 << OVERDUE"
        assert line.endswith(OVERDUE)

    def test_due_today_marker_appended_at_end(self):
        task = make_task(id=2, text="今日まで", due=TODAY)
        line = render_task(task, today=TODAY)
        assert line == "[ ] #2 今日まで !mid ~2026-08-20 << DUE TODAY"

    def test_no_marker_for_future_due(self):
        task = make_task(id=2, text="まだ先", due=date(2026, 9, 1))
        line = render_task(task, today=TODAY)
        assert line == "[ ] #2 まだ先 !mid ~2026-09-01"
        assert OVERDUE not in line
        assert DUE_TODAY not in line

    def test_no_marker_for_done_overdue_task(self):
        task = make_task(id=2, text="済んでいる", done=True, due=date(2020, 1, 1))
        line = render_task(task, today=TODAY)
        assert line == "[x] #2 済んでいる !mid ~2020-01-01"
        assert OVERDUE not in line

    def test_contains_every_required_element(self):
        task = Task(
            id=42,
            text="全部入り",
            done=False,
            priority=Priority.LOW,
            tags=["ops"],
            due=date(2026, 8, 19),
        )
        line = render_task(task, today=TODAY)
        for fragment in ("#42", "[ ]", "全部入り", "!low", "@ops", "~2026-08-19", OVERDUE):
            assert fragment in line

    def test_single_line_no_newline(self):
        task = make_task(tags=["a", "b"], due=date(2026, 8, 19))
        assert "\n" not in render_task(task, today=TODAY)

    def test_no_ansi_escape_sequences(self):
        """カラー出力は PRD の Out of Scope。エスケープ文字を一切含めない。"""
        task = make_task(id=1, text="遅れ", priority=Priority.HIGH, tags=["x"], due=date(2020, 1, 1))
        line = render_task(task, today=TODAY)
        assert "\x1b" not in line
        assert "\033[" not in line

    def test_empty_text_does_not_produce_double_space(self):
        line = render_task(make_task(id=8, text=""), today=TODAY)
        assert line == "[ ] #8 !mid"
        assert "  " not in line

    def test_today_defaults_to_call_time(self):
        line = render_task(make_task(id=1, text="大昔", due=date(1970, 1, 1)))
        assert line.endswith(OVERDUE)


class TestRenderList:
    def test_empty_list_returns_empty_string_without_raising(self):
        assert render_list([], today=TODAY) == ""

    def test_single_task(self):
        task = make_task(id=1, text="ひとつ", priority=Priority.HIGH)
        assert render_list([task], today=TODAY) == "[ ] #1 ひとつ !high"

    def test_lines_joined_by_newline_without_trailing_newline(self):
        tasks = [make_task(id=1, text="A"), make_task(id=2, text="B")]
        out = render_list(tasks, today=TODAY)
        assert len(out.splitlines()) == 2
        assert not out.endswith("\n")

    def test_applies_sort_order(self):
        tasks = [
            make_task(id=1, text="低", priority=Priority.LOW),
            make_task(id=2, text="高", priority=Priority.HIGH),
            make_task(id=3, text="中", priority=Priority.MID),
        ]
        out = render_list(tasks, today=TODAY)
        assert out.splitlines() == [
            "[ ] #2 高 !high",
            "[ ] #3 中 !mid",
            "[ ] #1 低 !low",
        ]

    def test_full_scenario_matches_us3_and_us4(self):
        tasks = [
            make_task(id=1, text="期限なし高", priority=Priority.HIGH, due=None),
            make_task(id=2, text="期限切れ高", priority=Priority.HIGH, due=date(2026, 8, 1)),
            make_task(id=3, text="今日まで高", priority=Priority.HIGH, due=TODAY),
            make_task(id=4, text="中", priority=Priority.MID, due=date(2026, 8, 25)),
            make_task(id=5, text="完了低", priority=Priority.LOW, done=True, due=date(2020, 1, 1)),
        ]
        assert render_list(tasks, today=TODAY).splitlines() == [
            "[ ] #2 期限切れ高 !high ~2026-08-01 << OVERDUE",
            "[ ] #3 今日まで高 !high ~2026-08-20 << DUE TODAY",
            "[ ] #1 期限なし高 !high",
            "[ ] #4 中 !mid ~2026-08-25",
            "[x] #5 完了低 !low ~2020-01-01",
        ]

    def test_does_not_mutate_input(self):
        tasks = [
            make_task(id=1, priority=Priority.LOW),
            make_task(id=2, priority=Priority.HIGH),
        ]
        render_list(tasks, today=TODAY)
        assert [t.id for t in tasks] == [1, 2]

    def test_does_not_filter(self):
        """フィルタはコマンド層（Issue #8）の責務。渡されたものは全部出す。"""
        tasks = [make_task(id=1, done=True), make_task(id=2, done=False)]
        assert len(render_list(tasks, today=TODAY).splitlines()) == 2

    def test_no_ansi_escape_sequences(self):
        tasks = [
            make_task(id=1, priority=Priority.HIGH, due=date(2020, 1, 1)),
            make_task(id=2, priority=Priority.LOW, due=TODAY),
        ]
        assert "\x1b" not in render_list(tasks, today=TODAY)

    def test_today_is_threaded_through_to_each_line(self):
        tasks = [make_task(id=1, due=date(2026, 8, 20))]
        assert render_list(tasks, today=date(2026, 8, 20)).endswith(DUE_TODAY)
        assert render_list(tasks, today=date(2026, 8, 21)).endswith(OVERDUE)
        assert render_list(tasks, today=date(2026, 8, 19)).endswith("~2026-08-20")
