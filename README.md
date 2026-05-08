# OSONE — Docker Edition 🐳

Containerized OSONE stack for Unraid / any Docker host with NVIDIA GPU.

## Services

| Container | Port | Description |
|-----------|------|-------------|
| `osone-llama` | internal | llama.cpp server (CUDA, NVIDIA GPU) |
| `osone-skyd` | internal | skyd AI daemon |
| `osone-gui` | 8000 | FastAPI backend + React dashboard |
| `osone-landing` | 9000 | Public landing page (nginx) |

## Prerequisites

- Docker + Docker Compose
- NVIDIA GPU with drivers installed
- [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)

## Unraid Setup

1. **Create directories on Unraid:**
   ```
   /mnt/user/osone/models/     ← put llama3.2.gguf here
   /mnt/user/osone/skyd/lang/  ← SkyLang rules (auto-populated)
   /mnt/user/osone/skyd/logs/  ← skyd logs
   /mnt/user/osone/web/        ← landing page HTML
   /etc/osone/                 ← users.json (auth)
   ```

2. **Copy your model:**
   ```bash
   cp llama3.2.gguf /mnt/user/osone/models/
   ```

3. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your values
   ```

4. **Build and start:**
   ```bash
   docker compose up -d --build
   ```

5. **Point Cloudflare Tunnel:**
   - `app.osone.org` → `http://localhost:8000`
   - `osone.org` → `http://localhost:9000`

## Admin Access

Visit `app.osone.org` — you'll land on the public chat.

To access admin: **click the OSONE logo 5 times** → admin login modal appears.

Default admin: `bennett` / `osone2025` ← **change this immediately!**

## Updating skyd

skyd auto-syncs to GitHub. To pull updates manually:
```bash
docker compose pull skyd && docker compose up -d skyd
```

## GPU Check

```bash
docker exec osone-llama nvidia-smi
```
