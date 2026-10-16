"""A scripted stand-in for an OpenAI-compatible client.

It returns pre-written replies, including tool calls, so each recipe's logic
can be tested end to end without a network connection or an API key.
"""

import itertools
import json
import threading
from types import SimpleNamespace

_ids = itertools.count(1)


def tool_call(name, **arguments):
    """One tool call the stand-in model will make."""
    return SimpleNamespace(
        id=f"call_{next(_ids)}",
        type="function",
        function=SimpleNamespace(name=name, arguments=json.dumps(arguments)),
    )


def reply(content=None, tool_calls=None):
    """One assistant reply, shaped like the OpenAI SDK's response object."""
    message = SimpleNamespace(role="assistant", content=content, tool_calls=tool_calls or None)
    return SimpleNamespace(
        choices=[SimpleNamespace(message=message, finish_reason="tool_calls" if tool_calls else "stop")],
        usage=SimpleNamespace(prompt_tokens=100, completion_tokens=50, total_tokens=150),
    )


class FakeClient:
    """Pass a list of replies, or a function that builds a reply from the request.

    Every request is recorded in `.requests` so tests can inspect what was sent.
    """

    def __init__(self, script):
        self._script = script if callable(script) else iter(script)
        self.requests = []
        self._lock = threading.Lock()
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        with self._lock:
            self.requests.append(kwargs)
            if callable(self._script):
                return self._script(kwargs)
            try:
                return next(self._script)
            except StopIteration:
                raise AssertionError("The recipe made more model calls than the test scripted.")
