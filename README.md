# Shedulex

Design and Implementation of an Intelligent Dynamic Academic Timetable Management System using Genetic Algorithms and Microservice Architecture.

## Overview

Shedulex is a distributed academic scheduling platform built as an enterprise-style microservice system.
It generates optimized timetables using a Genetic Algorithm (GA), supports dynamic AI-assisted adjustments,
and provides surrounding institutional tooling: notifications, analytics, calendar management, document export,
and auditable operations.

## Architecture

- API Gateway: Kong (`gateway/kong.yml`)
- Datastores: PostgreSQL + Redis
- Backend style: microservices with Flask, JWT, SQLAlchemy, REST APIs
- Frontend: Vue 3 + Pinia + Vue Router + Axios
- Async processing: Celery worker + Celery beat for reminders
- Containerization: Docker + Docker Compose

### Backend Services

- `auth-service` (5001)
  - Registration/login, JWT access/refresh, RBAC, sessions, password reset, email verification
- `timetable-engine` (5002)
  - GA timetable generation, resources CRUD (departments, rooms, lecturers, courses, constraints, time slots)
  - Conflict detection, smart conflict prediction, timetable entry swapping
  - Timetable version snapshots and restore
- `adjustment-engine` (5003)
  - LangGraph-powered natural language adjustment assistant
  - Suggestion and conflict operations
- `notification-service` (5004)
  - Email/SMS notifications, scheduled reminders, broadcast queueing
- `calendar-service` (5005)
  - Academic events, semester timelines, ICS export
- `document-service` (5006)
  - Timetable PDF/Excel/CSV export
- `analytics-service` (5007)
  - KPI overview, room utilization, lecturer workload metrics
- `audit-service` (5008)
  - Security and activity logs with admin querying/statistics

## Implemented Completion Pass

This repository now includes:

- Full frontend route coverage for all major dashboard pages:
  - Resources: departments, rooms, lecturers, courses, constraints
  - AI assistant, calendar, analytics, notifications, profile
  - Admin: users and audit logs
- Gateway route fixes for `/api/v1/users` and all timetable resource endpoints
- Secure service-to-service access pattern using `X-Internal-Service-Key`
- Timetable engine additions:
  - `/api/v1/timetable/entries`
  - `/api/v1/time-slots`
  - `/api/v1/timetable/<id>/predict-conflicts`
  - versioning snapshots and restore endpoints
- GA runtime bug fix in mutation pipeline (dict-vs-id issue) and passing unit tests

## Quick Start

1. Copy env file:
   - `cp .env.example .env` (or create `.env` manually on Windows)
2. Ensure Docker is running.
3. Start platform:
   - `docker compose up --build`
4. Access:
   - Frontend (dev): `frontend` via Vite on `http://localhost:5173`
   - Kong gateway: `http://localhost:8000`
   - Kong admin: `http://localhost:8001`

## Networking

By default, **only Kong** is published to the host (`8000` proxy, `8001` admin). All microservices, Postgres, Redis, and ChromaDB communicate on the internal `shedulex-net` Docker network. The frontend dev server proxies `/api` to Kong at `http://localhost:8000`.

To expose Postgres/Redis on the host for DBeaver or running a backend outside Docker:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev-ports.yml up -d
```

This publishes `localhost:5543` (Postgres) and `localhost:6490` (Redis) without exposing individual microservice ports.

## VPS production deployment

See **[deploy/DEPLOY.md](deploy/DEPLOY.md)** for migrating your local data to a VPS at `https://shedulex.hudumatech.com` (Docker + host Nginx + local frontend).

Quick backup before migration:

```bash
bash scripts/backup.sh
```

On Windows if the bash script hangs, use PowerShell instead:

```powershell
.\scripts\backup.ps1
```


```bash
cd frontend
npm install
npm run dev
```

Production build check:

```bash
npm run build
```

## Testing

Timetable engine unit tests:

```bash
cd Backend/timetable-engine
python -m pytest tests -q
```

## Environment Notes

- `INTERNAL_SERVICE_KEY` is required for trusted inter-service calls and should be rotated in production.
- `OPENAI_API_KEY` powers the adjustment-engine LangGraph assistant.
- Beem and SMTP credentials are required for real SMS/email delivery.

## Academic Defense Notes

For final-year presentation, highlight:

- GA optimization strategy and adaptive mutation
- Microservice decomposition and gateway governance
- Dynamic AI adjustment workflows
- Event-driven reminder processing (Celery + Redis)
- Security, auditing, and operational observability patterns
