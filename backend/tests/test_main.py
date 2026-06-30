"""Tests for FastAPI application setup."""

import logging


def test_app_services_logger_allows_info_logs() -> None:
    from app.main import configure_application_logging

    logging.getLogger("app.services").setLevel(logging.NOTSET)

    configure_application_logging()

    assert logging.getLogger("app.services").isEnabledFor(logging.INFO)
