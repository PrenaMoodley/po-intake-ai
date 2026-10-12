"""Test doubles for the Anthropic client.

The tests never call the real API. FakeClient replays scripted responses and
records every request, so we can assert on what our code sends.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from po_intake.reference import ReferenceData


def text_block(text: str):
    return SimpleNamespace(type="text", text=text)


def tool_use_block(id: str, name: str, input: dict):
    return SimpleNamespace(type="tool_use", id=id, name=name, input=input)


def response(content, stop_reason="end_turn", cache_read=0):
    usage = SimpleNamespace(
        input_tokens=100,
        output_tokens=50,
        cache_read_input_tokens=cache_read,
        cache_creation_input_tokens=0,
    )
    return SimpleNamespace(content=content, stop_reason=stop_reason, stop_details=None, usage=usage)


class FakeMessages:
    def __init__(self, scripted):
        self.scripted = list(scripted)
        self.requests = []

    def create(self, **kwargs):
        # Deep-ish copy of messages: our code mutates the list between calls.
        self.requests.append({**kwargs, "messages": list(kwargs["messages"])})
        return self.scripted.pop(0)


class FakeClient:
    def __init__(self, scripted):
        self.beta = SimpleNamespace(messages=FakeMessages(scripted))


@pytest.fixture
def ref() -> ReferenceData:
    return ReferenceData.load()
