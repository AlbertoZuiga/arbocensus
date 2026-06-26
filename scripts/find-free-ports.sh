#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${ENV_FILE:-.env}"

is_free() {
  local port="$1"
  ! lsof -iTCP:"$port" -sTCP:LISTEN -P -n >/dev/null 2>&1
}

find_free_port() {
  local port="$1"
  while ! is_free "$port"; do
    port=$((port + 1))
  done
  printf '%s' "$port"
}

set_env_var() {
  local key="$1" value="$2"
  touch "$ENV_FILE"
  if grep -qE "^${key}=" "$ENV_FILE"; then
    local tmp
    tmp="$(mktemp)"
    grep -vE "^${key}=" "$ENV_FILE" >"$tmp"
    mv "$tmp" "$ENV_FILE"
  fi
  printf '%s=%s\n' "$key" "$value" >>"$ENV_FILE"
}

backend_port="$(find_free_port "${BACKEND_PORT:-8000}")"
db_host_port="$(find_free_port "${DB_HOST_PORT:-5433}")"

set_env_var BACKEND_PORT "$backend_port"
set_env_var DB_HOST_PORT "$db_host_port"

printf 'BACKEND_PORT=%s\n' "$backend_port"
printf 'DB_HOST_PORT=%s\n' "$db_host_port"
