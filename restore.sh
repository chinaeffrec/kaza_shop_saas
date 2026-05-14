#!/usr/bin/env bash
# Kaza Shop — Восстановление из бэкапа
# Использование: sudo bash restore.sh [путь_к_архиву.tar.gz]
set -euo pipefail

INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${INSTALL_DIR}/.env" 2>/dev/null || true

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓${NC} $*"; }
warn() { echo -e "${YELLOW}⚠${NC}  $*"; }
info() { echo -e "${BLUE}→${NC} $*"; }
err()  { echo -e "${RED}✗ ОШИБКА:${NC} $*"; exit 1; }

[[ "$EUID" -ne 0 ]] && err "Запустите от root: sudo bash restore.sh"

BACKUP_DIR="${INSTALL_DIR}/backups"
DB_USER="${DB_USER:-kaza_user}"
DB_NAME="${DB_NAME:-kaza_shop}"
COMPOSE_FILE="${INSTALL_DIR}/docker-compose.prod.yml"

# ── Выбор бэкапа ─────────────────────────────────────────────────────────────
if [[ -n "${1:-}" && -f "$1" ]]; then
    ARCHIVE="$1"
else
    echo -e "\n${BOLD}Доступные бэкапы:${NC}"
    mapfile -t BACKUPS < <(find "$BACKUP_DIR" \( -name "kaza_backup_*.tar.gz" -o -name "kaza_backup_*.tar.gz.enc" \) ! -name "kaza_backup_last_stable*" | sort -r)
    if [[ ${#BACKUPS[@]} -eq 0 ]]; then
        err "Бэкапы не найдены в ${BACKUP_DIR}"
    fi
    for i in "${!BACKUPS[@]}"; do
        SIZE=$(du -sh "${BACKUPS[$i]}" | cut -f1)
        echo "  [$i] ${BACKUPS[$i]##*/}  (${SIZE})"
    done
    echo ""
    read -rp "Выберите номер бэкапа (0, 1, ...): " IDX
    [[ "$IDX" =~ ^[0-9]+$ && "$IDX" -lt "${#BACKUPS[@]}" ]] \
        || err "Неверный номер"
    ARCHIVE="${BACKUPS[$IDX]}"
fi

[[ ! -f "$ARCHIVE" ]] && err "Файл не найден: $ARCHIVE"
ok "Бэкап выбран: ${ARCHIVE##*/}"

echo ""
warn "╔══════════════════════════════════════════════════════════╗"
warn "║  ВНИМАНИЕ: ВСЕ ТЕКУЩИЕ ДАННЫЕ БУДУТ ЗАМЕНЕНЫ!           ║"
warn "║  Каталог, заказы, настройки — всё из бэкапа.            ║"
warn "╚══════════════════════════════════════════════════════════╝"
echo ""
read -rp "  Введите YES (заглавными) для подтверждения: " CONFIRM
[[ "$CONFIRM" == "YES" ]] || { info "Отменено."; exit 0; }

# ── Аварийный бэкап текущего состояния ───────────────────────────────────────
echo ""
info "Создаём аварийный бэкап текущего состояния перед восстановлением..."
if bash "${INSTALL_DIR}/backup.sh" --silent 2>/dev/null; then
    ok "Аварийный бэкап создан (можно найти в ${BACKUP_DIR})"
else
    warn "Не удалось создать аварийный бэкап (возможно, БД уже недоступна). Продолжаем."
fi

# ── Распаковка архива ─────────────────────────────────────────────────────────
TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

# ── Расшифровка зашифрованного архива ─────────────────────────────────────────
if [[ "$ARCHIVE" == *.enc ]]; then
    [[ -z "${BACKUP_ENCRYPTION_KEY:-}" ]] && \
        err "Архив зашифрован, но BACKUP_ENCRYPTION_KEY не задан в .env"
    info "Расшифровываем архив (AES-256-CBC)..."
    DECRYPTED="${TMP_DIR}/backup.tar.gz"
    if openssl enc -d -aes-256-cbc -pbkdf2 -iter 600000 \
            -pass pass:"${BACKUP_ENCRYPTION_KEY}" \
            -in  "${ARCHIVE}" \
            -out "${DECRYPTED}"; then
        ARCHIVE="${DECRYPTED}"
        ok "Архив расшифрован"
    else
        err "Ошибка расшифровки. Проверьте BACKUP_ENCRYPTION_KEY в .env"
    fi
fi

info "Распаковываем архив..."
tar -xzf "$ARCHIVE" -C "$TMP_DIR"
BACKUP_CONTENT=$(find "$TMP_DIR" -maxdepth 1 -mindepth 1 -type d | head -1)
[[ -z "$BACKUP_CONTENT" ]] && err "Архив пустой или имеет неверную структуру"
ok "Архив распакован: ${BACKUP_CONTENT##*/}"

# ── Проверка содержимого ──────────────────────────────────────────────────────
[[ -f "${BACKUP_CONTENT}/database.sql" ]] || err "database.sql не найден в архиве"
DB_DUMP_SIZE=$(du -sh "${BACKUP_CONTENT}/database.sql" | cut -f1)
ok "Дамп БД: ${DB_DUMP_SIZE}"

# ── Остановка app и bot (db оставляем работать для восстановления) ────────────
info "Останавливаем app и bot..."
cd "$INSTALL_DIR"
docker compose -f "$COMPOSE_FILE" stop app bot 2>/dev/null || true
sleep 3
ok "app и bot остановлены"

# ── Очистка схемы БД ─────────────────────────────────────────────────────────
# ВАЖНО: это обязательный шаг — без него pg_dump (даже с --clean) может
# столкнуться с несоответствиями после прерванного предыдущего восстановления
info "Очищаем схему базы данных..."

# Завершаем все активные соединения с БД (кроме нашего)
docker compose -f "$COMPOSE_FILE" exec -T db \
    psql -U "${DB_USER}" "${DB_NAME}" --no-password \
    -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity
        WHERE datname = '${DB_NAME}' AND pid <> pg_backend_pid();" \
    2>/dev/null || true

# Полностью сбрасываем схему и создаём заново
docker compose -f "$COMPOSE_FILE" exec -T db \
    psql -U "${DB_USER}" "${DB_NAME}" --no-password \
    -c "DROP SCHEMA public CASCADE;" \
    -c "CREATE SCHEMA public;" \
    -c "GRANT ALL ON SCHEMA public TO ${DB_USER};" \
    -c "GRANT ALL ON SCHEMA public TO public;" \
    || err "Не удалось очистить схему БД. Убедитесь, что контейнер db запущен:
  docker compose -f ${COMPOSE_FILE} ps db"
ok "Схема БД очищена"

# ── Восстановление данных ─────────────────────────────────────────────────────
info "Восстанавливаем базу данных (${DB_DUMP_SIZE})..."
if docker compose -f "$COMPOSE_FILE" exec -T db \
    psql -U "${DB_USER}" "${DB_NAME}" --no-password \
    < "${BACKUP_CONTENT}/database.sql"; then
    ok "БД восстановлена"
else
    # Если ошибка — пытаемся восстановить из аварийного бэкапа
    warn "Ошибка при восстановлении БД."
    warn "Аварийный бэкап текущего состояния (если был создан) находится в ${BACKUP_DIR}"
    warn "Для ручного восстановления: bash restore.sh и выберите аварийный бэкап"
    err "Восстановление прервано."
fi

# ── Медиафайлы ────────────────────────────────────────────────────────────────
if [[ -f "${BACKUP_CONTENT}/media.tar.gz" ]]; then
    info "Восстанавливаем медиафайлы..."
    # Сохраняем текущие медиафайлы как резерв
    if [[ -d "${INSTALL_DIR}/media" ]]; then
        mv "${INSTALL_DIR}/media" "${INSTALL_DIR}/media.restore_bak" 2>/dev/null || true
    fi
    if tar -xzf "${BACKUP_CONTENT}/media.tar.gz" -C "${INSTALL_DIR}/"; then
        rm -rf "${INSTALL_DIR}/media.restore_bak" 2>/dev/null || true
        ok "Медиафайлы восстановлены"
    else
        warn "Ошибка при распаковке медиафайлов"
        # Возвращаем резервную копию
        rm -rf "${INSTALL_DIR}/media" 2>/dev/null || true
        [[ -d "${INSTALL_DIR}/media.restore_bak" ]] \
            && mv "${INSTALL_DIR}/media.restore_bak" "${INSTALL_DIR}/media"
    fi
else
    info "Медиафайлы в бэкапе не найдены (пропускаем)"
fi

# ── Корректируем права на медиадиректорию ─────────────────────────────────────
chown -R 1000:1000 "${INSTALL_DIR}/media" 2>/dev/null || true

# ── Сброс Redis-кэша (чтобы не осталось устаревших данных) ────────────────────
# Redis поднимается первым; если уже запущен — сбрасываем кэш сразу,
# иначе он запустится с docker compose up -d ниже с чистым состоянием.
if docker compose -f "$COMPOSE_FILE" ps redis 2>/dev/null | grep -q "running"; then
    docker compose -f "$COMPOSE_FILE" exec -T redis redis-cli FLUSHALL >/dev/null 2>&1 \
        && info "Redis кэш сброшен" || true
fi

# ── Запуск сервисов ───────────────────────────────────────────────────────────
info "Запускаем все сервисы..."
docker compose -f "$COMPOSE_FILE" up -d
echo ""

info "Ожидаем готовности API (до 2 минут)..."
API_READY=0
for i in $(seq 1 24); do
    sleep 5
    HTTP=$(curl -sf -o /dev/null -w "%{http_code}" \
        --max-time 10 "http://localhost:8000/health" 2>/dev/null || echo "000")
    if [[ "$HTTP" == "200" ]]; then
        API_READY=1
        break
    fi
    echo -n "."
done
echo ""

if [[ $API_READY -eq 1 ]]; then
    echo ""
    echo -e "${BOLD}${GREEN}════════════════════════════════════════${NC}"
    echo -e "${BOLD}${GREEN}  ✓ Восстановление завершено успешно!${NC}"
    echo -e "${BOLD}${GREEN}════════════════════════════════════════${NC}"
    echo ""
    ok "API работает нормально"
    ok "Данные восстановлены из: ${ARCHIVE##*/}"
else
    echo ""
    warn "═══════════════════════════════════════════════"
    warn "  API не ответил после восстановления."
    warn "═══════════════════════════════════════════════"
    warn ""
    warn "Диагностика:"
    warn "  docker compose -f ${COMPOSE_FILE} logs app --tail=50"
    warn ""
    warn "Если в логах ошибки Alembic — попробуйте:"
    warn "  docker compose -f ${COMPOSE_FILE} restart app"
    warn ""
    warn "Если ошибки с паролем БД (FATAL: password):"
    warn "  Бэкап мог быть создан с другими параметрами подключения."
    warn "  Проверьте .env.backup внутри архива бэкапа:"
    warn "    tar -tzf ${ARCHIVE} | grep .env"
    warn "    tar -xzf ${ARCHIVE} --wildcards '*/.env.backup' -O"
fi
