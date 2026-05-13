#!/usr/bin/env bash
# Kaza Shop — Бэкап БД + медиафайлов
# Использование:
#   bash backup.sh            — ежедневный бэкап (с именем по дате)
#   bash backup.sh --hourly   — почасовой бэкап (фиксированное имя, отправляет файл в Telegram)
#   bash backup.sh --silent   — бэкап без Telegram-уведомлений (для автовызова из других скриптов)
#   bash backup.sh --emergency — аварийный бэкап при падении сервиса
set -euo pipefail

INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${INSTALL_DIR}/.env" 2>/dev/null || true

BACKUP_DIR="${INSTALL_DIR}/backups"
KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"
LOG_PREFIX="[$(date '+%Y-%m-%d %H:%M:%S')] BACKUP"

HOURLY_MODE=0
SILENT_MODE=0
EMERGENCY_MODE=0
for arg in "$@"; do
    [[ "$arg" == "--hourly"    ]] && HOURLY_MODE=1
    [[ "$arg" == "--silent"    ]] && SILENT_MODE=1
    [[ "$arg" == "--emergency" ]] && EMERGENCY_MODE=1
done

if [[ $HOURLY_MODE -eq 1 ]]; then
    BACKUP_NAME="kaza_backup_hourly"
elif [[ $EMERGENCY_MODE -eq 1 ]]; then
    BACKUP_NAME="kaza_backup_emergency_$(date +%Y%m%d_%H%M%S)"
else
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP_NAME="kaza_backup_${TIMESTAMP}"
fi

BACKUP_PATH="${BACKUP_DIR}/${BACKUP_NAME}"
ARCHIVE="${BACKUP_DIR}/${BACKUP_NAME}.tar.gz"

ALERT_BOT_TOKEN="${ALERT_BOT_TOKEN:-${BOT_TOKEN:-}}"
ALERT_CHAT_ID="${ALERT_CHAT_ID:-${ADMIN_TG_ID:-}}"

# ── Утилиты уведомлений ───────────────────────────────────────────────────────
send_telegram() {
    local text="$1"
    [[ $SILENT_MODE -eq 1 ]] && return 0
    [[ -z "${ALERT_BOT_TOKEN:-}" || -z "${ALERT_CHAT_ID:-}" ]] && return 0
    curl -sf "https://api.telegram.org/bot${ALERT_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${ALERT_CHAT_ID}" \
        -d "parse_mode=HTML" \
        --data-urlencode "text=${text}" >/dev/null 2>&1 || true
}

send_telegram_document() {
    local file_path="$1"
    local caption="${2:-}"
    [[ $SILENT_MODE -eq 1 ]] && return 0
    [[ -z "${ALERT_BOT_TOKEN:-}" || -z "${ALERT_CHAT_ID:-}" ]] && return 0
    [[ ! -f "$file_path" ]] && return 0

    # Telegram ограничение: 50 MB для sendDocument через multipart
    local file_size
    file_size=$(stat -c%s "$file_path" 2>/dev/null || stat -f%z "$file_path" 2>/dev/null || echo 0)
    if [[ "$file_size" -gt 47185920 ]]; then
        local size_human
        size_human=$(du -sh "$file_path" 2>/dev/null | cut -f1 || echo "?")
        send_telegram "⚠️ <b>Бэкап создан</b>, но слишком велик для отправки в Telegram (${size_human}).
Скачайте по SFTP: <code>${file_path}</code>"
        return 0
    fi

    if [[ -n "$caption" ]]; then
        curl -sf "https://api.telegram.org/bot${ALERT_BOT_TOKEN}/sendDocument" \
            -F "chat_id=${ALERT_CHAT_ID}" \
            -F "parse_mode=HTML" \
            -F "caption=${caption}" \
            -F "document=@${file_path}" >/dev/null 2>&1 \
        || send_telegram "⚠️ Бэкап создан ($(du -sh "$file_path" 2>/dev/null | cut -f1)), но отправить файл не удалось." || true
    else
        curl -sf "https://api.telegram.org/bot${ALERT_BOT_TOKEN}/sendDocument" \
            -F "chat_id=${ALERT_CHAT_ID}" \
            -F "document=@${file_path}" >/dev/null 2>&1 || true
    fi
}

# ── Подготовка ────────────────────────────────────────────────────────────────
mkdir -p "${BACKUP_DIR}"
echo "${LOG_PREFIX}: Начало бэкапа ${BACKUP_NAME}"
mkdir -p "${BACKUP_PATH}"

# ── БД ────────────────────────────────────────────────────────────────────────
echo "${LOG_PREFIX}: Дамп базы данных..."
# --clean --if-exists: дамп включает DROP IF EXISTS перед каждым CREATE
# это позволяет восстанавливать в непустую БД без ошибок конфликтов
if docker compose -f "${INSTALL_DIR}/docker-compose.prod.yml" exec -T db \
    pg_dump -U "${DB_USER:-kaza_user}" "${DB_NAME:-kaza_shop}" \
    --no-password --clean --if-exists 2>/dev/null \
    > "${BACKUP_PATH}/database.sql"; then
    DB_SIZE=$(du -sh "${BACKUP_PATH}/database.sql" | cut -f1)
    echo "${LOG_PREFIX}: БД сохранена (${DB_SIZE})"
else
    echo "${LOG_PREFIX}: ОШИБКА дампа БД"
    rm -rf "${BACKUP_PATH}"
    send_telegram "⚠️ <b>Бэкап не выполнен</b>

Не удалось создать дамп базы данных.
Проверьте состояние сервиса:
<code>docker compose -f /opt/kaza_shop/docker-compose.prod.yml ps</code>"
    exit 1
fi

# ── Медиафайлы ────────────────────────────────────────────────────────────────
echo "${LOG_PREFIX}: Архивирование медиафайлов..."
MEDIA_SIZE="нет"
if [[ -d "${INSTALL_DIR}/media" ]]; then
    tar -czf "${BACKUP_PATH}/media.tar.gz" \
        -C "${INSTALL_DIR}" media/ 2>/dev/null || true
    MEDIA_SIZE=$(du -sh "${BACKUP_PATH}/media.tar.gz" 2>/dev/null | cut -f1 || echo "0")
    echo "${LOG_PREFIX}: Медиафайлы сохранены (${MEDIA_SIZE})"
fi

# ── .env ──────────────────────────────────────────────────────────────────────
cp "${INSTALL_DIR}/.env" "${BACKUP_PATH}/.env.backup"
chmod 600 "${BACKUP_PATH}/.env.backup"

# ── Итоговый архив ────────────────────────────────────────────────────────────
# Для почасового — удаляем предыдущий
[[ $HOURLY_MODE -eq 1 && -f "$ARCHIVE" ]] && rm -f "$ARCHIVE"

tar -czf "$ARCHIVE" -C "${BACKUP_DIR}" "${BACKUP_NAME}/"
rm -rf "${BACKUP_PATH}"

TOTAL_SIZE=$(du -sh "$ARCHIVE" | cut -f1)
echo "${LOG_PREFIX}: Архив создан: ${ARCHIVE} (${TOTAL_SIZE})"

# Симлинк на последний стабильный бэкап (используется healthcheck при падении)
ln -sf "$(basename "$ARCHIVE")" "${BACKUP_DIR}/kaza_backup_last_stable.tar.gz" 2>/dev/null || true

# ── Ротация (только для ежедневных бэкапов) ────────────────────────────────────
if [[ $HOURLY_MODE -eq 0 && $EMERGENCY_MODE -eq 0 ]]; then
    DELETED=$(find "${BACKUP_DIR}" -name "kaza_backup_2*.tar.gz" \
        -mtime "+${KEEP_DAYS}" -delete -print 2>/dev/null | wc -l)
    [[ "$DELETED" -gt 0 ]] && echo "${LOG_PREFIX}: Удалено старых бэкапов: ${DELETED}"
fi

BACKUP_COUNT=$(find "${BACKUP_DIR}" -name "kaza_backup_2*.tar.gz" 2>/dev/null | wc -l)
BACKUP_TOTAL=$(du -sh "${BACKUP_DIR}" 2>/dev/null | cut -f1)
TIMESTAMP_DISPLAY=$(date '+%d.%m.%Y %H:%M')

echo "${LOG_PREFIX}: Итого бэкапов: ${BACKUP_COUNT} (${BACKUP_TOTAL})"

# ── Уведомление ───────────────────────────────────────────────────────────────
if [[ $HOURLY_MODE -eq 1 ]]; then
    # Почасовой бэкап: только локально, без Telegram
    echo "${LOG_PREFIX}: Почасовой бэкап завершён (Telegram не отправляется)"

elif [[ $EMERGENCY_MODE -eq 1 ]]; then
    # Аварийный бэкап: отправляем файл в Telegram
    CAPTION="🆘 <b>Аварийный бэкап Kaza Shop</b>
📅 ${TIMESTAMP_DISPLAY}
📦 Размер: ${TOTAL_SIZE}
🗄 БД: ${DB_SIZE}   📁 Медиа: ${MEDIA_SIZE}

Сервис упал — это последняя стабильная копия данных.
Для восстановления:
1. Установите сервис заново: <code>bash install.sh</code>
2. Поместите файл в <code>/opt/kaza_shop/backups/</code>
3. Выполните: <code>sudo bash /opt/kaza_shop/restore.sh</code>"
    send_telegram_document "$ARCHIVE" "$CAPTION"

else
    # Ежедневный бэкап: отправляем файл в Telegram
    CAPTION="💾 <b>Ежедневный бэкап Kaza Shop</b>
📅 ${TIMESTAMP_DISPLAY}
📦 Размер: ${TOTAL_SIZE}
🗄 БД: ${DB_SIZE}   📁 Медиа: ${MEDIA_SIZE}
Хранится ${KEEP_DAYS} дней (всего: ${BACKUP_COUNT})

Для восстановления на новом сервере:
1. Скачайте файл и поместите в <code>/opt/kaza_shop/backups/</code>
2. Выполните: <code>sudo bash /opt/kaza_shop/restore.sh</code>"
    send_telegram_document "$ARCHIVE" "$CAPTION"
fi

echo "${LOG_PREFIX}: Завершено успешно"
