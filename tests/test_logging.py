import logging

from sime_mcp.logging_utils import RedactingFilter


def test_sensitive_fields_are_redacted():
    record = logging.makeLogRecord(
        {
            "msg": "request %s cookie=abc session=xyz salt=123",
            "args": ("https://agenda.sime.md/ords/wwv_flow.ajax?p_context=secret",),
        }
    )
    assert RedactingFilter().filter(record)
    message = record.getMessage()
    assert "abc" not in message
    assert "xyz" not in message
    assert "secret" not in message
    assert "123" not in message
