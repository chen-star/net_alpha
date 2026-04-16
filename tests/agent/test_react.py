from __future__ import annotations

from unittest.mock import MagicMock

from net_alpha.agent.react import MAX_ITERATIONS, run_react_turn

# --- Test helpers ---


def _text_block(text: str) -> MagicMock:
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def _tool_use_block(name: str, input_: dict, id_: str = "tu_1") -> MagicMock:
    block = MagicMock()
    block.type = "tool_use"
    block.name = name
    block.input = input_
    block.id = id_
    return block


def _end_turn_response(text: str) -> MagicMock:
    resp = MagicMock()
    resp.stop_reason = "end_turn"
    resp.content = [_text_block(text)]
    return resp


def _tool_use_response(name: str, input_: dict, id_: str = "tu_1") -> MagicMock:
    resp = MagicMock()
    resp.stop_reason = "tool_use"
    resp.content = [_tool_use_block(name, input_, id_)]
    return resp


# --- Tests ---


def test_text_only_response_returned_immediately():
    client = MagicMock()
    client.messages.create.return_value = _end_turn_response("Hello world")
    messages = []
    result = run_react_turn(client, "model", "system", messages, [], lambda n, i: "")
    assert result == "Hello world"
    assert client.messages.create.call_count == 1


def test_single_tool_call_then_text_response():
    client = MagicMock()
    client.messages.create.side_effect = [
        _tool_use_response("run_status", {}),
        _end_turn_response("Status looks good."),
    ]
    messages = []
    executed = []

    def executor(name: str, inp: dict) -> str:
        executed.append((name, inp))
        return "status output"

    result = run_react_turn(client, "model", "system", messages, [], executor)
    assert result == "Status looks good."
    assert executed == [("run_status", {})]
    assert client.messages.create.call_count == 2


def test_tool_result_appended_to_messages():
    client = MagicMock()
    client.messages.create.side_effect = [
        _tool_use_response("run_check", {"ticker": "AAPL"}, id_="tu_abc"),
        _end_turn_response("Done."),
    ]
    messages = []
    run_react_turn(client, "model", "system", messages, [], lambda n, i: "check result")

    # messages should have: [assistant tool_use, user tool_result]
    assert len(messages) == 2
    assert messages[0]["role"] == "assistant"
    assert messages[1]["role"] == "user"
    tool_result_content = messages[1]["content"]
    assert tool_result_content[0]["type"] == "tool_result"
    assert tool_result_content[0]["tool_use_id"] == "tu_abc"
    assert tool_result_content[0]["content"] == "check result"


def test_tool_error_string_passed_to_claude():
    """Tool exceptions return error strings to Claude, not tracebacks."""
    client = MagicMock()
    client.messages.create.side_effect = [
        _tool_use_response("run_check", {}, id_="tu_err"),
        _end_turn_response("No data available."),
    ]
    messages = []
    run_react_turn(client, "model", "system", messages, [], lambda n, i: "Error: no trades imported")

    tool_result_msg = messages[1]
    assert tool_result_msg["content"][0]["content"] == "Error: no trades imported"


def test_multi_tool_chain():
    client = MagicMock()
    client.messages.create.side_effect = [
        _tool_use_response("run_status", {}, id_="tu_1"),
        _tool_use_response("run_check", {}, id_="tu_2"),
        _end_turn_response("All clear."),
    ]
    messages = []
    executed = []
    run_react_turn(client, "model", "system", messages, [], lambda n, i: executed.append(n) or "ok")

    assert executed == ["run_status", "run_check"]
    assert client.messages.create.call_count == 3


def test_max_iterations_cap_triggers_summary_call():
    """After MAX_ITERATIONS tool calls, a final summarization API call is made."""
    client = MagicMock()
    # Always return tool_use to saturate the cap
    client.messages.create.side_effect = [_tool_use_response("run_status", {})] * MAX_ITERATIONS + [
        _end_turn_response("Here is my summary.")
    ]
    messages = []
    result = run_react_turn(client, "model", "system", messages, [], lambda n, i: "")

    assert result == "Here is my summary."
    assert client.messages.create.call_count == MAX_ITERATIONS + 1


def test_second_api_call_includes_prior_messages():
    client = MagicMock()
    client.messages.create.side_effect = [
        _tool_use_response("run_status", {}, id_="tu_1"),
        _end_turn_response("Done."),
    ]
    messages = [{"role": "user", "content": "hello"}]
    run_react_turn(client, "model", "system", messages, [], lambda n, i: "out")

    second_call_kwargs = client.messages.create.call_args_list[1][1]
    second_messages = second_call_kwargs["messages"]
    # Should include: original user message + assistant tool_use + user tool_result
    assert len(second_messages) == 3
    assert second_messages[0]["content"] == "hello"
