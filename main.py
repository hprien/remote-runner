import os
import re
import subprocess
import threading
import httpx
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, field_validator
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "scripts")
API_KEY = os.getenv("API_KEY", "")
PORT = int(os.getenv("PORT", "8000"))
HOST = os.getenv("HOST", "127.0.0.1")
WEBHOOK_TIMEOUT_SECONDS = 10

SCRIPT_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')


class ScriptRequest(BaseModel):
    script_name: str
    script_response_webhook: str
    script_timeout_seconds: int

    @field_validator('script_name')
    @classmethod
    def validate_script_name(cls, v: str) -> str:
        if not SCRIPT_NAME_PATTERN.match(v):
            raise ValueError('script_name must contain only letters, numbers, dashes, and underscores')
        return v

    @field_validator('script_timeout_seconds')
    @classmethod
    def validate_script_timeout_seconds(cls, v: int) -> int:
        if v <= 0:
            raise ValueError('script_timeout_seconds must be positive')
        return v


class ScriptResponse(BaseModel):
    status: str
    script_name: str
    message: str


def verify_api_key(authorization: str = Header(None)):
    if not API_KEY:
        raise HTTPException(status_code=500, detail="API_KEY not configured")

    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header")

    token = authorization[7:]  # Remove "Bearer " prefix
    if token != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return token


def call_webhook(webhook_url: str, content: dict):
    try:
        httpx.post(webhook_url, json=content, timeout=WEBHOOK_TIMEOUT_SECONDS)
    except httpx.TimeoutException as e:
        print(f"Webhook delivery timed out: {e}")
    except httpx.ConnectError as e:
        print(f"Webhook connection failed: {e}")

def run_script_and_notify(script_path: str, webhook_url: str, timeout: int):
    """Run script in background and notify webhook when done."""

    try:
        result = subprocess.run(
            [script_path],
            capture_output=True,
            text=True,
            timeout=timeout
        )

        response_data = {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "return_code": result.returncode
        }

        call_webhook(webhook_url, response_data)

    except subprocess.TimeoutExpired:
        call_webhook(webhook_url, {"error": "Script execution timed out"})


@app.post("/run", response_model=ScriptResponse)
def run_script(request: ScriptRequest, authorization: str = Header(None)):
    verify_api_key(authorization)

    script_path = os.path.join(SCRIPTS_DIR, request.script_name, request.script_name)

    if not os.path.exists(script_path):
        raise HTTPException(status_code=404, detail=f"Script '{request.script_name}' not found")

    if not os.access(script_path, os.X_OK):
        raise HTTPException(status_code=403, detail=f"Script '{request.script_name}' not found")

    # Start script in background thread
    thread = threading.Thread(target=run_script_and_notify, args=(script_path, request.script_response_webhook, request.script_timeout_seconds))
    thread.start()

    return ScriptResponse(
        status="accepted",
        script_name=request.script_name,
        message="Script execution started"
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
