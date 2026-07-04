import pytest
from unittest.mock import patch, MagicMock


def test_no_url_returns_false():
    from app.services.metrics_sidecar_client import emit_metrics_event

    with patch("os.getenv", return_value=""):
        result = emit_metrics_event({"event_type": "test"})
        assert result is False


def test_failed_request_returns_false():
    from app.services.metrics_sidecar_client import emit_metrics_event
    import requests

    with patch("os.getenv", return_value="http://localhost:9100"):
        with patch("requests.post", side_effect=requests.exceptions.RequestException("Connection refused")):
            result = emit_metrics_event({"event_type": "test"})
            assert result is False


def test_successful_request_returns_true():
    from app.services.metrics_sidecar_client import emit_metrics_event

    mock_response = MagicMock()
    mock_response.status_code = 202

    with patch("os.getenv", return_value="http://localhost:9100"):
        with patch("requests.post", return_value=mock_response):
            result = emit_metrics_event({"event_type": "test"})
            assert result is True


def test_non_202_response_returns_false():
    from app.services.metrics_sidecar_client import emit_metrics_event

    mock_response = MagicMock()
    mock_response.status_code = 500

    with patch("os.getenv", return_value="http://localhost:9100"):
        with patch("requests.post", return_value=mock_response):
            result = emit_metrics_event({"event_type": "test"})
            assert result is False


def test_empty_url_returns_false():
    from app.services.metrics_sidecar_client import emit_metrics_event

    with patch("os.getenv", return_value="   "):
        result = emit_metrics_event({"event_type": "test"})
        assert result is False