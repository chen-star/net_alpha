from __future__ import annotations

from collections.abc import Callable
from typing import Any

MAX_ITERATIONS = 10


def run_react_turn(
    client: Any,
    model: str,
    system_prompt: str,
    messages: list[dict],
    tool_schemas: list[dict],
    tool_executor: Callable[[str, dict], str],
) -> str:
    """
    Run one ReAct turn against the Claude API.

    Drives the tool-use loop: calls the API, dispatches tool_use blocks via
    tool_executor, appends results to messages, and loops until Claude returns
    an end_turn text response or the iteration cap is reached.

    Mutates `messages` in place — callers maintain conversation history
    by keeping a reference to the same list across turns.

    Returns the final text response string.
    """
    for _ in range(MAX_ITERATIONS):
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=system_prompt,
            tools=tool_schemas,
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            for block in response.content:
                if block.type == "text":
                    return block.text
            return ""

        if response.stop_reason == "tool_use":
            # Append assistant's full response (includes tool_use blocks)
            messages.append({"role": "assistant", "content": response.content})

            # Execute all tool_use blocks and collect results
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = tool_executor(block.name, block.input)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        }
                    )

            messages.append({"role": "user", "content": tool_results})
            continue

        return f"Unexpected API stop reason: {response.stop_reason}"

    # Iteration cap reached — ask Claude to summarize what it has
    messages.append(
        {
            "role": "user",
            "content": (
                "You have used the maximum number of tool calls. "
                "Please summarize what you have found so far and give your best answer."
            ),
        }
    )
    response = client.messages.create(
        model=model,
        max_tokens=1024,
        system=system_prompt,
        messages=messages,
    )
    for block in response.content:
        if block.type == "text":
            return block.text
    return "Unable to complete within iteration limit."
