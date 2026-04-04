# RankJee Deployment Checklist

This project is Docker-ready. The fastest path is a one-command deploy:

```bash
chmod +x docker-deploy.sh
./docker-deploy.sh
```

The command above will:
- stop existing containers,
- rebuild images,
- start `db`, `redis`, `web`, `celery`, and `celery-beat`,
- run migrations and collectstatic via [`entrypoint.sh`](entrypoint.sh) (Dockerfile `ENTRYPOINT`; each service runs this before `gunicorn` / Celery),
- print service status.

`docker-compose.yml` uses `${VAR:-default}` so you can place a `.env` file next to it (copy from [`.env.production.example`](.env.production.example)) and set `SECRET_KEY`, `ALLOWED_HOSTS`, `SITE_BASE_URL`, email, Razorpay, etc. Django also calls `load_dotenv()`, so extra keys in `.env` (e.g. `EMAIL_HOST_USER`) are picked up when the project directory is mounted.

---

## 1) Pre-deploy checks

- Docker and Docker Compose are installed:
  - `docker --version`
  - `docker compose version`
- Ports are free or mapped as expected:
  - `8000` (web), `5432` (db optional local access)
- Required env values are set for your environment:
  - `DEBUG=0`
  - `SECRET_KEY` (strong value)
  - `ALLOWED_HOSTS` (comma-separated)
  - `DATABASE_URL` (postgres in deploy)
  - `REDIS_URL`
  - `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`
  - `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`
  - `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET` (or `RAZORPAY_USE_DUMMY=1` for demo)
  - `SITE_BASE_URL` (for email links)

---

## 2) One-command deploy

```bash
./docker-deploy.sh
```

Verify:
- `docker compose ps` shows `web`, `db`, `redis`, `celery`, `celery-beat` up.
- App opens at [http://localhost:8000](http://localhost:8000)
- Admin opens at [http://localhost:8000/sd/](http://localhost:8000/sd/)

---

## 3) Post-deploy smoke tests

- Login/signup works.
- Take test -> result page works.
- Weak concept -> Watch Lesson opens relevant video page.
- Earnings -> withdrawal request submission works.
- CMS pages open:
  - `/admin/cms/`
  - `/admin/cms/paths/new/`
  - `/admin/cms/skills/new/`
  - `/admin/cms/tasks/new/`
  - `/admin/cms/videos/new/`
- Celery reminder task visible in logs.

---

## 4) Production hardening reminders

- Use real `SECRET_KEY`, never default fallback.
- Keep `DEBUG=0`.
- Configure real domain in `ALLOWED_HOSTS`.
- Use HTTPS at reverse proxy/load balancer.
- Rotate DB and SMTP credentials.
- Back up Postgres volume (`postgres_data`) regularly.
- Replace draft legal pages with final legal copy.

---

## 5) Useful commands

- View logs:
  - `docker compose logs -f web`
  - `docker compose logs -f celery`
- Restart services:
  - `docker compose restart web celery celery-beat`
- Stop everything:
  - `docker compose down`

---

## 6) DigitalOcean (Droplet + Docker) — recommended path

Use a **Ubuntu 22.04/24.04 Droplet** (2 GB RAM minimum for Postgres + Redis + web + Celery; 4 GB is more comfortable).

### One-time server setup

1. **Create the Droplet** in the DigitalOcean control panel, add your SSH key, and note the **public IP**.
2. **DNS:** Point your domain’s **A record** to that IP (e.g. `app.yourdomain.com` or `@`).
3. **SSH in:** `ssh root@YOUR_DROPLET_IP`
4. Install Docker (official convenience script or DigitalOcean’s Docker 1-click image):
   - `apt update && apt install -y ca-certificates curl`
   - Install Docker Engine + Compose plugin per [Docker’s Ubuntu docs](https://docs.docker.com/engine/install/ubuntu/).
5. **Firewall:** `ufw allow OpenSSH` and `ufw allow 80` and `ufw allow 443` (if you terminate TLS on the droplet), then `ufw enable`. Do **not** expose Postgres (`5432`) publicly.

### Deploy the app

1. **Clone the repo** (or upload a release tarball):
   - `git clone https://github.com/YOU/sd-rankjee2026.git && cd sd-rankjee2026`
2. **Create `.env`** in the project root (same folder as `docker-compose.yml`):
   - `cp .env.production.example .env`
   - Edit `.env`: set a long random `SECRET_KEY`, `ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com,YOUR_DROPLET_IP`, `SITE_BASE_URL=https://yourdomain.com`, real SMTP if you send mail, Razorpay keys (or `RAZORPAY_USE_DUMMY=1` for demos only).
   - Keep `DATABASE_URL=postgres://postgres:postgres@db:5432/rankjee_db` as in the example **when using the bundled Postgres service** in Compose.
3. **Run the one-command deploy:**
   - `chmod +x docker-deploy.sh && ./docker-deploy.sh`
4. **Smoke test over HTTP:** open `http://YOUR_DROPLET_IP:8000` (or your domain if DNS points here). Student UI is at `/`, dashboard at `/admin/`, Django admin at `/sd/`.

### HTTPS and port 80 (production)

Gunicorn in Compose listens on **8000**. For real users you should put **HTTPS** in front:

- **Option A — Caddy (simple):** Install Caddy on the host, proxy `https://yourdomain.com` → `127.0.0.1:8000`, let Caddy obtain Let’s Encrypt certificates.
- **Option B — Nginx:** Same idea: reverse proxy to `127.0.0.1:8000`, certbot for TLS.

After HTTPS works, set `SITE_BASE_URL=https://yourdomain.com` and ensure `ALLOWED_HOSTS` includes that host.

### DigitalOcean managed DB (optional)

You can use **Managed PostgreSQL** instead of the `db` service: create a cluster in DO, set `DATABASE_URL` in `.env` to the provided connection string, and remove or stop the `db` service from `docker-compose.yml` (advanced; keep backups and private networking in mind).

### Troubleshooting: `exec: "/app/entrypoint.sh": permission denied`

Compose mounts your project directory over `/app`, so the **host** `entrypoint.sh` is used. If it is not marked executable (common after `git clone` on Linux), direct `exec` fails. The Dockerfile runs the script with **`/bin/sh /app/entrypoint.sh`** so this should not happen after a **rebuild**:

```bash
docker compose build --no-cache web celery celery-beat
./docker-deploy.sh
```

Alternatively on the server: `chmod +x entrypoint.sh` then `docker compose up -d`.

### App Platform note

**DigitalOcean App Platform** can run Dockerfiles, but this project expects **Postgres + Redis + Celery + Celery Beat** together. The Droplet + `docker compose` approach matches the repo’s [`docker-compose.yml`](docker-compose.yml) with minimal changes. Using App Platform usually means splitting into separate components (web worker, workers, databases) and is not “one click” from this file alone.

