"""
Pre-scripted mock LLM client. Zero API cost. Zero latency.
Used by all mock agent scenario tests.
"""
from __future__ import annotations


class MockLLMClient:
    """
    Usage:
        client = MockLLMClient(
            script=["Hello!", "I'll send the email.", "Done."],
            token_counts=[(100, 20), (200, 50), (150, 30)],
        )
        response, in_tok, out_tok = client.complete("Say hello")
    """

    def __init__(
        self,
        script: list[str],
        token_counts: list[tuple[int, int]] | None = None,
    ):
        self._script = list(script)
        self._token_counts = list(token_counts) if token_counts else [
            (100, 20) for _ in script
        ]
        self._index = 0

    def complete(self, prompt: str) -> tuple[str, int, int]:
        """Returns (response_text, input_tokens, output_tokens)."""
        if self._index >= len(self._script):
            raise StopIteration("MockLLMClient script exhausted")
        response = self._script[self._index]
        in_tok, out_tok = self._token_counts[self._index]
        self._index += 1
        return response, in_tok, out_tok

    @property
    def calls_made(self) -> int:
        return self._index
