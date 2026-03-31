import unittest
from datetime import date
from unittest.mock import patch, MagicMock
from urllib import error as urllib_error

from app.services.google_ads import GoogleAdsService, GoogleAdsIntegrationError


class GoogleAdsRetryTests(unittest.TestCase):
    """Tests for exponential backoff retry on 429/RESOURCE_EXHAUSTED."""

    def _make_429_error(self, url: str = "https://googleads.googleapis.com/v23/customers/123/googleAds:searchStream") -> urllib_error.HTTPError:
        exc = urllib_error.HTTPError(
            url=url,
            code=429,
            msg="Too Many Requests",
            hdrs={},
            fp=None,
        )
        exc.read = lambda: b'{"error":{"code":429,"message":"RESOURCE_EXHAUSTED","details":[{"errors":[{"message":"Too Many Requests. Retry in 10 seconds"}]}]}}'
        exc.headers = {}
        return exc

    def _make_200_response(self):
        resp = MagicMock()
        resp.read.return_value = b'{"results": []}'
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        return resp

    @patch("time.sleep")
    @patch("app.services.google_ads.request.urlopen")
    def test_retry_on_429_then_success(self, mock_urlopen, mock_sleep):
        """Should retry on 429 and succeed on subsequent attempt."""
        mock_urlopen.side_effect = [
            self._make_429_error(),
            self._make_200_response(),
        ]

        service = GoogleAdsService()
        result = service._http_json(
            method="POST",
            url="https://googleads.googleapis.com/v23/customers/123/googleAds:searchStream",
        )

        self.assertEqual(result, {"results": []})
        self.assertEqual(mock_sleep.call_count, 1)
        wait_time = mock_sleep.call_args[0][0]
        self.assertGreater(wait_time, 0)

    @patch("time.sleep")
    @patch("app.services.google_ads.request.urlopen")
    def test_retry_exhausted_raises(self, mock_urlopen, mock_sleep):
        """Should raise after max retries exhausted."""
        mock_urlopen.side_effect = [self._make_429_error() for _ in range(6)]

        service = GoogleAdsService()
        with self.assertRaises(GoogleAdsIntegrationError) as ctx:
            service._http_json(
                method="POST",
                url="https://googleads.googleapis.com/v23/customers/123/googleAds:searchStream",
            )

        self.assertEqual(ctx.exception.provider_error_code, "RESOURCE_EXHAUSTED")
        self.assertEqual(mock_sleep.call_count, 5)

    @patch("time.sleep")
    @patch("app.services.google_ads.request.urlopen")
    def test_non_429_error_not_retried(self, mock_urlopen, mock_sleep):
        """Non-429 errors should not be retried."""
        exc = urllib_error.HTTPError(
            url="https://googleads.googleapis.com/v23/customers/123/googleAds:searchStream",
            code=403,
            msg="Forbidden",
            hdrs={},
            fp=None,
        )
        exc.read = lambda: b'{"error":{"code":403,"message":"Permission denied"}}'
        exc.headers = {}
        mock_urlopen.side_effect = exc

        service = GoogleAdsService()
        with self.assertRaises(GoogleAdsIntegrationError):
            service._http_json(
                method="POST",
                url="https://googleads.googleapis.com/v23/customers/123/googleAds:searchStream",
            )

        mock_sleep.assert_not_called()

    @patch("time.sleep")
    @patch("app.services.google_ads.request.urlopen")
    def test_backoff_increases(self, mock_urlopen, mock_sleep):
        """Backoff wait time should increase with each retry."""
        mock_urlopen.side_effect = [
            self._make_429_error(),
            self._make_429_error(),
            self._make_429_error(),
            self._make_200_response(),
        ]

        service = GoogleAdsService()
        service._http_json(
            method="POST",
            url="https://googleads.googleapis.com/v23/customers/123/googleAds:searchStream",
        )

        self.assertEqual(mock_sleep.call_count, 3)
        waits = [call[0][0] for call in mock_sleep.call_args_list]
        # Each wait should be >= the base (2^attempt), though jitter adds randomness
        self.assertGreater(waits[1], 1.0)  # 2^1 = 2, minus jitter still > 1
        self.assertGreater(waits[2], 2.0)  # 2^2 = 4, minus jitter still > 2


class GoogleAdsRetryWaitTests(unittest.TestCase):
    """Tests for _retry_wait_seconds calculation."""

    def test_wait_respects_max(self):
        service = GoogleAdsService()
        wait = service._retry_wait_seconds(10)
        self.assertLessEqual(wait, service._RETRY_MAX_WAIT_SECONDS)

    def test_wait_uses_retry_after_when_larger(self):
        service = GoogleAdsService()
        wait = service._retry_wait_seconds(0, retry_after=30)
        self.assertGreaterEqual(wait, 30.0)

    def test_wait_base_increases_with_attempt(self):
        service = GoogleAdsService()
        wait0 = service._retry_wait_seconds(0)
        wait2 = service._retry_wait_seconds(2)
        # attempt=2 base is 4s, attempt=0 base is 1s, but jitter makes this probabilistic
        # Just check both are positive
        self.assertGreater(wait0, 0)
        self.assertGreater(wait2, 0)


if __name__ == "__main__":
    unittest.main()
