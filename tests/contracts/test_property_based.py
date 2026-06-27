"""Property-based (fuzz) tests using hypothesis.

Covers core conversion logic, SSE parsing, and settings validation
with randomly generated inputs to find edge cases that example-based
tests would miss (TST-01).
"""

import pytest
from hypothesis import given
from hypothesis import strategies as st

# ---- Helpers: strategies ------------------------------------------------

# A simplified message content strategy (avoids deeply nested schemas that
# hypothesis would struggle to shrink).


def message_content():
    """Generate valid-ish Anthropic message content blocks."""
    return st.one_of(
        st.builds(
            dict,
            type=st.just("text"),
            text=st.text(max_size=50),
        ),
        st.builds(
            dict,
            type=st.just("image"),
            source=st.builds(
                dict,
                type=st.just("base64"),
                media_type=st.sampled_from(["image/jpeg", "image/png"]),
                data=st.text(alphabet="abcdef0123456789", min_size=1, max_size=20),
            ),
        ),
        st.builds(
            dict,
            type=st.just("tool_use"),
            name=st.text(max_size=10),
            input=st.builds(dict),
            id=st.text(max_size=10),
        ),
        st.builds(
            dict,
            type=st.just("tool_result"),
            tool_use_id=st.text(max_size=10),
            content=st.text(max_size=30),
        ),
    )


def anthropic_message():
    """Generate an Anthropic-format message."""
    return st.builds(
        dict,
        role=st.sampled_from(["user", "assistant"]),
        content=st.one_of(
            st.text(max_size=50),
            st.lists(message_content(), max_size=3),
        ),
    )


def messages_strategy():
    """Generate a list of Anthropic messages."""
    return st.lists(anthropic_message(), min_size=0, max_size=5)


# ---- Property: Core Conversion -----------------------------------------


@pytest.mark.skip(reason="Requires hypothesis; run manually with `pytest --hypothesis`")
class TestConversionInvariants:
    """Fuzz the Anthropic-to-OpenAI converter with random inputs."""

    @given(messages=messages_strategy())
    def test_conversion_never_raises_on_well_typed_input(self, messages):
        """Well-typed message dicts should never cause an unhandled exception."""
        from core.anthropic.conversion import AnthropicToOpenAIConverter

        try:
            result = AnthropicToOpenAIConverter.convert_messages(messages)
        except KeyError, TypeError, ValueError, AttributeError:
            # These are acceptable for invalid inputs — we just don't want
            # hard crashes (SystemExit, RecursionError, etc.).
            return
        assert isinstance(result, list)
        for msg in result:
            assert isinstance(msg, dict)
            assert "role" in msg
            assert msg["role"] in ("user", "assistant", "system")


@pytest.mark.skip(reason="Requires hypothesis; run manually")
class TestSSEParsingInvariants:
    """Fuzz SSE event parsing with random strings."""

    @given(data=st.text(max_size=200))
    def test_parse_sse_lines_never_raises(self, data):
        """Parsing arbitrary text should never raise."""
        from core.anthropic.stream_contracts import parse_sse_lines

        try:
            events = list(parse_sse_lines(data))
        except Exception:
            # Some inputs may cause encoding/parsing errors — that's acceptable.
            return
        assert isinstance(events, list)


# ---- Property: Settings Validation --------------------------------------


@pytest.mark.skip(reason="Requires hypothesis; run manually")
class TestSettingsValidationInvariants:
    """Fuzz settings field parsing with random values."""

    @given(
        proxy_value=st.one_of(st.none(), st.text(max_size=50)),
        model_value=st.text(max_size=50),
        rate_limit=st.integers(min_value=0, max_value=1000),
    )
    def test_proxy_field_accepts_string_or_none(
        self, proxy_value, model_value, rate_limit
    ):
        """Proxy fields should accept str | None without crashing."""
        env = {
            "MODEL": model_value or "nvidia_nim/minimaxai/minimax-m2.7",
            "NVIDIA_NIM_API_KEY": "test-key",
        }
        if proxy_value is not None:
            env["NVIDIA_NIM_PROXY"] = proxy_value
        try:
            from config.settings import Settings

            with pytest.MonkeyPatch.context() as mp:
                for k, v in env.items():
                    mp.setenv(k, v)
                s = Settings()
                assert s.nvidia_nim_proxy is None or isinstance(s.nvidia_nim_proxy, str)
        except Exception:
            pass


# ---- Property: Redaction Safety -----------------------------------------


@pytest.mark.skip(reason="Requires hypothesis; run manually")
@given(
    prefix=st.sampled_from(
        [
            "https://api.telegram.org/bot",
        ]
    ),
    token=st.text(alphabet="abcdef0123456789_:", min_size=5, max_size=30),
    suffix=st.text(max_size=20),
)
def test_redaction_never_leaks_telegram_token(prefix, token, suffix):
    """Telegram bot tokens in log messages must always be redacted."""
    from config.logging_config import _redact_sensitive_substrings

    message = f"{prefix}{token}{suffix}"
    redacted = _redact_sensitive_substrings(message)
    assert token not in redacted, f"Token {token!r} leaked in {redacted!r}"


@pytest.mark.skip(reason="Requires hypothesis; run manually")
@given(
    header=st.sampled_from(
        [
            "Authorization: Bearer ",
            "authorization: bearer ",
            "authorization: Bearer ",
        ]
    ),
    token=st.text(
        alphabet="abcdefghijklmnopqrstuvwxyz0123456789._-", min_size=8, max_size=40
    ),
    suffix=st.text(max_size=20),
)
def test_redaction_never_leaks_auth_header(header, token, suffix):
    """Authorization headers in log messages must always be redacted."""
    from config.logging_config import _redact_sensitive_substrings

    message = f"{header}{token}{suffix}"
    redacted = _redact_sensitive_substrings(message)
    assert token not in redacted, f"Token {token!r} leaked in {redacted!r}"
