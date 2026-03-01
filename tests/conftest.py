import os
import sys
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

# Ensure the parent directory is in the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app, API_KEY, active_scripts_count, active_scripts_lock


@pytest.fixture
def client():
    """Return a TestClient for the FastAPI app."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_active_scripts_counter():
    """Reset the active scripts counter before and after each test."""
    global active_scripts_count
    with active_scripts_lock:
        active_scripts_count = 0
    yield
    with active_scripts_lock:
        active_scripts_count = 0


@pytest.fixture
def mock_api_key():
    """Set a known API key for testing."""
    original_key = API_KEY
    with patch.dict(os.environ, {"API_KEY": "test-api-key-12345"}):
        import importlib
        import main
        importlib.reload(main)
        yield "test-api-key-12345"
    # Restore original
    with patch.dict(os.environ, {"API_KEY": original_key}):
        importlib.reload(main)


@pytest.fixture
def auth_headers():
    """Return authorization headers with valid API key."""
    return {"Authorization": "Bearer test-api-key-12345"}
