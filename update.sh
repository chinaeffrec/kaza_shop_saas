#!/usr/bin/env bash
# Kaza Shop — Обновление сервиса на сервере
# Использование: sudo bash update.sh
set -euo pipefail

INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${INSTALL_DIR}/.env" 2>/dev/null || true

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓${NC} $*"; }
warn() { echo -e "${YELLOW}⚠${NC}  $*"; }
info() { echo -e "${BLUE}→${NC} $*"; }
err()  { echo -e "${RED}✗${NC} $*"; }

[[ "$EUID" -ne 0 ]] && { err "Запустите от root: sudo bash update.sh"; exit 1; }

ALERT_BOT_TOKEN="${ALERT_BOT_TOKEN:-${BOT_TOKEN:-}}"
ALERT_CHAT_ID="${ALERT_CHAT_ID:-${ADMIN_TG_ID:-}}"
UPDATE_CHANNEL="${UPDATE_CHANNEL:-}"
UPDATE_BRANCH="${UPDATE_BRANCH:-main}"
UPDATE_ARCHIVE_URL="${UPDATE_ARCHIVE_URL:-}"
COMPOSE_FILE="${INSTALL_DIR}/docker-compose.prod.yml"

validate_migrations() {
    python3 - <<'PY'
from pathlib import Path
import sys

base = Path("/opt/kaza_shop/alembic/versions")
files = sorted(p for p in base.glob("*.py") if not p.name.startswith("._"))
if not files:
    print("ERROR: alembic/versions пуст")
    sys.exit(1)

for p in files:
    b = p.read_bytes()
    if b"\x00" in b:
        print(f"ERROR: null bytes detected in {p}")
        sys.exit(1)
    try:
        compile(b.decode("utf-8"), str(p), "exec")
    except Exception as e:
        print(f"ERROR: invalid migration file {p}: {e}")
        sys.exit(1)
print("Alembic migrations: OK")
PY
}

send_telegram() {
    local text="$1"
    [[ -z "$ALERT_BOT_TOKEN" || -z "$ALERT_CHAT_ID" ]] && return 0
    curl -sf "https://api.telegram.org/bot${ALERT_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${ALERT_CHAT_ID}" -d "parse_mode=HTML" \
        --data-urlencode "text=${text}" >/dev/null 2>&1 || true
}

send_telegram_document() {
    local file_path="$1"
    local caption="${2:-}"
    [[ -z "$ALERT_BOT_TOKEN" || -z "$ALERT_CHAT_ID" ]] && return 0
    [[ ! -f "$file_path" ]] && return 0
    local file_size
    file_size=$(stat -c%s "$file_path" 2>/dev/null || stat -f%z "$file_path" 2>/dev/null || echo 0)
    if [[ "$file_size" -gt 47185920 ]]; then
        send_telegram "⚠️ Бэкап перед обновлением создан ($(du -sh "$file_path" | cut -f1)), но слишком велик для Telegram.
Скачайте по SFTP: <code>${file_path}</code>"
        return 0
    fi
    curl -sf "https://api.telegram.org/bot${ALERT_BOT_TOKEN}/sendDocument" \
        -F "chat_id=${ALERT_CHAT_ID}" \
        -F "parse_mode=HTML" \
        -F "caption=${caption}" \
        -F "document=@${file_path}" >/dev/null 2>&1 \
    || send_telegram "⚠️ Бэкап создан, но файл не удалось отправить в Telegram." || true
}

echo -e "\n${BOLD}Kaza Shop — Обновление${NC}"
echo "────────────────────────────────────────"
cd "$INSTALL_DIR"

info "Проверяем миграции текущей версии..."
validate_migrations
ok "Текущие миграции валидны"

# ── Шаг 1: Бэкап + отправка в Telegram ───────────────────────────────────────
info "Создаём бэкап данных перед обновлением..."
BACKUP_CREATED=0
if bash "${INSTALL_DIR}/backup.sh" --silent 2>/dev/null; then
    BACKUP_CREATED=1
    ok "Бэкап создан"
else
    warn "Бэкап не создан."
    read -rp "  Продолжить без бэкапа? (y/N): " C
    [[ "$C" =~ ^[Yy]$ ]] || exit 1
fi

if [[ $BACKUP_CREATED -eq 1 ]]; then
    # Находим только что созданный бэкап
    LATEST_BACKUP=$(find "${INSTALL_DIR}/backups" -name "kaza_backup_2*.tar.gz" | sort -r | head -1 || echo "")
    if [[ -n "$LATEST_BACKUP" ]]; then
        TIMESTAMP_DISPLAY=$(date '+%d.%m.%Y %H:%M')
        BACKUP_SIZE=$(du -sh "$LATEST_BACKUP" 2>/dev/null | cut -f1 || echo "?")
        CAPTION="📦 <b>Бэкап перед обновлением Kaza Shop</b>
📅 ${TIMESTAMP_DISPLAY}
📦 Размер: ${BACKUP_SIZE}

Сохраните этот файл! Если обновление пройдёт с ошибкой, его можно использовать для восстановления:
1. Установите сервис: <code>bash install.sh</code>
2. Поместите файл в <code>/opt/kaza_shop/backups/</code>
3. Восстановите: <code>sudo bash /opt/kaza_shop/restore.sh</code>"
        info "Отправляем бэкап в Telegram..."
        send_telegram_document "$LATEST_BACKUP" "$CAPTION"
        ok "Бэкап отправлен в Telegram"
    fi
fi

# ── Шаг 2: Снимок кода для отката ────────────────────────────────────────────
TS="$(date +%Y%m%d_%H%M%S)"
CODE_BACKUP="/tmp/kaza_code_backup_${TS}.tar.gz"
tar -czf "$CODE_BACKUP" \
    --exclude './media' --exclude './data' --exclude './logs' \
    --exclude './backups' --exclude './.git' --exclude './.venv' .
ok "Снимок кода для отката: $CODE_BACKUP"

OLD_COMMIT="$(git rev-parse HEAD 2>/dev/null || echo "")"
OLD_IMAGE="$(docker compose -f "$COMPOSE_FILE" images -q app 2>/dev/null | head -1 || echo "")"
if [[ -n "$OLD_IMAGE" ]]; then
    docker tag "$OLD_IMAGE" kaza_rollback:pre-update >/dev/null 2>&1 || true
fi

# ── Шаг 3: Получение новой версии ────────────────────────────────────────────
NEW_VERSION="unknown"
UPDATED_FROM="none"

is_git_repo() {
    git rev-parse --is-inside-work-tree >/dev/null 2>&1
}

update_from_git() {
    local branch="${UPDATE_BRANCH:-main}"
    info "Источник обновления: git (${branch})"
    git fetch --all --prune
    git checkout "$branch"
    git pull --ff-only origin "$branch"
    NEW_VERSION="$(git describe --tags --always 2>/dev/null || git rev-parse --short HEAD)"
    UPDATED_FROM="git"
}

update_from_archive() {
    local url="$UPDATE_ARCHIVE_URL"
    [[ -z "$url" ]] && return 1
    info "Источник обновления: archive (${url})"
    local tmp_dir tmp_archive
    tmp_dir="$(mktemp -d)"
    tmp_archive="${tmp_dir}/release.tar.gz"

    # Поддержка локальных файлов (file://) и URL
    if [[ "$url" == file://* ]]; then
        local local_path="${url#file://}"
        [[ -f "$local_path" ]] || { warn "Файл не найден: $local_path"; rm -rf "$tmp_dir"; return 1; }
        cp "$local_path" "$tmp_archive"
    else
        curl -fL --connect-timeout 20 --max-time 300 "$url" -o "$tmp_archive"
    fi

    tar -xzf "$tmp_archive" -C "$tmp_dir"
    local src_dir=""
    src_dir="$(find "$tmp_dir" -mindepth 1 -maxdepth 1 -type d | head -1)"
    [[ -z "$src_dir" ]] && src_dir="$tmp_dir"

    rsync -a --delete \
        --exclude '.env' --exclude 'media/' --exclude 'data/' \
        --exclude 'logs/' --exclude 'backups/' \
        --exclude '.git/' --exclude '.venv/' \
        "${src_dir}/" "${INSTALL_DIR}/"

    NEW_VERSION="$(date +%Y%m%d_%H%M%S)"
    UPDATED_FROM="archive"
    rm -rf "$tmp_dir"
}

if [[ "${UPDATE_CHANNEL}" == "git" || -z "${UPDATE_CHANNEL}" ]]; then
    if is_git_repo; then
        if update_from_git; then
            ok "Код обновлён из git"
        else
            warn "Не удалось обновить из git."
            [[ -n "$UPDATE_ARCHIVE_URL" ]] && update_from_archive
        fi
    else
        [[ -n "$UPDATE_ARCHIVE_URL" ]] && update_from_archive
    fi
elif [[ "${UPDATE_CHANNEL}" == "archive" ]]; then
    update_from_archive
else
    err "Неизвестный UPDATE_CHANNEL=${UPDATE_CHANNEL}"
    exit 1
fi

if [[ "$UPDATED_FROM" == "none" ]]; then
    err "Источник обновления не настроен."
    info "Для установки обновления с архивом используйте deploy.sh или configure-updates.sh"
    exit 1
fi

ok "Версия: ${NEW_VERSION} (source: ${UPDATED_FROM})"
info "Проверяем миграции новой версии..."
validate_migrations
ok "Новые миграции валидны"

# ── Шаг 4: Сборка и перезапуск ───────────────────────────────────────────────
info "Собираем и применяем обновление..."
docker compose -f "$COMPOSE_FILE" build --no-cache
docker compose -f "$COMPOSE_FILE" up -d --remove-orphans

# ── Шаг 5: Health-check ──────────────────────────────────────────────────────
info "Проверяем работоспособность..."
sleep 10
for i in $(seq 1 6); do
    HTTP=$(curl -sf -o /dev/null -w "%{http_code}" \
        --max-time 10 "http://localhost:8000/health" 2>/dev/null || echo "000")
    if [[ "$HTTP" == "200" ]]; then
        ok "Сервис работает корректно"
        send_telegram "✅ <b>Обновление завершено</b>
📅 $(date '+%d.%m.%Y %H:%M')
Версия: ${NEW_VERSION}
Источник: ${UPDATED_FROM}"
        echo -e "\n${GREEN}${BOLD}Обновление выполнено успешно!${NC}"
        exit 0
    fi
    warn "Попытка ${i}/6: HTTP ${HTTP}, ждём 10 сек..."
    sleep 10
done

# ── Rollback ──────────────────────────────────────────────────────────────────
warn "Сервис не ответил после обновления. Выполняем откат..."
send_telegram "🔴 <b>Ошибка обновления</b>
📅 $(date '+%d.%m.%Y %H:%M')
Выполняется автоматический откат..."

docker compose -f "$COMPOSE_FILE" down || true

if [[ "$UPDATED_FROM" == "git" && -n "$OLD_COMMIT" ]] && is_git_repo; then
    git reset --hard "$OLD_COMMIT" >/dev/null 2>&1 || true
else
    tar -xzf "$CODE_BACKUP" -C "$INSTALL_DIR"
fi

if docker image inspect kaza_rollback:pre-update >/dev/null 2>&1; then
    target_image="$(docker compose -f "$COMPOSE_FILE" config --images 2>/dev/null | head -1 || echo kaza_shop_app)"
    docker tag kaza_rollback:pre-update "$target_image" >/dev/null 2>&1 || true
fi

docker compose -f "$COMPOSE_FILE" up -d || true
sleep 15
ROLLBACK_CHECK=$(curl -sf -o /dev/null -w "%{http_code}" \
    --max-time 10 "http://localhost:8000/health" 2>/dev/null || echo "000")
if [[ "$ROLLBACK_CHECK" == "200" ]]; then
    warn "Откат выполнен, сервис восстановлен."
    send_telegram "⚠️ <b>Откат выполнен</b>
Сервис восстановлен до предыдущей версии.
Данные сохранены (бэкап был отправлен в Telegram перед обновлением)."
else
    err "Откат не помог. Требуется ручное вмешательство."
    send_telegram "🆘 <b>Критическая ошибка</b>
Обновление и откат не удались.
Используйте бэкап, отправленный в Telegram перед обновлением, для ручного восстановления:
<code>sudo bash /opt/kaza_shop/restore.sh</code>"
fi
