# Tarot Reader API (Vercel Python Serverless)

A lightweight Tarot draw API deployed as a Vercel Python Serverless Function.

* Endpoint: `POST /api/tarot`
* Input: JSON body with `positions` (array of strings) and optional `label`
* Output: JSON with `draws` and `meta`

---

## Project structure

```
tarot-reader/
├─ api/
│  └─ tarot.py
├─ dev_server.py
├─ requirements.txt
└─ .gitignore
```

---

## API contract

### Request (POST)

`Content-Type: application/json`

```json
{
  "positions": ["Past", "Present", "Future"],
  "label": "3-card"
}
```

Rules:

* `positions` must be a non-empty array of non-empty strings
* `positions` must be unique
* maximum positions: 30
* `label` is optional; maximum length: 200 characters

---

### Response (200)

```json
{
  "draws": {
    "Past": { "card": "Knight of Cups", "orientation": "upright" },
    "Present": { "card": "Justice", "orientation": "reversed" },
    "Future": { "card": "The Fool", "orientation": "upright" }
  },
  "meta": { "label": "3-card" }
}
```

### Error responses

* `400` — invalid JSON or validation error
* `401` — Unauthorized (when auth is enabled)
* `405` — Method not allowed

---

## Authentication

Authentication is optional and controlled via an environment variable.

* Environment variable: `TAROT_API_KEY`
* Header format:

```
Authorization: Bearer <key>
```

### Behavior

* If `TAROT_API_KEY` **is not set** → authentication is disabled (all requests allowed)
* If `TAROT_API_KEY` **is set** → requests must include a matching Bearer token

---

## Local development setup

### Local secret file (recommended)

Create `.env.local` (do **not** commit):

```bash
export TAROT_API_KEY='your-long-secret'
```

Ensure `.env.local` is listed in `.gitignore`.

---

## Local testing (no Vercel CLI required)

### 1) Run the dev server

Create `dev_server.py` in the project root:

```python
from http.server import HTTPServer
from api.tarot import handler

if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", 8000), handler)
    print("Listening on http://127.0.0.1:8000")
    server.serve_forever()
```

Start the server (Terminal 1):

```bash
source .env.local   # optional, only if auth should be enabled locally
python3 dev_server.py
```

---

### 2) Test with curl (Terminal 2)

#### When authentication is enabled

**No Authorization header (expected: 401):**

```bash
curl -i -X POST "http://127.0.0.1:8000" \
  -H "Content-Type: application/json" \
  -d '{"positions":["Past","Present","Future"]}'
```

**Wrong token (expected: 401):**

```bash
curl -i -X POST "http://127.0.0.1:8000" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer wrong" \
  -d '{"positions":["Past","Present","Future"]}'
```

**Correct token (expected: 200):**

```bash
source .env.local
curl -i -X POST "http://127.0.0.1:8000" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TAROT_API_KEY" \
  -d '{"positions":["Past","Present","Future"],"label":"3-card"}'
```

> Note: If you do not `source .env.local` in the curl terminal, `$TAROT_API_KEY` expands to an empty string and authentication will fail.

#### When authentication is disabled

```bash
curl -i -X POST "http://127.0.0.1:8000" \
  -H "Content-Type: application/json" \
  -d '{"positions":["Past","Present","Future"]}'
```

---

## Deployment to Vercel

### Git-based deployment (recommended)

1. Push the repository to GitHub
2. In Vercel: **New Project → Import Git Repository → Deploy**

The API will be available at:

```
POST https://<project>.vercel.app/api/tarot
```

---

### Enable authentication in production

In the Vercel dashboard:

* Project → Settings → Environment Variables
* Add `TAROT_API_KEY` with your secret value
* Apply to **Production** (and optionally **Preview**)
* Redeploy the project

---

## Production test

```bash
curl -i -X POST "https://<project>.vercel.app/api/tarot" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <YOUR_PROD_KEY>" \
  -d '{"positions":["Past","Present","Future"]}'
```