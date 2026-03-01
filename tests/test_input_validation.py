import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestInputValidation:
    """Tests for input validation including script name, webhook, and timeout."""

    class TestScriptNameValidation:
        """Tests for script name validation."""

        def test_valid_script_name_alphanumeric(self, client):
            """Test valid alphanumeric script names are accepted."""
            import main

            with patch("main.API_KEY", "test-key"):
                with patch("os.path.exists", return_value=False):
                    with patch("main.active_scripts_count", 0):
                        response = client.post("/run", json={
                            "script_name": "validscript123",
                            "script_response_webhook": "https://example.com/webhook",
                            "script_timeout_seconds": 60
                        }, headers={"Authorization": "Bearer test-key"})
                        # Should pass validation, fail at script existence
                        assert response.status_code == 404

        def test_valid_script_name_with_underscore(self, client):
            """Test script names with underscores are accepted."""
            import main

            with patch("main.API_KEY", "test-key"):
                with patch("os.path.exists", return_value=False):
                    with patch("main.active_scripts_count", 0):
                        response = client.post("/run", json={
                            "script_name": "valid_script",
                            "script_response_webhook": "https://example.com/webhook",
                            "script_timeout_seconds": 60
                        }, headers={"Authorization": "Bearer test-key"})
                        assert response.status_code == 404

        def test_valid_script_name_with_dash(self, client):
            """Test script names with dashes are accepted."""
            import main

            with patch("main.API_KEY", "test-key"):
                with patch("os.path.exists", return_value=False):
                    with patch("main.active_scripts_count", 0):
                        response = client.post("/run", json={
                            "script_name": "valid-script",
                            "script_response_webhook": "https://example.com/webhook",
                            "script_timeout_seconds": 60
                        }, headers={"Authorization": "Bearer test-key"})
                        assert response.status_code == 404

        def test_invalid_script_name_with_dot(self, client):
            """Test script names with dots are rejected (path traversal)."""
            with patch("main.API_KEY", "test-key"):
                response = client.post("/run", json={
                    "script_name": "../etc/passwd",
                    "script_response_webhook": "https://example.com/webhook",
                    "script_timeout_seconds": 60
                }, headers={"Authorization": "Bearer test-key"})
                assert response.status_code == 422
                assert "script_name" in str(response.json()).lower()

        def test_invalid_script_name_with_slash(self, client):
            """Test script names with slashes are rejected."""
            with patch("main.API_KEY", "test-key"):
                response = client.post("/run", json={
                    "script_name": "scripts/malicious",
                    "script_response_webhook": "https://example.com/webhook",
                    "script_timeout_seconds": 60
                }, headers={"Authorization": "Bearer test-key"})
                assert response.status_code == 422

        def test_invalid_script_name_with_special_chars(self, client):
            """Test script names with special characters are rejected."""
            with patch("main.API_KEY", "test-key"):
                invalid_names = [
                    "script;rm -rf",
                    "script\u0026\u0026malicious",
                    "script|cat",
                    "script$(whoami)",
                    "script`id`"
                ]
                for name in invalid_names:
                    response = client.post("/run", json={
                        "script_name": name,
                        "script_response_webhook": "https://example.com/webhook",
                        "script_timeout_seconds": 60
                    }, headers={"Authorization": "Bearer test-key"})
                    assert response.status_code == 422, f"Expected 422 for script_name: {name}"

        def test_empty_script_name(self, client):
            """Test empty script names are rejected."""
            with patch("main.API_KEY", "test-key"):
                response = client.post("/run", json={
                    "script_name": "",
                    "script_response_webhook": "https://example.com/webhook",
                    "script_timeout_seconds": 60
                }, headers={"Authorization": "Bearer test-key"})
                assert response.status_code == 422

        def test_unicode_in_script_name(self, client):
            """Test Unicode characters in script names are rejected."""
            with patch("main.API_KEY", "test-key"):
                response = client.post("/run", json={
                    "script_name": "scrípt-ñame",
                    "script_response_webhook": "https://example.com/webhook",
                    "script_timeout_seconds": 60
                }, headers={"Authorization": "Bearer test-key"})
                assert response.status_code == 422

    class TestWebhookValidation:
        """Tests for webhook URL validation."""

        def test_valid_https_webhook(self, client):
            """Test valid HTTPS webhook URLs are accepted."""
            import main

            with patch("main.API_KEY", "test-key"):
                with patch("os.path.exists", return_value=False):
                    with patch("main.active_scripts_count", 0):
                        response = client.post("/run", json={
                            "script_name": "hello",
                            "script_response_webhook": "https://example.com/webhook",
                            "script_timeout_seconds": 60
                        }, headers={"Authorization": "Bearer test-key"})
                        assert response.status_code == 404  # Passes validation, fails at script

        def test_invalid_http_webhook(self, client):
            """Test HTTP (non-HTTPS) webhook URLs are rejected."""
            with patch("main.API_KEY", "test-key"):
                response = client.post("/run", json={
                    "script_name": "hello",
                    "script_response_webhook": "http://example.com/webhook",
                    "script_timeout_seconds": 60
                }, headers={"Authorization": "Bearer test-key"})
                assert response.status_code == 422
                assert "https" in str(response.json()).lower()

        def test_invalid_ftp_webhook(self, client):
            """Test FTP webhook URLs are rejected."""
            with patch("main.API_KEY", "test-key"):
                response = client.post("/run", json={
                    "script_name": "hello",
                    "script_response_webhook": "ftp://example.com/webhook",
                    "script_timeout_seconds": 60
                }, headers={"Authorization": "Bearer test-key"})
                assert response.status_code == 422

        def test_invalid_file_webhook(self, client):
            """Test file:// webhook URLs are rejected (SSRF prevention)."""
            with patch("main.API_KEY", "test-key"):
                response = client.post("/run", json={
                    "script_name": "hello",
                    "script_response_webhook": "file:///etc/passwd",
                    "script_timeout_seconds": 60
                }, headers={"Authorization": "Bearer test-key"})
                assert response.status_code == 422

        def test_invalid_webhook_no_scheme(self, client):
            """Test webhook URLs without scheme are rejected."""
            with patch("main.API_KEY", "test-key"):
                response = client.post("/run", json={
                    "script_name": "hello",
                    "script_response_webhook": "example.com/webhook",
                    "script_timeout_seconds": 60
                }, headers={"Authorization": "Bearer test-key"})
                assert response.status_code == 422

        def test_invalid_webhook_no_netloc(self, client):
            """Test webhook URLs without netloc are rejected."""
            with patch("main.API_KEY", "test-key"):
                response = client.post("/run", json={
                    "script_name": "hello",
                    "script_response_webhook": "https:///path",
                    "script_timeout_seconds": 60
                }, headers={"Authorization": "Bearer test-key"})
                assert response.status_code == 422

        def test_ssrf_internal_ip(self, client):
            """Test webhook URLs pointing to internal IPs (SSRF prevention concern)."""
            # Note: Currently the code only validates HTTPS, not internal IPs
            # This test documents the current behavior - SSRF protection may need enhancement
            with patch("main.API_KEY", "test-key"):
                with patch("os.path.exists", return_value=False):
                    internal_ips = [
                        "https://127.0.0.1/webhook",
                        "https://10.0.0.1/webhook",
                        "https://192.168.1.1/webhook",
                        "https://169.254.169.254/latest/meta-data/"  # AWS metadata
                    ]
                    for ip in internal_ips:
                        response = client.post("/run", json={
                            "script_name": "hello",
                            "script_response_webhook": ip,
                            "script_timeout_seconds": 60
                        }, headers={"Authorization": "Bearer test-key"})
                        # Currently accepts these - may want to add SSRF protection
                        assert response.status_code in [404, 503]  # Passes validation

        def test_empty_webhook(self, client):
            """Test empty webhook URLs are rejected."""
            with patch("main.API_KEY", "test-key"):
                response = client.post("/run", json={
                    "script_name": "hello",
                    "script_response_webhook": "",
                    "script_timeout_seconds": 60
                }, headers={"Authorization": "Bearer test-key"})
                assert response.status_code == 422

    class TestTimeoutValidation:
        """Tests for script timeout validation."""

        def test_valid_timeout(self, client):
            """Test valid positive timeouts are accepted."""
            import main

            with patch("main.API_KEY", "test-key"):
                with patch("os.path.exists", return_value=False):
                    with patch("main.active_scripts_count", 0):
                        response = client.post("/run", json={
                            "script_name": "hello",
                            "script_response_webhook": "https://example.com/webhook",
                            "script_timeout_seconds": 60
                        }, headers={"Authorization": "Bearer test-key"})
                        assert response.status_code == 404  # Passes validation

        def test_zero_timeout(self, client):
            """Test zero timeout is rejected."""
            with patch("main.API_KEY", "test-key"):
                response = client.post("/run", json={
                    "script_name": "hello",
                    "script_response_webhook": "https://example.com/webhook",
                    "script_timeout_seconds": 0
                }, headers={"Authorization": "Bearer test-key"})
                assert response.status_code == 422
                assert "positive" in str(response.json()).lower()

        def test_negative_timeout(self, client):
            """Test negative timeout is rejected."""
            with patch("main.API_KEY", "test-key"):
                response = client.post("/run", json={
                    "script_name": "hello",
                    "script_response_webhook": "https://example.com/webhook",
                    "script_timeout_seconds": -1
                }, headers={"Authorization": "Bearer test-key"})
                assert response.status_code == 422

        def test_timeout_exceeds_maximum(self, client):
            """Test timeout exceeding MAX_SCRIPT_TIMEOUT_SECONDS is rejected."""
            with patch("main.API_KEY", "test-key"):
                with patch("main.MAX_SCRIPT_TIMEOUT_SECONDS", 3600):
                    response = client.post("/run", json={
                        "script_name": "hello",
                        "script_response_webhook": "https://example.com/webhook",
                        "script_timeout_seconds": 7200  # Exceeds max
                    }, headers={"Authorization": "Bearer test-key"})
                    assert response.status_code == 422
                    assert "3600" in str(response.json())

        def test_timeout_at_maximum(self, client):
            """Test timeout exactly at maximum is accepted."""
            import main

            with patch("main.API_KEY", "test-key"):
                with patch("main.MAX_SCRIPT_TIMEOUT_SECONDS", 3600):
                    with patch("os.path.exists", return_value=False):
                        with patch("main.active_scripts_count", 0):
                            response = client.post("/run", json={
                                "script_name": "hello",
                                "script_response_webhook": "https://example.com/webhook",
                                "script_timeout_seconds": 3600
                            }, headers={"Authorization": "Bearer test-key"})
                            assert response.status_code == 404  # Passes validation

        def test_extremely_large_timeout(self, client):
            """Test extremely large timeout (overflow attempt) is rejected."""
            with patch("main.API_KEY", "test-key"):
                response = client.post("/run", json={
                    "script_name": "hello",
                    "script_response_webhook": "https://example.com/webhook",
                    "script_timeout_seconds": 2147483647
                }, headers={"Authorization": "Bearer test-key"})
                assert response.status_code == 422

    def test_missing_request_fields(self, client):
        """Test request with missing required fields."""
        with patch("main.API_KEY", "test-key"):
            # Missing script_name
            response = client.post("/run", json={
                "script_response_webhook": "https://example.com/webhook",
                "script_timeout_seconds": 60
            }, headers={"Authorization": "Bearer test-key"})
            assert response.status_code == 422

    def test_invalid_json_body(self, client):
        """Test request with invalid JSON body."""
        with patch("main.API_KEY", "test-key"):
            response = client.post("/run", data="not json", headers={
                "Authorization": "Bearer test-key",
                "Content-Type": "application/json"
            })
            assert response.status_code == 422

    def test_extra_fields_in_request(self, client):
        """Test request with extra unexpected fields."""
        with patch("main.API_KEY", "test-key"):
            with patch("os.path.exists", return_value=False):
                response = client.post("/run", json={
                    "script_name": "hello",
                    "script_response_webhook": "https://example.com/webhook",
                    "script_timeout_seconds": 60,
                    "extra_field": "should be ignored"
                }, headers={"Authorization": "Bearer test-key"})
                # Pydantic by default ignores extra fields
                assert response.status_code == 404
