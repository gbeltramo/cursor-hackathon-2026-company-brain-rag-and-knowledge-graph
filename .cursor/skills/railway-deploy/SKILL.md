---
name: railway-deploy
description: Deploy a FastAPI backend to Railway as a single service. Use this skill whenever the user mentions deploying to Railway, running `railway up`, setting Railway environment variables, generating a Railway domain, or troubleshooting Railway build/deploy issues. Also trigger when the user asks to "deploy the backend", "publish to Railway", or wants a public URL for their FastAPI app.
---

# Railway Deploy — Single FastAPI Service

Deploys the `backend/` FastAPI app to Railway with no Dockerfile and no GitHub. Railway builds via Railpack (auto-detected from `pyproject.toml` + `uv.lock`). One service, one URL, everything served from it (`/ask`, `/`, `/files/`).

---

## Prerequisites checklist

Before starting, confirm:
- [ ] Railway CLI installed (`railway --version`)
- [ ] Logged in (`railway whoami`)
- [ ] Working directory is `backend/`
- [ ] Local `.env` values are at hand (you'll set them as Railway variables)

---

## Step-by-step deploy

### 1. Account setup (first time only)

Sign up at https://railway.com — $5 free credit, no card needed.

**Set the default region before creating any project:**
> Railway dashboard → avatar (top-right) → Account Settings → Default Region → **EU West Metal (Amsterdam)**

Low latency matters against 30 s eval budgets. Do this *before* `railway init`.

### 2. Install the CLI

**macOS / Linux**
```bash
npm install -g @railway/cli
# or: brew install railway
```

**Windows (PowerShell as Administrator)**
```powershell
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser -Force
powershell -c "irm https://community.chocolatey.org/install.ps1 | iex"
choco install nodejs-lts -y
# Close and reopen PowerShell, then:
npm install -g @railway/cli
railway --version
```

Verify with `railway --version`.

### 3. Log in

```bash
railway login
```

Opens the browser for auth. Confirm with `railway whoami`.

### 4. Create the project and deploy

```bash
cd backend/
railway init        # choose a name, e.g. company-brain-yourname
railway up          # upload → Railpack build → deploy (live logs)
```

> **Naming tip:** unique names get clean domains; generic names (e.g. `backend`) get a random suffix. Both work.

> **Avoid `--detach`** — plain `railway up` keeps the CLI linked to the service. If you used `--detach`, re-link with `railway service <name>`.

### 5. Set environment variables

```bash
railway variables \
  --set LLM_BASE_URL=https://api.regolo.ai/v1 \
  --set LLM_API_KEY=<your-key> \
  --set MODEL=<your-model-id> \
  --set MOCK_API_BASE_URL=https://aldente.yellowtest.it \
  --set MOCK_API_TOKEN=<your-token-from-platform-dashboard>
```

Alternatively: Railway dashboard → service → **Variables** → New Variable.  
Changing any variable triggers an automatic redeploy.

### 6. Generate the public URL

```bash
railway domain
```

Copy the URL (e.g. `https://company-brain-yourname-production.up.railway.app`), then:

1. **Submit this URL on the event platform** — the evaluator hits `<url>/ask`.
2. Set it as `PUBLIC_BASE_URL` so artifact links work:

```bash
railway variables --set PUBLIC_BASE_URL=https://<your-url>
```

### 7. Smoke test

```bash
curl https://<your-url>/health
# expected: {"status":"ok"}

curl -X POST https://<your-url>/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"test"}'
# 501 is fine until /ask is implemented
```

Run the **endpoint check** on the platform dashboard to validate the full `/ask` contract before submitting.

### 8. Subsequent deploys

Every later deploy from `backend/` is just:
```bash
railway up
```
It takes seconds. **Deploy often.**

---

## Useful CLI commands

| Command | Purpose |
|---|---|
| `railway whoami` | Which account is logged in |
| `railway status` | Linked project + service |
| `railway list` | All your projects |
| `railway logs` | Runtime logs |
| `railway logs --build` | Build logs (use when deploy fails) |
| `railway variables` | List env vars |
| `railway domain` | Print or create the public URL |

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `railway: command not found` | `npm install -g @railway/cli` (Windows: see step 2) |
| `No service could be found` | CLI lost the link (usually after `--detach`). Run `railway service <name>`. |
| Build fails | `railway logs --build`. Most often a typo in `pyproject.toml` deps. |
| Healthcheck failing | `GET /health` must return `{"status":"ok"}`. Avoid heavy startup work — do it lazily or the healthcheck times out. |
| `/ask` works locally but 401/500 on Railway | A variable is missing. `railway variables` and compare with your local `.env`. |
| Artifact links point to localhost | `PUBLIC_BASE_URL` not set (step 6). |
| Upload is huge (>100 MB) or stalls | A `venv/` or `env/` folder (no leading dot) is being uploaded. Rename it to `.venv` — it's auto-excluded. |
| Service deployed in US | `railway scale --service <name> --europe-west4=1`. Set the default region for next time. |
| First request slow after deploy | Cold start — warm up with a few `/health` + easy `/ask` calls right after deploying. |

---

## Optional: Railway MCP server in Cursor

Lets Cursor's agent drive Railway via native tools (`deploy`, `set-variables`, `generate-domain`, `get-logs`, etc.) instead of shell commands.

```bash
railway setup agent
```

Then check **Cursor Settings → MCP** to confirm the Railway server is listed.  
Full reference: https://docs.railway.com/reference/mcp-server

---

## Submission checklist

- [ ] `/health` returns `{"status":"ok"}`
- [ ] `/ask` responds (even 501 is fine pre-implementation)
- [ ] `PUBLIC_BASE_URL` is set
- [ ] Platform endpoint check passes
- [ ] URL submitted on the event platform

> **Deploy by hour 3**, even if `/ask` still returns 501. A live service with a valid URL is what the evaluator needs — don't leave it for the last hour.
