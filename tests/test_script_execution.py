import pytest
import time
import threading
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock, MagicMock
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestScriptExecution:
    """Tests for script execution and concurrency."""

    def test_script_not_found(self, client):
        """Test 404 returned when script does not exist."""
        with patch("main.API_KEY", "test-key"):
            with patch("os.path.exists", return_value=False):
                response = client.post("/run", json={
                    "script_name": "nonexistent",
                    "script_response_webhook": "https://example.com/webhook",
                    "script_timeout_seconds": 60
                }, headers={"Authorization": "Bearer test-key"})
                assert response.status_code == 404
                assert "not found" in response.json()["detail"].lower()

    def test_script_not_executable(self, client):
        """Test 404 returned when script exists but is not executable."""
        with patch("main.API_KEY", "test-key"):
            with patch("os.path.exists", return_value=True):
                with patch("os.access", return_value=False):
                    response = client.post("/run", json={
                        "script_name": "notexecutable",
                        "script_response_webhook": "https://example.com/webhook",
                        "script_timeout_seconds": 60
                    }, headers={"Authorization": "Bearer test-key"})
                    # Both missing and non-executable return 404
                    assert response.status_code == 404

    def test_information_disclosure_prevention(self, client):
        """Test that 404 is returned for both missing and non-executable scripts."""
        with patch("main.API_KEY", "test-key"):
            # Test missing script
            with patch("os.path.exists", return_value=False):
                response_missing = client.post("/run", json={
                    "script_name": "missing",
                    "script_response_webhook": "https://example.com/webhook",
                    "script_timeout_seconds": 60
                }, headers={"Authorization": "Bearer test-key"})

            # Test non-executable script
            with patch("os.path.exists", return_value=True):
                with patch("os.access", return_value=False):
                    response_not_executable = client.post("/run", json={
                        "script_name": "notexe",
                        "script_response_webhook": "https://example.com/webhook",
                        "script_timeout_seconds": 60
                    }, headers={"Authorization": "Bearer test-key"})

            # Both should return 404 (same status prevents information disclosure)
            assert response_missing.status_code == 404
            assert response_not_executable.status_code == 404
            # Both should have "not found" message (may include script name)
            assert "not found" in response_missing.json()["detail"].lower()
            assert "not found" in response_not_executable.json()["detail"].lower()

    def test_concurrent_script_limit_reached(self, client):
        """Test 503 returned when concurrent script limit is reached."""
        with patch("main.API_KEY", "test-key"):
            with patch("main.MAX_CONCURRENT_SCRIPTS", 1):
                with patch("main.active_scripts_count", 1):
                    response = client.post("/run", json={
                        "script_name": "hello",
                        "script_response_webhook": "https://example.com/webhook",
                        "script_timeout_seconds": 60
                    }, headers={"Authorization": "Bearer test-key"})
                    assert response.status_code == 503
                    assert "limit reached" in response.json()["detail"].lower()

    def test_concurrent_script_counter_incremented(self, client):
        """Test active_scripts_count is incremented when script starts and blocks subsequent requests at limit."""
        import main
        import threading

        # Save the real Thread class before any patches
        RealThread = threading.Thread

        with patch("main.API_KEY", "test-key"):
            with patch("main.MAX_CONCURRENT_SCRIPTS", 1):
                with patch("main.active_scripts_count", 0):
                    with patch("os.path.exists", return_value=True):
                        with patch("os.access", return_value=True):
                            event = threading.Event()
                            started_threads = []

                            def blocking_thread(*args, **kwargs):
                                """Thread that blocks until event is set."""
                                def run():
                                    started_threads.append(1)
                                    event.wait()
                                # Use the real Thread class, not the mock
                                return RealThread(target=run)

                            with patch("threading.Thread", side_effect=blocking_thread):
                                # First request should succeed and increment counter
                                response1 = client.post("/run", json={
                                    "script_name": "hello",
                                    "script_response_webhook": "https://example.com/webhook",
                                    "script_timeout_seconds": 60
                                }, headers={"Authorization": "Bearer test-key"})

                                assert response1.status_code == 200
                                assert len(started_threads) == 1
                                assert main.active_scripts_count == 1

                                # Second request should be rejected (limit reached)
                                response2 = client.post("/run", json={
                                    "script_name": "hello2",
                                    "script_response_webhook": "https://example.com/webhook2",
                                    "script_timeout_seconds": 60
                                }, headers={"Authorization": "Bearer test-key"})

                                assert response2.status_code == 503
                                assert "limit reached" in response2.json()["detail"].lower()

                            # Cleanup: release threads and reset counter
                            event.set()
                            with main.active_scripts_lock:
                                main.active_scripts_count = 0

    def test_concurrent_script_counter_decremented_on_error(self, client):
        """Test active_scripts_count is decremented when script fails before starting."""
        import main

        with patch("main.API_KEY", "test-key"):
            with patch("os.path.exists", return_value=False):
                with patch.object(main, "active_scripts_count", 0):
                    with patch("main.MAX_CONCURRENT_SCRIPTS", 1):
                        # This will fail at script existence check
                        response = client.post("/run", json={
                            "script_name": "nonexistent",
                            "script_response_webhook": "https://example.com/webhook",
                            "script_timeout_seconds": 60
                        }, headers={"Authorization": "Bearer test-key"})

                        assert response.status_code == 404
                        assert main.active_scripts_count == 0

    def test_successful_script_execution_response(self, client):
        """Test successful request returns 'accepted' status."""
        with patch("main.API_KEY", "test-key"):
            with patch("os.path.exists", return_value=True):
                with patch("os.access", return_value=True):
                    with patch("threading.Thread") as mock_thread:
                        mock_thread.return_value.start = Mock()

                        response = client.post("/run", json={
                            "script_name": "hello",
                            "script_response_webhook": "https://example.com/webhook",
                            "script_timeout_seconds": 60
                        }, headers={"Authorization": "Bearer test-key"})

                        assert response.status_code == 200
                        assert response.json()["status"] == "accepted"
                        assert response.json()["script_name"] == "hello"
                        assert "execution started" in response.json()["message"].lower()

    def test_script_execution_in_thread(self, client):
        """Test script is executed in a background thread."""
        import main

        with patch("main.API_KEY", "test-key"):
            with patch("os.path.exists", return_value=True):
                with patch("os.access", return_value=True):
                    captured_args = []
                    original_thread = threading.Thread

                    def capture_thread(*args, **kwargs):
                        captured_args.append((args, kwargs))
                        return Mock(start=Mock())

                    with patch("threading.Thread", side_effect=capture_thread):
                        response = client.post("/run", json={
                            "script_name": "hello",
                            "script_response_webhook": "https://example.com/webhook",
                            "script_timeout_seconds": 60
                        }, headers={"Authorization": "Bearer test-key"})

                        assert response.status_code == 200
                        assert len(captured_args) == 1
                        # Verify it's running in a thread
                        assert captured_args[0][1].get("target") == main.run_script_and_notify

    
class TestScriptRunner:
    """Tests for the run_script_and_notify function."""

    def test_script_success(self):
        """Test successful script execution."""
        import main

        mock_result = Mock()
        mock_result.stdout = "Hello World"
        mock_result.stderr = ""
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_subprocess:
            with patch.object(main, "call_webhook") as mock_webhook:
                main.run_script_and_notify("/path/to/script", "https://webhook.com", 60)

                mock_subprocess.assert_called_once_with(
                    ["/path/to/script"],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                mock_webhook.assert_called_once_with(
                    "https://webhook.com",
                    {"stdout": "Hello World", "stderr": "", "return_code": 0}
                )

    def test_script_failure(self):
        """Test script execution with non-zero exit code."""
        import main

        mock_result = Mock()
        mock_result.stdout = ""
        mock_result.stderr = "Error occurred"
        mock_result.returncode = 1

        with patch("subprocess.run", return_value=mock_result):
            with patch.object(main, "call_webhook") as mock_webhook:
                main.run_script_and_notify("/path/to/script", "https://webhook.com", 60)

                mock_webhook.assert_called_once_with(
                    "https://webhook.com",
                    {"stdout": "", "stderr": "Error occurred", "return_code": 1}
                )

    def test_script_timeout(self):
        """Test script execution timeout."""
        import main
        import subprocess

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 60)):
            with patch.object(main, "call_webhook") as mock_webhook:
                main.run_script_and_notify("/path/to/script", "https://webhook.com", 60)

                mock_webhook.assert_called_once_with(
                    "https://webhook.com",
                    {"error": "Script execution timed out"}
                )

    def test_script_counter_decremented_in_finally(self):
        """Test active_scripts_count is decremented even on exceptions."""
        import main
        import subprocess

        main.active_scripts_count = 1

        with patch("subprocess.run", side_effect=Exception("Unexpected error")):
            with patch.object(main, "call_webhook"):
                try:
                    main.run_script_and_notify("/path/to/script", "https://webhook.com", 60)
                except Exception:
                    pass

                # Counter should be decremented in finally block
                assert main.active_scripts_count == 0


class TestWebhookCaller:
    """Tests for the call_webhook function."""

    def test_successful_webhook_call(self):
        """Test successful webhook POST."""
        import main

        with patch("httpx.post") as mock_post:
            mock_post.return_value = Mock(status_code=200)
            main.call_webhook("https://webhook.com", {"key": "value"})

            mock_post.assert_called_once_with(
                "https://webhook.com",
                json={"key": "value"},
                timeout=main.WEBHOOK_TIMEOUT_SECONDS
            )

    def test_webhook_timeout(self):
        """Test webhook timeout handling."""
        import main
        import httpx

        with patch("httpx.post", side_effect=httpx.TimeoutException("Timeout")):
            # Should not raise exception
            main.call_webhook("https://webhook.com", {"key": "value"})

    def test_webhook_connection_error(self):
        """Test webhook connection error handling."""
        import main
        import httpx

        with patch("httpx.post", side_effect=httpx.ConnectError("Connection failed")):
            # Should not raise exception
            main.call_webhook("https://webhook.com", {"key": "value"})


class TestConcurrency:
    """Tests for concurrency and thread safety."""

    def test_thread_safety_of_counter(self):
        """Test that active_scripts_count is thread-safe."""
        import main

        errors = []
        threads = []

        def increment_decrement():
            try:
                with main.active_scripts_lock:
                    main.active_scripts_count += 1
                # Small delay to increase chance of race condition
                time.sleep(0.001)
                with main.active_scripts_lock:
                    main.active_scripts_count -= 1
            except Exception as e:
                errors.append(e)

        # Start many threads
        for _ in range(100):
            t = threading.Thread(target=increment_decrement)
            threads.append(t)

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0
        assert main.active_scripts_count == 0

    def test_max_concurrent_scripts_boundary(self, client):
        """Test boundary of MAX_CONCURRENT_SCRIPTS."""
        import main

        with patch("main.API_KEY", "test-key"):
            with patch("main.MAX_CONCURRENT_SCRIPTS", 2):
                with patch("main.active_scripts_count", 2):
                    response = client.post("/run", json={
                        "script_name": "hello",
                        "script_response_webhook": "https://example.com/webhook",
                        "script_timeout_seconds": 60
                    }, headers={"Authorization": "Bearer test-key"})
                    assert response.status_code == 503

                # At limit - 1 should succeed
                with patch("main.active_scripts_count", 1):
                    with patch("os.path.exists", return_value=True):
                        with patch("os.access", return_value=True):
                            with patch("threading.Thread") as mock_thread:
                                mock_thread.return_value.start = Mock()
                                response = client.post("/run", json={
                                    "script_name": "hello",
                                    "script_response_webhook": "https://example.com/webhook",
                                    "script_timeout_seconds": 60
                                }, headers={"Authorization": "Bearer test-key"})
                                assert response.status_code == 200
