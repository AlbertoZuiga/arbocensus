#!/usr/bin/env bash
set -euo pipefail

# Provisions a fresh Ubuntu 24.04 droplet into a running Arbocensus production
# stack. Idempotent: safe to re-run after fixing a failed step.
#
#   apt-get update && apt-get install -y git
#   git clone https://github.com/AlbertoZuiga/arbocensus-routing.git /srv/arbocensus
#   bash /srv/arbocensus/scripts/bootstrap-droplet.sh

TARGET_DIR="/srv/arbocensus"
DEPLOY_USER="deploy"
REPO_URL="https://github.com/AlbertoZuiga/arbocensus-routing.git"
BRANCH="production"
SWAP_FILE="/swapfile"
SWAP_SIZE="2G"

bold() { printf '\n\033[1m== %s\033[0m\n' "$1"; }
info() { printf '   %s\n' "$1"; }
die() { printf '\n\033[31mERROR: %s\033[0m\n' "$1" >&2; exit 1; }

ask() { # ask VAR "prompt" "default"
  local __var=$1 __prompt=$2 __default=${3:-} __reply
  if [ -n "$__default" ]; then
    read -r -p "   $__prompt [$__default]: " __reply
  else
    read -r -p "   $__prompt: " __reply
  fi
  __reply=${__reply//$'\r'/}
  printf -v "$__var" '%s' "${__reply:-$__default}"
}

# `|| true` swallows tr's SIGPIPE (141) when head closes the pipe, which under
# `set -eo pipefail` would abort the whole script.
randstr() { tr -dc 'A-Za-z0-9' </dev/urandom | head -c "${1:-48}" || true; }

[ "$(id -u)" -eq 0 ] || die "run as root"

# ── 1. System packages ────────────────────────────────────────────────────────
bold "1/10 Paquetes del sistema"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq docker.io docker-compose-v2 git curl ufw cron
systemctl enable --now docker >/dev/null
info "docker $(docker --version | awk '{print $3}' | tr -d ,) · compose $(docker compose version --short)"

# ── 2. Swap ───────────────────────────────────────────────────────────────────
bold "2/10 Swap ($SWAP_SIZE)"
if swapon --show | grep -q "$SWAP_FILE"; then
  info "ya activo"
else
  fallocate -l "$SWAP_SIZE" "$SWAP_FILE"
  chmod 600 "$SWAP_FILE"
  mkswap "$SWAP_FILE" >/dev/null
  swapon "$SWAP_FILE"
  grep -q "$SWAP_FILE" /etc/fstab || echo "$SWAP_FILE none swap sw 0 0" >>/etc/fstab
  info "creado y montado"
fi

# ── 3. Firewall ───────────────────────────────────────────────────────────────
bold "3/10 Firewall"
ufw allow 22 >/dev/null
ufw allow 80 >/dev/null
ufw allow 443 >/dev/null
ufw --force enable >/dev/null
info "22, 80, 443 abiertos"

# ── 4. Usuario deploy ─────────────────────────────────────────────────────────
bold "4/10 Usuario $DEPLOY_USER"
id "$DEPLOY_USER" >/dev/null 2>&1 || useradd -m -s /bin/bash "$DEPLOY_USER"
usermod -aG docker "$DEPLOY_USER"
install -d -m 700 -o "$DEPLOY_USER" -g "$DEPLOY_USER" "/home/$DEPLOY_USER/.ssh"

KEY_PATH="/home/$DEPLOY_USER/.ssh/arbocensus_deploy"
AUTH="/home/$DEPLOY_USER/.ssh/authorized_keys"
touch "$AUTH"

authorize() { # authorize PUBKEY
  grep -qF "$1" "$AUTH" || echo "$1" >>"$AUTH"
  chown "$DEPLOY_USER:$DEPLOY_USER" "$AUTH"
  chmod 600 "$AUTH"
}

info "GitHub Actions entra al droplet como '$DEPLOY_USER' con una llave SSH."

# DigitalOcean copia las públicas elegidas al crear el droplet en el
# authorized_keys de root; las ofrecemos para no pedir copiar y pegar.
FOUND_KEYS=()
while read -r line; do
  case "$line" in
    ssh-*|ecdsa-*) FOUND_KEYS+=("$line") ;;
  esac
done < <(cat /root/.ssh/authorized_keys "$AUTH" 2>/dev/null | sort -u)

MENU_MAX=0
for i in "${!FOUND_KEYS[@]}"; do
  MENU_MAX=$((i + 1))
  info "  $MENU_MAX) usar llave ya instalada: $(ssh-keygen -lf /dev/stdin <<<"${FOUND_KEYS[$i]}" |
    awk '{print $2, $NF, $3}')"
done
N=$MENU_MAX
if [ -f "$KEY_PATH" ]; then
  OPT_KEEP=$((++N))
  info "  $OPT_KEEP) conservar el par ya generado en $KEY_PATH (default)"
  OPT_NEW=$((++N))
  info "  $OPT_NEW) regenerar ese par (invalida el secreto DEPLOY_SSH_KEY actual)"
  DEFAULT_CHOICE=$OPT_KEEP
else
  OPT_KEEP=-1
  OPT_NEW=$((++N))
  info "  $OPT_NEW) generar un par nuevo aquí e imprimir la privada al final (default)"
  DEFAULT_CHOICE=$OPT_NEW
fi
OPT_PASTE=$((++N))
info "  $OPT_PASTE) pegar otra llave pública"
OPT_SKIP=$((++N))
info "  $OPT_SKIP) omitir — ya la autorizaste por otra vía"
ask KEY_CHOICE "Opción" "$DEFAULT_CHOICE"

generate_pair() {
  rm -f "$KEY_PATH" "$KEY_PATH.pub"
  sudo -u "$DEPLOY_USER" ssh-keygen -t ed25519 -f "$KEY_PATH" -N "" -C "github-actions" >/dev/null
}

PRINT_PRIVATE_KEY=false
if [ "$KEY_CHOICE" -ge 1 ] 2>/dev/null && [ "$KEY_CHOICE" -le "$MENU_MAX" ]; then
  authorize "${FOUND_KEYS[$((KEY_CHOICE - 1))]}"
  info "llave autorizada para $DEPLOY_USER"
  info "OJO: DEPLOY_SSH_KEY debe ser la privada que le corresponde. Si es tu llave"
  info "     personal, estarás subiéndola a GitHub — prefiere un par dedicado."
elif [ "$KEY_CHOICE" = "$OPT_NEW" ]; then
  generate_pair
  authorize "$(cat "$KEY_PATH.pub")"
  PRINT_PRIVATE_KEY=true
  info "par generado"
elif [ "$KEY_CHOICE" = "$OPT_KEEP" ]; then
  authorize "$(cat "$KEY_PATH.pub")"
  PRINT_PRIVATE_KEY=true
  info "par conservado"
elif [ "$KEY_CHOICE" = "$OPT_PASTE" ]; then
  ask PUBKEY "Pega la llave pública (ssh-ed25519 AAAA...)" ""
  [ -n "$PUBKEY" ] || die "llave pública vacía"
  authorize "$PUBKEY"
  info "llave pública autorizada"
elif [ "$KEY_CHOICE" = "$OPT_SKIP" ]; then
  [ -s "$AUTH" ] || die "authorized_keys de $DEPLOY_USER está vacío: el deploy no podrá entrar"
  info "omitido — se usa lo que ya está en authorized_keys"
else
  die "opción inválida: $KEY_CHOICE"
fi

# ── 5. Checkout ───────────────────────────────────────────────────────────────
bold "5/10 Repositorio en $TARGET_DIR"
if [ -d "$TARGET_DIR/.git" ]; then
  info "ya existe, se conserva"
else
  git clone --branch "$BRANCH" "$REPO_URL" "$TARGET_DIR" 2>/dev/null ||
    git clone "$REPO_URL" "$TARGET_DIR"
fi
git config --global --add safe.directory "$TARGET_DIR"
cd "$TARGET_DIR"
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
info "rama $CURRENT_BRANCH"
[ "$CURRENT_BRANCH" = "$BRANCH" ] ||
  info "AVISO: el workflow de deploy hace reset --hard a origin/$BRANCH"

# ── 6. Variables de entorno ───────────────────────────────────────────────────
bold "6/10 Configuración (.env)"
if [ -f .env ]; then
  info ".env ya existe — se conserva. Bórralo y re-ejecuta para regenerarlo."
else
  PUBLIC_IP=$(curl -fsS --max-time 5 https://api.ipify.org || echo "")
  ask SITE_ADDRESS "Dominio (vacío = ${PUBLIC_IP:-IP}.sslip.io)" "${PUBLIC_IP:+$PUBLIC_IP.sslip.io}"
  [ -n "$SITE_ADDRESS" ] || die "sin dominio ni IP pública detectable"
  ask ADMIN_USER "Usuario admin" "admin"
  ask ADMIN_EMAIL "Email admin" "admin@example.com"
  ask ADMIN_PASSWORD "Password admin (vacío = aleatorio)" ""
  [ -n "$ADMIN_PASSWORD" ] || { ADMIN_PASSWORD=$(randstr 20); info "password generado: $ADMIN_PASSWORD"; }
  ask LEGACY_API_DB_URL "ARBOCENSUS_API_DB_URL legado (opcional)" ""
  ask LEGACY_DB_URL "ARBOCENSUS_DB_URL legado (opcional)" ""

  GHCR_OWNER=$(git remote get-url origin |
    sed -E 's#.*[:/]([^/]+)/[^/]+(\.git)?$#\1#' | tr '[:upper:]' '[:lower:]')

  cat >.env <<EOF
SECRET_KEY=$(randstr 64)
DEBUG=false
ALLOWED_HOSTS=$SITE_ADDRESS
CSRF_TRUSTED_ORIGINS=https://$SITE_ADDRESS

DB_HOST=db
DB_PORT=5432
DB_NAME=arbocensus
DB_USER=arbocensus
DB_PASSWORD=$(randstr 32)

REDIS_URL=redis://redis:6379/0

OSRM_URL=http://osrm:5000
OSM_REGION=santiago

ARBOCENSUS_API_DB_URL=$LEGACY_API_DB_URL
ARBOCENSUS_DB_URL=$LEGACY_DB_URL

CORS_ALLOWED_ORIGINS=

DJANGO_SUPERUSER_USERNAME=$ADMIN_USER
DJANGO_SUPERUSER_EMAIL=$ADMIN_EMAIL
DJANGO_SUPERUSER_PASSWORD=$ADMIN_PASSWORD

SITE_ADDRESS=$SITE_ADDRESS

GHCR_OWNER=$GHCR_OWNER
IMAGE_TAG=production
EOF
  info ".env escrito (GHCR_OWNER=$GHCR_OWNER, SITE_ADDRESS=$SITE_ADDRESS)"
fi
chmod 600 .env

# ── 7. Extracto OSM ───────────────────────────────────────────────────────────
bold "7/10 Extracto OSM del Gran Santiago"
bash scripts/osm-extract-santiago.sh

chown -R "$DEPLOY_USER:$DEPLOY_USER" "$TARGET_DIR"

# ── 8. Imágenes ───────────────────────────────────────────────────────────────
bold "8/10 Imágenes de contenedor"
COMPOSE=(sudo -u "$DEPLOY_USER" docker compose -f docker-compose.production.yml)
if "${COMPOSE[@]}" pull backend caddy 2>/dev/null; then
  info "descargadas desde GHCR"
else
  info "GHCR no disponible (imágenes privadas o aún no publicadas) — construyendo local"
  "${COMPOSE[@]}" build backend caddy
fi

# ── 9. Levantar el stack ──────────────────────────────────────────────────────
bold "9/10 Levantando servicios"
"${COMPOSE[@]}" up -d --remove-orphans
info "OSRM procesa el PBF en el primer arranque: 5-15 min hasta quedar healthy"

# ── 10. Backup diario ─────────────────────────────────────────────────────────
bold "10/10 Backup diario"
CRON_LINE="0 3 * * * $TARGET_DIR/scripts/pg-backup.sh >> /var/log/arbocensus-backup.log 2>&1"
if crontab -l 2>/dev/null | grep -qF "pg-backup.sh"; then
  info "cron ya configurado"
else
  (crontab -l 2>/dev/null; echo "$CRON_LINE") | crontab -
  info "cron 03:00, retención 7 días, dumps en $TARGET_DIR/backups/"
fi

# ── Resumen ───────────────────────────────────────────────────────────────────
SITE=$(grep '^SITE_ADDRESS=' .env | cut -d= -f2-)
cat <<EOF

────────────────────────────────────────────────────────────────────────────────
LISTO. Sitio: https://$SITE   (Caddy emite el certificado al primer request)

Estado:   cd $TARGET_DIR && docker compose -f docker-compose.production.yml ps
Logs:     docker compose -f docker-compose.production.yml logs -f backend osrm

Para habilitar el deploy automático, crea estos secretos en
GitHub → Settings → Secrets and variables → Actions:

  DEPLOY_HOST     $(curl -fsS --max-time 5 https://api.ipify.org || echo "<IP del droplet>")
  DEPLOY_USER     $DEPLOY_USER
  DEPLOY_SSH_KEY  la clave privada que corresponde a la pública autorizada
EOF

if [ "$PRINT_PRIVATE_KEY" = true ]; then
  cat <<EOF
──────── clave privada de deploy (pegar completa, incluidas BEGIN/END) ────────
$(cat "$KEY_PATH")
EOF
else
  echo "   (la privada la tienes tú: no se generó ninguna en el droplet)"
fi
echo "────────────────────────────────────────────────────────────────────────────────"
