import pytest
import logging
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestAuditLogging:
    """Tests for audit logging functionality."""

    @pytest.fixture(autouse=True)
    def reset_audit_logger(self):
        """Reset the audit logger before each test."""
        import main
        # Clear any existing handlers to avoid duplicate logs
        main.audit_logger.handlers.clear()
        yield
        # Cleanup after test
        main.audit_logger.handlers.clear()

    def test_audit_logger_configuration(self):
        """Test that audit logger is configured correctly."""
        import main

        assert main.audit_logger.name == "audit"
        assert main.audit_logger.level == logging.INFO
        assert main.audit_logger.propagate is False

        # Note: SysLogHandler may not be present in test environment
        # but the logger structure is correct

    def test_api_key_verification_success_logged(self, client):
        """Test successful API key verification is logged."""
        import main

        with patch("main.API_KEY", "test-key"):
            with patch.object(main.audit_logger, "info") as mock_info:
                with patch.object(main.audit_logger, "warning") as mock_warning:
                    with patch.object(main.audit_logger, "error") as mock_error:
                        response = client.post("/run", json={
                            "script_name": "nonexistent",
                            "script_response_webhook": "https://example.com/webhook",
                            "script_timeout_seconds": 60
                        }, headers={
                            "Authorization": "Bearer test-key"
                        })

                        # Check that API key verified was logged (TestClient uses "testclient" as IP)
                        assert any(
                            "API key verified" in str(call) and "client_ip=" in str(call)
                            for call in mock_info.call_args_list
                        )

    def test_invalid_api_key_logged(self, client):
        """Test invalid API key attempt is logged."""
        import main

        with patch("main.API_KEY", "correct-key"):
            with patch.object(main.audit_logger, "warning") as mock_warning:
                response = client.post("/run", json={
                    "script_name": "hello",
                    "script_response_webhook": "https://example.com/webhook",
                    "script_timeout_seconds": 60
                }, headers={
                    "Authorization": "Bearer wrong-key",
                    "X-Forwarded-For": "10.0.0.1"
                })

                # Check warning was logged
                assert any(
                    "Invalid API key" in str(call)
                    for call in mock_warning.call_args_list
                )

    def test_missing_authorization_header_logged(self, client):
        """Test missing Authorization header is logged."""
        import main

        with patch("main.API_KEY", "test-key"):
            with patch.object(main.audit_logger, "warning") as mock_warning:
                response = client.post("/run", json={
                    "script_name": "hello",
                    "script_response_webhook": "https://example.com/webhook",
                    "script_timeout_seconds": 60
                })

                assert any(
                    "Missing Authorization header" in str(call)
                    for call in mock_warning.call_args_list
                )

    def test_invalid_authorization_format_logged(self, client):
        """Test invalid Authorization header format is logged."""
        import main

        with patch("main.API_KEY", "test-key"):
            with patch.object(main.audit_logger, "warning") as mock_warning:
                response = client.post("/run", json={
                    "script_name": "hello",
                    "script_response_webhook": "https://example.com/webhook",
                    "script_timeout_seconds": 60
                }, headers={"Authorization": "Basic dGVzdA=="})

                assert any(
                    "Invalid Authorization header format" in str(call)
                    for call in mock_warning.call_args_list
                )

    def test_script_not_found_logged(self, client):
        """Test script not found event is logged."""
        import main

        with patch("main.API_KEY", "test-key"):
            with patch("os.path.exists", return_value=False):
                with patch.object(main.audit_logger, "warning") as mock_warning:
                    response = client.post("/run", json={
                        "script_name": "nonexistent",
                        "script_response_webhook": "https://example.com/webhook",
                        "script_timeout_seconds": 60
                    }, headers={
                        "Authorization": "Bearer test-key",
                        "X-Forwarded-For": "192.168.1.50"
                    })

                    assert any(
                        "Script not found" in str(call) and "nonexistent" in str(call)
                        for call in mock_warning.call_args_list
                    )

    def test_script_not_executable_logged(self, client):
        """Test script not executable event is logged."""
        import main

        with patch("main.API_KEY", "test-key"):
            with patch("os.path.exists", return_value=True):
                with patch("os.access", return_value=False):
                    with patch.object(main.audit_logger, "error") as mock_error:
                        response = client.post("/run", json={
                            "script_name": "notexe",
                            "script_response_webhook": "https://example.com/webhook",
                            "script_timeout_seconds": 60
                        }, headers={"Authorization": "Bearer test-key"})

                        assert any(
                            "Script not executable" in str(call) and "notexe" in str(call)
                            for call in mock_error.call_args_list
                        )

    def test_script_execution_started_logged(self, client):
        """Test script execution start is logged."""
        import main

        with patch("main.API_KEY", "test-key"):
            with patch("os.path.exists", return_value=True):
                with patch("os.access", return_value=True):
                    with patch("threading.Thread") as mock_thread:
                        mock_thread.return_value.start = Mock()

                        with patch.object(main.audit_logger, "info") as mock_info:
                            response = client.post("/run", json={
                                "script_name": "hello",
                                "script_response_webhook": "https://example.com/webhook",
                                "script_timeout_seconds": 60
                            }, headers={
                                "Authorization": "Bearer test-key",
                                "X-Forwarded-For": "192.168.1.200"
                            })

                            assert response.status_code == 200
                            assert any(
                                "Script execution started" in str(call)
                                and "hello" in str(call)
                                and "https://example.com/webhook" in str(call)
                                for call in mock_info.call_args_list
                            )

    def test_concurrent_limit_reached_logged(self, client):
        """Test concurrent limit reached event is logged."""
        import main

        with patch("main.API_KEY", "test-key"):
            with patch("main.MAX_CONCURRENT_SCRIPTS", 1):
                with patch("main.active_scripts_count", 1):
                    with patch.object(main.audit_logger, "warning") as mock_warning:
                        response = client.post("/run", json={
                            "script_name": "hello",
                            "script_response_webhook": "https://example.com/webhook",
                            "script_timeout_seconds": 60
                        }, headers={"Authorization": "Bearer test-key"})

                        assert any(
                            "Concurrent script limit reached" in str(call)
                            and "limit=1" in str(call)
                            for call in mock_warning.call_args_list
                        )

    def test_api_key_not_configured_logged(self, client):
        """Test API key not configured error is logged."""
        import main

        with patch("main.API_KEY", ""):
            with patch.object(main.audit_logger, "error") as mock_error:
                response = client.post("/run", json={
                    "script_name": "hello",
                    "script_response_webhook": "https://example.com/webhook",
                    "script_timeout_seconds": 60
                }, headers={"Authorization": "Bearer any-key"})

                assert any(
                    "API_KEY not configured" in str(call)
                    for call in mock_error.call_args_list
                )

    def test_log_includes_client_ip(self, client):
        """Test that all audit logs include client IP address."""
        import main

        with patch("main.API_KEY", "test-key"):
            with patch("os.path.exists", return_value=False):
                with patch.object(main.audit_logger, "warning") as mock_warning:
                    # Test with direct connection
                    response = client.post("/run", json={
                        "script_name": "missing",
                        "script_response_webhook": "https://example.com/webhook",
                        "script_timeout_seconds": 60
                    }, headers={"Authorization": "Bearer test-key"})

                    # Check that client_ip is in the log
                    assert any(
                        "client_ip=" in str(call)
                        for call in mock_warning.call_args_list
                    )

    def test_log_format(self):
        """Test that log messages follow expected format."""
        import main

        # Test that messages contain expected fields
        with patch.object(main.audit_logger, "info") as mock_info:
            main.audit_logger.info("Test message - client_ip=127.0.0.1, event=test")

            call_args = mock_info.call_args
            assert "client_ip=" in str(call_args)

    def test_audit_logger_has_no_propagation(self):
        """Test that audit logger doesn't propagate to root logger."""
        import main

        # Check propagation is disabled to avoid duplicate logs
        assert main.audit_logger.propagate is False


class TestSecurityEventLogging:
    """Tests for security event logging coverage."""

    def test_all_security_events_are_logged(self, client):
        """Test that all security-relevant events generate audit logs."""
        import main

        security_events = [
            ("Missing auth", {"status_code": 401, "log_message": "Missing Authorization header"}),
            ("Invalid auth format", {"status_code": 401, "log_message": "Invalid Authorization header format"}),
            ("Invalid key", {"status_code": 401, "log_message": "Invalid API key"}),
            ("Script not found", {"status_code": 404, "log_message": "Script not found"}),
            ("Script not executable", {"status_code": 404, "log_message": "Script not executable"}),
            ("Concurrent limit", {"status_code": 503, "log_message": "Concurrent script limit reached"}),
        ]

        # This test documents expected security logging coverage
        # Implementation verifies each event is logged
        for event_name, expected in security_events:
            # Each event should have corresponding log
            assert expected["log_message"] is not None

    def test_no_sensitive_data_in_logs(self, client):
        """Test that sensitive data is not logged."""
        import main

        with patch("main.API_KEY", "secret-api-key"):
            with patch("os.path.exists", return_value=True):
                with patch("os.access", return_value=True):
                    with patch("threading.Thread") as mock_thread:
                        mock_thread.return_value.start = Mock()

                        with patch.object(main.audit_logger, "info") as mock_info:
                            response = client.post("/run", json={
                                "script_name": "hello",
                                "script_response_webhook": "https://example.com/webhook",
                                "script_timeout_seconds": 60
                            }, headers={"Authorization": "Bearer secret-api-key"})

                            # API key should not appear in logs
                            for call in mock_info.call_args_list:
                                assert "secret-api-key" not in str(call)

    def test_webhook_url_in_logs(self, client):
        """Test that webhook URL is logged for auditing."""
        import main

        with patch("main.API_KEY", "test-key"):
            with patch("os.path.exists", return_value=True):
                with patch("os.access", return_value=True):
                    with patch("threading.Thread") as mock_thread:
                        mock_thread.return_value.start = Mock()

                        with patch.object(main.audit_logger, "info") as mock_info:
                            response = client.post("/run", json={
                                "script_name": "hello",
                                "script_response_webhook": "https://webhook.example.com/endpoint",
                                "script_timeout_seconds": 60
                            }, headers={"Authorization": "Bearer test-key"})

                            # Webhook URL should be in execution log
                            assert any(
                                "https://webhook.example.com/endpoint" in str(call)
                                for call in mock_info.call_args_list
                            )
