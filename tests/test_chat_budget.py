from fplcore.chat.budget import clear_old_tool_results, estimate_tokens, trim_history
from fplcore.chat.prompt import PROMPT_VERSION, SYSTEM_PROMPT, ContextView, SquadRow, render_context
from fplcore.chat.types import Message, ToolCall


def test_prompt_stays_inside_its_budget() -> None:
    assert PROMPT_VERSION
    tokens = estimate_tokens(SYSTEM_PROMPT)
    assert tokens < 1600


def test_old_tool_results_become_stubs() -> None:
    messages = [
        Message(role="user", content="first", turn_index=1),
        Message(role="tool", content='{"ok":true,"data":{"secret":1}}', name="get_player", tool_call_id="a", turn_index=1),
        Message(role="assistant", content="answer one", turn_index=1),
        Message(role="user", content="second", turn_index=2),
        Message(role="assistant", content="answer two", turn_index=2),
        Message(role="user", content="third", turn_index=3),
        Message(role="tool", content='{"ok":true}', name="get_fixtures", tool_call_id="b", turn_index=3),
    ]
    cleared = clear_old_tool_results(messages, keep_turns=2)
    old = next(message for message in cleared if message.tool_call_id == "a")
    fresh = next(message for message in cleared if message.tool_call_id == "b")
    assert "cleared" in old.content
    assert "secret" not in old.content
    assert fresh.content == '{"ok":true}'


def test_trim_keeps_the_first_turn_and_the_tail() -> None:
    messages = []
    for index in range(1, 8):
        messages.append(Message(role="user", content="word " * 80, turn_index=index))
        messages.append(Message(role="assistant", content="reply " * 80, turn_index=index))
    trimmed = trim_history(messages, budget=200, keep_last_turns=3)
    indexes = [message.turn_index for message in trimmed if message.role == "user"]
    assert indexes[0] == 1
    assert indexes[-3:] == [5, 6, 7]


def test_context_block_has_ids_and_no_instructions() -> None:
    text = render_context(
        ContextView(
            season_id="2026/27",
            decision_gw=9,
            decision_name="Gameweek 9",
            deadline_utc="2026-10-31T10:00:00Z",
            hours_to_deadline=20,
            phase="pre_deadline",
            has_team=True,
            team_name="Danny FC",
            bank_m=0.6,
            free_transfers=1,
            snapshot_gw=8,
            snapshot_fetched_at="2026-10-25T05:12:00Z",
            starters=[SquadRow(12, "Haaland", "MCI", "FWD", 15.0, 7.4, "a")],
            captain_id=12,
            captain_name="Haaland",
            data_as_of="2026-10-25T05:10:00Z",
            data_version=412,
        )
    )
    assert "<context" in text
    assert "12 Haaland" in text
    assert "transfers for a later deadline are hidden" in text
    assert "ignore previous" not in text.lower()
    assert "entry_id" not in text


def test_assistant_tool_call_message_serialises() -> None:
    message = Message(
        role="assistant",
        content="",
        tool_calls=[ToolCall(id="c1", name="get_player", arguments={"player_id": 12}, raw_arguments='{"player_id":12}')],
    )
    payload = message.to_api()
    assert payload["tool_calls"][0]["function"]["name"] == "get_player"
    assert isinstance(payload["tool_calls"][0]["function"]["arguments"], str)
