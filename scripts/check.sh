#!/bin/sh
set -eu

echo '=== Containers ==='
docker compose ps

echo
echo '=== SIP registrations ==='
docker compose exec asterisk asterisk -rx 'pjsip show registrations' || true
echo
echo '=== Endpoints ==='
docker compose exec asterisk asterisk -rx 'pjsip show endpoints' || true
echo
echo '=== App logs (last 50) ==='
docker compose logs --tail=50 app || true
