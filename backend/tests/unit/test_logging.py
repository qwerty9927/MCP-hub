"""Log level colors: only for a terminal, never with NO_COLOR, and never leaking into the record."""

import io
import logging
import sys

import pytest

from app.core import logging as hub_logging
from app.core.logging import ColorLevelFormatter, _use_color, setup_logging


class Terminal(io.StringIO):
    def isatty(self) -> bool:
        return True


def record(level: int) -> logging.LogRecord:
    return logging.LogRecord("mcp_hub", level, __file__, 1, "hello", None, None)


@pytest.mark.parametrize(
    ("level", "code"),
    [(logging.DEBUG, "36"), (logging.INFO, "32"), (logging.WARNING, "33"), (logging.ERROR, "31"), (logging.CRITICAL, "1;31")],
)
def test_the_level_name_is_colored_and_the_record_left_unchanged(level, code):
    entry = record(level)

    line = ColorLevelFormatter("[%(levelname)s] %(message)s").format(entry)

    assert line == f"[\033[{code}m{logging.getLevelName(level)}\033[0m] hello"
    assert entry.levelname == logging.getLevelName(level)  # other handlers still see plain text


def test_color_only_for_a_terminal_and_not_with_no_color(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    assert _use_color(Terminal()) is True
    assert _use_color(io.StringIO()) is False  # a pipe or file: Docker, CI, log collectors
    assert _use_color(object()) is False

    monkeypatch.setenv("NO_COLOR", "1")
    assert _use_color(Terminal()) is False


def test_setup_logging_writes_plain_text_unless_stderr_is_a_terminal(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    root = logging.getLogger()
    saved_handlers, saved_level = root.handlers[:], root.level
    try:
        monkeypatch.setattr(sys, "stderr", io.StringIO())
        setup_logging()
        [handler] = root.handlers
        assert type(handler.formatter) is logging.Formatter

        terminal = Terminal()
        monkeypatch.setattr(sys, "stderr", terminal)
        setup_logging()
        [handler] = root.handlers
        assert isinstance(handler.formatter, ColorLevelFormatter)
        hub_logging.logger.warning("careful")
        assert "\033[33mWARNING\033[0m" in terminal.getvalue()
    finally:
        root.handlers = saved_handlers
        root.setLevel(saved_level)
