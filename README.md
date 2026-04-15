# remote-runner

Offers script execution via REST API.

## Setup

```bash
# Configure environment
cp .env.example .env
# Edit .env with your API_KEY and PORT

# Build Docker image
docker build -t remote-runner .
```

## Running

Using Docker:
```bash
docker run -d \
  --name remote-runner \
  -p 8000:8000 \
  -v $(pwd)/scripts:/app/scripts \
  --env-file .env \
  remote-runner
```

Using Docker Compose:
```bash
docker compose up -d
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
  "script_response_webhook": "https://example.com/webhook",
  "script_timeout_seconds": 300
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

The script runs in the background. Results are sent to `script_response_webhook` when complete:
```json
{
  "stdout": "Hello from remote-runner!\nCurrent date: ...\n",
  "stderr": "",
  "return_code": 0
}
```

## Testing with webhook.site

1. Visit https://webhook.site and copy your unique ID
2. Copy `example.sh.example` to `example.sh`:
   ```bash
   cp example.sh.example example.sh
   ```
3. Edit `example.sh` and replace `<your-webhook-site-id-here>` with your webhook.site ID
4. Make it executable and run:
   ```bash
   chmod +x example.sh
   ./example.sh
   ```
5. Check webhook.site to see the script execution results

## Viewing Audit Logs

Audit logs are sent to syslog and can be viewed with:

```bash
# View all remote-runner audit logs
journalctl -t remote-runner

# Follow logs in real-time
journalctl -t remote-runner -f

# View last 50 entries
journalctl -t remote-runner -n 50

# Logs from last hour
journalctl -t remote-runner --since "1 hour ago"
```

## Adding Scripts

Place executable scripts in `scripts/<script_name>/<script_name>`. For example:
- `scripts/hello/hello` - executable script file
