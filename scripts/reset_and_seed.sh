#!/usr/bin/env bash
# Full reset: apply pending migrations, wipe all data, seed 5 universities.
#
# Usage (from project root):
#   bash scripts/reset_and_seed.sh
#
# Services must be running first:  docker compose up -d
set -e

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║       Shedulex  —  Full Reset & Seed (5 Universities)    ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

echo "Step 1/4 — Applying auth-service migrations…"
docker compose exec -T auth-service flask db upgrade

echo ""
echo "Step 2/4 — Applying timetable-engine migrations…"
docker compose exec -T timetable-engine flask db upgrade

echo ""
echo "Step 3/4 — Seeding timetable-engine (universities, resources)…"
docker compose exec -T timetable-engine python seed_fresh.py

echo ""
echo "Step 4/4 — Seeding auth-service (user accounts)…"
docker compose exec -T auth-service python seed_users.py

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  All done! Open http://localhost:5173 and log in.        ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "Admin logins (password: Admin@2026):"
echo "  STR  →  admin@str.shedulex.ac"
echo "  UON  →  admin@uon.shedulex.ac"
echo "  KU   →  admin@ku.shedulex.ac"
echo "  MU   →  admin@mu.shedulex.ac"
echo "  TUK  →  admin@tuk.shedulex.ac"
echo ""
echo "Also available per university:"
echo "  Timetable Officer  →  officer@<code>.shedulex.ac  /  Officer@2026"
echo "  Head of Dept       →  hod@<code>.shedulex.ac      /  Hod@2026"
echo "  Lecturer           →  lect@<code>.shedulex.ac     /  Lect@2026"
echo ""
