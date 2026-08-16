from __future__ import annotations

import json
import logging
import sys

logger = logging.getLogger("genar")

if not logger.handlers:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def emit(event: str, level: str = "info", **fields: object) -> None:
    getattr(logger, level)(json.dumps({"event": event, **fields}))
