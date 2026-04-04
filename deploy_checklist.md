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
- run migrations and collectstatic via `entrypoint.sh`,
- print service status.

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

