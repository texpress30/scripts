from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.api import public_feeds as public_feeds_module
from app.api.public_feeds import _check_rate_limit, _parse_token_and_ext, _rate_log, router


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_TOKEN = "a" * 64  # 64-char hex token


def _make_feed(*, token=_VALID_TOKEN, s3_key="feeds/1/f1/feed.xml", status="published"):
    return {
        "id": "feed-1",
        "subaccount_id": 1,
        "name": "Test Feed",
        "feed_source_id": "src-1",
        "status": status,
        "feed_format": "xml",
        "public_token": token,
        "s3_key": s3_key,
        "products_count": 42,
        "last_generated_at": "2026-04-01T12:00:00+00:00",
    }


# ---------------------------------------------------------------------------
# Token parsing
# ---------------------------------------------------------------------------

class TestParseTokenAndExt:
    def test_valid_xml(self):
        token, ext = _parse_token_and_ext(f"{_VALID_TOKEN}.xml")
        assert token == _VALID_TOKEN
        assert ext == "xml"

    def test_valid_json(self):
        token, ext = _parse_token_and_ext(f"{_VALID_TOKEN}.json")
        assert ext == "json"

    def test_valid_csv(self):
        token, ext = _parse_token_and_ext(f"{_VALID_TOKEN}.csv")
        assert ext == "csv"

    def test_invalid_extension(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            _parse_token_and_ext(f"{_VALID_TOKEN}.pdf")
        assert exc_info.value.status_code == 404

    def test_no_dot(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            _parse_token_and_ext("nodothere")

    def test_short_token(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            _parse_token_and_ext("short.xml")
        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

class TestRateLimit:
    def setup_method(self):
        _rate_log.clear()

    def test_allows_under_limit(self):
        for _ in range(99):
            assert _check_rate_limit("test-token") is True

    def test_blocks_over_limit(self):
        for _ in range(100):
            _check_rate_limit("test-token")
        assert _check_rate_limit("test-token") is False

    def test_independent_per_token(self):
        for _ in range(100):
            _check_rate_limit("token-a")
        # token-b should still be allowed
        assert _check_rate_limit("token-b") is True


# ---------------------------------------------------------------------------
# Public feed endpoint
# ---------------------------------------------------------------------------

class TestGetPublicFeed:
    def test_serve_valid_feed(self):
        feed = _make_feed()
        mock_service = MagicMock()
        mock_service.get_output_feed_by_token.return_value = feed

        mock_s3 = MagicMock()
        mock_s3.get_object.return_value = {
            "Body": MagicMock(read=lambda: b"<products></products>")
        }

        _rate_log.clear()

        with patch.object(public_feeds_module, "output_feed_service", mock_service), \
             patch("app.services.s3_provider.get_s3_client", return_value=mock_s3), \
             patch("app.services.s3_provider.get_s3_bucket_name", return_value="test-bucket"):
            from app.api.public_feeds import get_public_feed
            response = get_public_feed(f"{_VALID_TOKEN}.xml")

        assert response.status_code == 200
        assert b"<products>" in response.body
        assert response.media_type == "application/xml; charset=utf-8"
        assert "Cache-Control" in response.headers

    def test_404_invalid_token(self):
        mock_service = MagicMock()
        mock_service.get_output_feed_by_token.return_value = None

        _rate_log.clear()

        with patch.object(public_feeds_module, "output_feed_service", mock_service):
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                from app.api.public_feeds import get_public_feed
                get_public_feed(f"{_VALID_TOKEN}.xml")
            assert exc_info.value.status_code == 404

    def test_404_no_s3_key(self):
        feed = _make_feed(s3_key=None)
        mock_service = MagicMock()
        mock_service.get_output_feed_by_token.return_value = feed

        _rate_log.clear()

        with patch.object(public_feeds_module, "output_feed_service", mock_service):
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                from app.api.public_feeds import get_public_feed
                get_public_feed(f"{_VALID_TOKEN}.xml")
            assert exc_info.value.status_code == 404

    def test_rate_limited(self):
        _rate_log.clear()
        # Exhaust rate limit
        for _ in range(100):
            _check_rate_limit(_VALID_TOKEN)

        mock_service = MagicMock()
        with patch.object(public_feeds_module, "output_feed_service", mock_service):
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                from app.api.public_feeds import get_public_feed
                get_public_feed(f"{_VALID_TOKEN}.xml")
            assert exc_info.value.status_code == 429

    def test_json_content_type(self):
        feed = _make_feed()
        mock_service = MagicMock()
        mock_service.get_output_feed_by_token.return_value = feed

        mock_s3 = MagicMock()
        mock_s3.get_object.return_value = {
            "Body": MagicMock(read=lambda: b'[{"id":"1"}]')
        }

        _rate_log.clear()

        with patch.object(public_feeds_module, "output_feed_service", mock_service), \
             patch("app.services.s3_provider.get_s3_client", return_value=mock_s3), \
             patch("app.services.s3_provider.get_s3_bucket_name", return_value="test-bucket"):
            from app.api.public_feeds import get_public_feed
            response = get_public_feed(f"{_VALID_TOKEN}.json")

        assert response.media_type == "application/json; charset=utf-8"

    def test_csv_content_type(self):
        feed = _make_feed()
        mock_service = MagicMock()
        mock_service.get_output_feed_by_token.return_value = feed

        mock_s3 = MagicMock()
        mock_s3.get_object.return_value = {
            "Body": MagicMock(read=lambda: b"id,title\n1,Shoes")
        }

        _rate_log.clear()

        with patch.object(public_feeds_module, "output_feed_service", mock_service), \
             patch("app.services.s3_provider.get_s3_client", return_value=mock_s3), \
             patch("app.services.s3_provider.get_s3_bucket_name", return_value="test-bucket"):
            from app.api.public_feeds import get_public_feed
            response = get_public_feed(f"{_VALID_TOKEN}.csv")

        assert response.media_type == "text/csv; charset=utf-8"
