# remote-runner

Offers script execution via REST API.

## Setup

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API_KEY and PORT
```

## Running

```bash
python main.py
```

The server will start on `http://127.0.0.1:8000` (or the host/port specified in .env).

## API

### POST /run

Execute a script and send results to a webhook.

**Headers:**
- `Authorization: Bearer <API_KEY>`

**Body:**
```json
{
  "script_name": "hello",
  "output_webhook": "https://example.com/webhook",
  "timeout": 300
}
```

**Response (immediate):**
```json
{
  "status": "accepted",
  "script_name": "hello",
  "message": "Script execution started"
}
```

The script runs in the background. Results are sent to `output_webhook` when complete:
```json
{
  "stdout": "Hello from remote-runner!\nCurrent date: ...\n",
  "stderr": "",
  "return_code": 0
}
```

## Adding Scripts

Place executable scripts in `scripts/<script_name>/<script_name>`. For example:
- `scripts/hello/hello` - executable script file
