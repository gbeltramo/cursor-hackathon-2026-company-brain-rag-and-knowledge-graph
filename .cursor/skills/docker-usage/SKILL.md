---
name: docker-usage
description: >
  Use this skill when the user asks about Docker, docker compose, containers,
  or running the dev environment via Docker. Covers setup, daily commands,
  rebuilding after dependency changes, and common error fixes specific to this
  project's docker-compose.dev.yml setup. Trigger on phrases like "start the
  dev environment", "Docker isn't working", "container logs", "hot reload
  stopped", or any mention of docker/docker compose in the context of this
  project.
---

# Docker Usage (Fallback Dev Environment)

> **You probably don't need this.** The default way to run the starter is
> native: `uv` + Python (see `README.md`, two commands). Use Docker only if
> you can't or don't want to install Python tooling on your machine. Railway
> deploys do **not** use Docker either — Railway builds the app itself (see
> `DEPLOY.md`).

---

## 1. Install Docker Desktop

Download from https://www.docker.com/products/docker-desktop/ — no Docker
account required; skip any sign-in prompt.

Pick the right build for your machine:

- **Mac**: Apple Silicon (M1/M2/M3/M4) or Intel — check Apple menu → About
  This Mac if unsure.
- **Windows**: AMD64 (most common) or ARM64. During install, keep the **WSL2**
  option enabled (default). If prompted to enable WSL2/virtualization, accept
  and reboot.
- **Linux**: Docker Desktop, or plain `docker` + `docker compose` from your
  package manager.

After installing, **start Docker Desktop** and wait for the whale icon to
settle. Verify in a terminal:

```bash
docker --version
docker ps        # must not error — an empty list is fine
```

---

## 2. First-time setup

From the project root (where `docker-compose.dev.yml` lives):

```bash
# 1. Create your env file and fill in the required values
cp backend/.env.example backend/.env

# 2. Start the dev environment (image builds automatically on first run)
docker compose -f docker-compose.dev.yml up -d
```

Then open:
- **App**: http://localhost:8000
- **API docs**: http://localhost:8000/docs

Your code is bind-mounted — edit files locally and the server hot-reloads
inside the container automatically.

---

## 3. Everyday commands

You can ask Cursor to run these ("start the dev environment", "show me the
backend logs") or run them directly:

| Task | Command |
|---|---|
| Start | `docker compose -f docker-compose.dev.yml up -d` |
| Tail logs | `docker compose -f docker-compose.dev.yml logs -f` |
| Stop | `docker compose -f docker-compose.dev.yml down` |
| Rebuild (after `pyproject.toml` changes) | `docker compose -f docker-compose.dev.yml up -d --build` |
| Restart (if hot reload misbehaves) | `docker compose -f docker-compose.dev.yml restart` |

---

## 4. Troubleshooting

| Problem | Fix |
|---|---|
| `Cannot connect to the Docker daemon` | Docker Desktop isn't running. Start it and wait for the whale icon. |
| Port `8000` already in use | Something else is using port 8000. Stop it, or change the port mapping in `docker-compose.dev.yml` to `"8001:8000"` and use http://localhost:8001. |
| Added a dependency but the container doesn't see it | Dependencies install at build time — rebuild: `docker compose -f docker-compose.dev.yml up -d --build` |
| Hot reload stopped working | `docker compose -f docker-compose.dev.yml restart` |
| Windows: WSL2 errors at startup | Open PowerShell as Administrator → `wsl --update` → reboot → restart Docker Desktop. |
| Changes to `.env` not picked up | Containers read env at start — `down` then `up -d`. |

---

If Docker keeps fighting you, switch to the native path (`README.md` → Quick
start): it's one `uv sync` away.
