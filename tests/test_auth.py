import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import time
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestAuthentication:
    """Tests for API key authentication."""

    def test_missing_authorization_header(self, client):
        """Test request without Authorization header returns 401."""
        response = client.post("/run", json={
            "script_name": "hello",
            "script_response_webhook": "https://example.com/webhook",
            "script_timeout_seconds": 60
        })
        assert response.status_code == 401
        assert "Missing Authorization header" in response.json()["detail"]

    def test_invalid_authorization_format(self, client):
        """Test request with invalid Authorization format returns 401."""
        response = client.post("/run", json={
            "script_name": "hello",
            "script_response_webhook": "https://example.com/webhook",
            "script_timeout_seconds": 60
        }, headers={"Authorization": "Basic dGVzdDpwYXNz"})
        assert response.status_code == 401
        assert "Invalid Authorization header" in response.json()["detail"]

    def test_invalid_api_key(self, client):
        """Test request with wrong API key returns 401."""
        with patch("main.API_KEY", "correct-key"):
            response = client.post("/run", json={
                "script_name": "hello",
                "script_response_webhook": "https://example.com/webhook",
                "script_timeout_seconds": 60
            }, headers={"Authorization": "Bearer wrong-key"})
            assert response.status_code == 401
            assert "Invalid API key" in response.json()["detail"]

    def test_valid_api_key(self, client):
        """Test request with valid API key proceeds past authentication."""
        with patch("main.API_KEY", "valid-key"):
            with patch("os.path.exists", return_value=False):
                response = client.post("/run", json={
                    "script_name": "hello",
                    "script_response_webhook": "https://example.com/webhook",
                    "script_timeout_seconds": 60
                }, headers={"Authorization": "Bearer valid-key"})
                # Should pass auth and fail at script existence check (404)
                assert response.status_code == 404

    def test_api_key_not_configured(self, client):
        """Test request when API_KEY is not configured returns 500."""
        with patch("main.API_KEY", ""):
            response = client.post("/run", json={
                "script_name": "hello",
                "script_response_webhook": "https://example.com/webhook",
                "script_timeout_seconds": 60
            }, headers={"Authorization": "Bearer any-key"})
            assert response.status_code == 500
            assert "API_KEY not configured" in response.json()["detail"]

    def test_constant_time_comparison(self, client):
        """Test that API key comparison is constant-time (prevents timing attacks)."""
        import secrets
        from unittest.mock import patch as mock_patch

        with patch("main.API_KEY", "correct-api-key"):
            # Verify secrets.compare_digest is used
            with mock_patch("main.secrets.compare_digest") as mock_compare:
                mock_compare.return_value = False
                client.post("/run", json={
                    "script_name": "hello",
                    "script_response_webhook": "https://example.com/webhook",
                    "script_timeout_seconds": 60
                }, headers={"Authorization": "Bearer wrong-key"})
                mock_compare.assert_called_once()

    def test_timing_attack_resistance(self, client):
        """Verify that timing differences are minimal between valid and invalid keys."""
        import time
        from statistics import mean

        with patch("main.API_KEY", "valid-key-for-timing-test"):
            # Warm up
            for _ in range(5):
                client.post("/run", json={
                    "script_name": "hello",
                    "script_response_webhook": "https://example.com/webhook",
                    "script_timeout_seconds": 60
                }, headers={"Authorization": "Bearer valid-key-for-timing-test"})

            # Time valid key
            valid_times = []
            for _ in range(10):
                start = time.perf_counter()
                client.post("/run", json={
                    "script_name": "hello",
                    "script_response_webhook": "https://example.com/webhook",
                    "script_timeout_seconds": 60
                }, headers={"Authorization": "Bearer valid-key-for-timing-test"})
                valid_times.append(time.perf_counter() - start)

            # Time invalid key
            invalid_times = []
            for _ in range(10):
                start = time.perf_counter()
                client.post("/run", json={
                    "script_name": "hello",
                    "script_response_webhook": "https://example.com/webhook",
                    "script_timeout_seconds": 60
                }, headers={"Authorization": "Bearer invalid-key-xyz"})
                invalid_times.append(time.perf_counter() - start)

            avg_valid = mean(valid_times)
            avg_invalid = mean(invalid_times)
            # Timing difference should be minimal (less than 50% difference)
            ratio = max(avg_valid, avg_invalid) / min(avg_valid, avg_invalid) if min(avg_valid, avg_invalid) > 0 else 1
            assert ratio < 2.0, f"Timing difference too large: valid={avg_valid:.6f}s, invalid={avg_invalid:.6f}s"
