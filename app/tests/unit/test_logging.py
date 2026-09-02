import json
import logging

from app.core.logging import JSONFormatter


def test_json_formatter_returns_valid_json():
    formatter = JSONFormatter()

    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Test message",
        args=(),
        exc_info=None,
    )

    output = formatter.format(record)
    payload = json.loads(output)

    assert payload["level"] == "INFO"
    assert payload["logger"] == "test_logger"
    assert payload["message"] == "Test message"
    assert "timestamp" in payload


def test_json_formatter_includes_exception():
    formatter = JSONFormatter()

    try:
        raise ValueError("Test failure")
    except ValueError:
        record = logging.LogRecord(
            name="test_logger",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="Something failed",
            args=(),
            exc_info=None,
        )
        record.exc_info = (
            ValueError,
            ValueError("Test failure"),
            None,
        )

    output = formatter.format(record)
    payload = json.loads(output)

    assert payload["level"] == "ERROR"
    assert payload["message"] == "Something failed"
    assert "exception" in payload