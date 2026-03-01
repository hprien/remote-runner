import os
import subprocess
import threading
import httpx
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "scripts")
API_KEY = os.getenv("API_KEY", "")
PORT = int(os.getenv("PORT", "8000"))


class ScriptRequest(BaseModel):
    script_name: str
    output_webhook: str


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


def run_script_and_notify(script_path: str, webhook_url: str):
    """Run script in background and notify webhook when done."""
    try:
        result = subprocess.run(
            [script_path],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        response_data = {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "return_code": result.returncode
        }

        # Send results to webhook
        try:
            httpx.post(webhook_url, json=response_data, timeout=10)
        except Exception as webhook_error:
            print(f"Webhook delivery failed: {webhook_error}")

    except subprocess.TimeoutExpired:
        try:
            httpx.post(webhook_url, json={"error": "Script execution timed out"}, timeout=10)
        except:
            pass
    except Exception as e:
        try:
            httpx.post(webhook_url, json={"error": str(e)}, timeout=10)
        except:
            pass


@app.post("/run", response_model=ScriptResponse)
def run_script(request: ScriptRequest, authorization: str = Header(None)):
    verify_api_key(authorization)

    script_path = os.path.join(SCRIPTS_DIR, request.script_name, request.script_name)

    if not os.path.exists(script_path):
        raise HTTPException(status_code=404, detail=f"Script '{request.script_name}' not found")

    if not os.access(script_path, os.X_OK):
        raise HTTPException(status_code=403, detail=f"Script '{request.script_name}' not found")

    # Start script in background thread
    thread = threading.Thread(target=run_script_and_notify, args=(script_path, request.output_webhook))
    thread.start()

    return ScriptResponse(
        status="accepted",
        script_name=request.script_name,
        message="Script execution started"
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
