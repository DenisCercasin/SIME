"""Conservative application logging. Never pass raw browser objects to a logger."""

import logging
import re
import sys

_SENSITIVE = re.compile(
    r"(?i)(?:https?://[^\s]+/ords/wwv_flow\.ajax[^\s]*|"
    r"(?:cookie|authorization|session|checksum|salt|p_instance|p_context)\s*[:=]\s*[^\s,;]+)"
)


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        rendered = record.getMessage()
        record.msg = _SENSITIVE.sub("[REDACTED]", rendered)
        record.args = ()
        return True


def configure_logging() -> None:
    logger = logging.getLogger("sime_mcp")
    logger.setLevel(logging.WARNING)
    logger.propagate = False
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.addFilter(RedactingFilter())
        handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        logger.addHandler(handler)
