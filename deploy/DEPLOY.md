# Shedulex VPS deployment guide

**Domain:** `shedulex.hudumatech.com`  
**API:** `https://shedulex.hudumatech.com/api/v1`  
**Architecture:** Docker backend (Kong on localhost) + host Nginx HTTPS + local Vue frontend

---

## 1. Backup on your local machine

Ensure the stack is running:

```bash
docker compose up -d
```

Create a backup:

```bash
bash scripts/backup.sh
# optional AI vector store:
bash scripts/backup.sh --with-chroma
```

Output: `backups/shedulex-YYYYMMDD-HHMMSS/` with `postgres-all.sql`, `env.backup`, `manifest.txt`.

Transfer to VPS:

```bash
scp -r backups/shedulex-YYYYMMDD-HHMMSS user@YOUR_VPS_IP:/opt/shedulex/backups/
```

---

## 2. VPS prerequisites

```bash
# Docker (if not installed)
curl -fsSL https://get.docker.com | sh
apt install -y docker-compose-plugin git

# Firewall — Nginx handles 80/443; Kong is NOT public
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
```

**DNS:** A record `shedulex` → VPS public IP (`shedulex.hudumatech.com`).

**SSL** (if not already issued):

```bash
sudo certbot certonly --nginx -d shedulex.hudumatech.com
```

---

## 3. Clone repo on VPS

```bash
sudo mkdir -p /opt/shedulex
sudo chown $USER:$USER /opt/shedulex
cd /opt/shedulex
git clone https://github.com/snavid/shedulex.git .
```

---

## 4. Configure production environment

```bash
cp .env.production.example .env
nano .env
```

Copy secrets from local `env.backup`. **Critical:** use the same `JWT_SECRET_KEY`, `JWT_ISSUER`, and `INTERNAL_SERVICE_KEY` as local so logins and inter-service calls work after restore.

| Variable | Value |
|----------|-------|
| `FLASK_ENV` | `production` |
| `DOCUMENT_PUBLIC_BASE_URL` | `https://shedulex.hudumatech.com` |
| `FRONTEND_URL` | `http://localhost:5173` |

---

## 5. Restore database and start stack

```bash
cd /opt/shedulex

# Postgres only first
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d postgres
docker compose exec postgres pg_isready -U shedulex -d shedulex_master

# Restore (interactive confirm)
COMPOSE_FILES="-f docker-compose.yml -f docker-compose.prod.yml" \
  bash scripts/restore.sh backups/shedulex-YYYYMMDD-HHMMSS/postgres-all.sql

# Full stack (Kong on 127.0.0.1:8000 only)
bash scripts/deploy-production.sh
```

---

## 6. Enable Nginx site

```bash
sudo cp deploy/nginx/shedulex.conf /etc/nginx/sites-available/shedulex
sudo ln -sf /etc/nginx/sites-available/shedulex /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

Edit SSL paths in `shedulex.conf` if your certificates are not under `/etc/letsencrypt/live/shedulex.hudumatech.com/`.

---

## 7. Verify

**On VPS:**

```bash
curl -s https://shedulex.hudumatech.com/api/v1/universities | head
curl -s http://127.0.0.1:8000/api/v1/universities | head
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
docker compose logs notification-worker --tail 20
```

Kong must **not** be reachable from the public internet on port 8000.

**Kong admin** (SSH tunnel only):

```bash
ssh -L 8001:127.0.0.1:8001 user@YOUR_VPS_IP
# then open http://localhost:8001
```

---

## 8. Local frontend (your PC)

```bash
cd frontend
cp .env.local.example .env.local
npm run dev
```

Open `http://localhost:5173` — API calls go to `https://shedulex.hudumatech.com/api/v1`.

---

## Ongoing operations

### Deploy updates

```bash
cd /opt/shedulex
git pull
bash scripts/deploy-production.sh
```

### Scheduled backups on VPS

```cron
0 2 * * * root cd /opt/shedulex && bash scripts/backup.sh >> /var/log/shedulex-backup.log 2>&1
```

Copy backups off-server regularly.

### Rollback

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml down
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d postgres
bash scripts/restore.sh backups/PREVIOUS/postgres-all.sql
bash scripts/deploy-production.sh
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| 502 from Nginx | `docker compose ps` — ensure Kong healthy; `curl http://127.0.0.1:8000/api/v1/universities` |
| CORS error from local UI | Kong must allow `http://localhost:5173` in `gateway/kong.yml`; restart Kong |
| JWT / login fails after migrate | `JWT_SECRET_KEY` must match local `.env` exactly |
| Sora SSE drops | Nginx `proxy_buffering off` + `proxy_read_timeout 360s` in `deploy/nginx/shedulex.conf` |
| Stale upstream after rebuild | `docker compose restart kong` |
