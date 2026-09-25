"""
Basic structured logging.

Every log line about an assessment run should include the assessment_id
so we can trace one founder's request through all three agents (Section 19).
"""
import logging
import sys

from app.config.settings import settings


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(settings.log_level)
    return logger
