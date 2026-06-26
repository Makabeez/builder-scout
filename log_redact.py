"""
Logging filter that redacts CROO SDK keys and key= URL params from all log
records, so demo recordings never expose secrets. Import and call
install_redaction() once at startup, before creating the AgentClient.
"""

import logging
import re

# croo_sk_ followed by hex, OR key=<token> in a URL
_PATTERNS = [
    re.compile(r"croo_sk_[A-Za-z0-9]+"),
    re.compile(r"(key=)[A-Za-z0-9_]+"),
]


class _RedactFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
            redacted = msg
            redacted = _PATTERNS[0].sub("croo_sk_****REDACTED", redacted)
            redacted = _PATTERNS[1].sub(r"\1****REDACTED", redacted)
            if redacted != msg:
                record.msg = redacted
                record.args = ()
        except Exception:
            pass
        return True


def install_redaction() -> None:
    """Attach the redaction filter to the root logger and all handlers."""
    f = _RedactFilter()
    root = logging.getLogger()
    root.addFilter(f)
    for h in root.handlers:
        h.addFilter(f)
    # Also attach to the croo + httpx loggers specifically (they may add handlers)
    for name in ("croo", "httpx", "websockets"):
        logging.getLogger(name).addFilter(f)
