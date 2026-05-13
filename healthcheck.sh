#!/usr/bin/env bash
# Kaza Shop — Мониторинг сервисов (запускается cron каждые 5 минут)
set -euo pipefail

INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${INSTALL_DIR}/.env" 2>/dev/null || true

STATE_DIR="${INSTALL_DIR}/data/.monitor"
mkdir -p "$STATE_DIR"

LOG_PREFIX="[$(date '+%Y-%m-%d %H:%M:%S')] MONITOR"
DOMAIN="${DOMAIN:-localhost}"
ALERT_BOT_TOKEN="${ALERT_BOT_TOKEN:-${BOT_TOKEN:-}}"
ALERT_CHAT_ID="${ALERT_CHAT_ID:-${ADMIN_TG_ID:-}}"
COMPOSE_FILE="${INSTALL_DIR}/docker-compose.prod.yml"

# ── Отправка текстового сообщения ─────────────────────────────────────────────
send_alert() {
    local text="$1"
    [[ -z "$ALERT_BOT_TOKEN" || -z "$ALERT_CHAT_ID" ]] && return 0
    curl -sf "https://api.telegram.org/bot${ALERT_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${ALERT_CHAT_ID}" \
        -d "parse_mode=HTML" \
        --data-urlencode "text=${text}" >/dev/null 2>&1 || true
}

# ── Отправка файла бэкапа ─────────────────────────────────────────────────────
send_backup_document() {
    local file_path="$1"
    local caption="${2:-}"
    [[ -z "$ALERT_BOT_TOKEN" || -z "$ALERT_CHAT_ID" ]] && return 0
    [[ ! -f "$file_path" ]] && return 0

    local file_size
    file_size=$(stat -c%s "$file_path" 2>/dev/null || stat -f%z "$file_path" 2>/dev/null || echo 0)
    if [[ "$file_size" -gt 47185920 ]]; then
        send_alert "⚠️ Бэкап есть, но слишком велик для отправки ($(du -sh "$file_path" | cut -f1)).
Скачайте по SFTP: <code>${file_path}</code>"
        return 0
    fi

    if [[ -n "$caption" ]]; then
        curl -sf "https://api.telegram.org/bot${ALERT_BOT_TOKEN}/sendDocument" \
            -F "chat_id=${ALERT_CHAT_ID}" \
            -F "parse_mode=HTML" \
            -F "caption=${caption}" \
            -F "document=@${file_path}" >/dev/null 2>&1 \
        || send_alert "⚠️ Бэкап создан, но отправить файл не удалось. Скачайте по SFTP: <code>${file_path}</code>" || true
    else
        curl -sf "https://api.telegram.org/bot${ALERT_BOT_TOKEN}/sendDocument" \
            -F "chat_id=${ALERT_CHAT_ID}" \
            -F "document=@${file_path}" >/dev/null 2>&1 || true
    fi
}

# ── Антифлуд: не слать одно и то же чаще раза в час ──────────────────────────
should_alert() {
    local key="$1"
    local cooldown="${2:-3600}"
    local state_file="${STATE_DIR}/${key}.last_alert"
    local now
    now=$(date +%s)
    if [[ -f "$state_file" ]]; then
        local last
        last=$(cat "$state_file")
        (( now - last < cooldown )) && return 1
    fi
    echo "$now" > "$state_file"
    return 0
}

mark_recovered() {
    local key="$1"
    local state_file="${STATE_DIR}/${key}.down"
    if [[ -f "$state_file" ]]; then
        rm -f "$state_file"
        return 0   # только что восстановился
    fi
    return 1
}

mark_down() {
    local key="$1"
    touch "${STATE_DIR}/${key}.down"
}

is_down() {
    local key="$1"
    [[ -f "${STATE_DIR}/${key}.down" ]]
}

# ── Аварийный бэкап + отправка при первом обнаружении падения ────────────────
# Вызывается однократно при первом обнаружении (not is_down → mark_down).
# Пытается создать свежий бэкап; если не получается — отправляет последний стабильный.
send_emergency_backup() {
    local reason="$1"
    local backup_sent_file="${STATE_DIR}/emergency_backup.sent"

    # Отправляем только ОДИН РАЗ за каждый инцидент падения
    [[ -f "$backup_sent_file" ]] && return 0
    touch "$backup_sent_file"

    local TIMESTAMP_DISPLAY
    TIMESTAMP_DISPLAY=$(date '+%d.%m.%Y %H:%M')
    local BACKUP_ARCHIVE=""

    echo "${LOG_PREFIX}: Аварийное падение обнаружено — пытаемся создать аварийный бэкап..."

    # Пробуем создать свежий бэкап (тихо)
    if bash "${INSTALL_DIR}/backup.sh" --emergency --silent 2>/dev/null; then
        # Находим только что созданный emergency-бэкап
        BACKUP_ARCHIVE=$(find "${INSTALL_DIR}/backups" -name "kaza_backup_emergency_*.tar.gz" \
            -newer "${backup_sent_file}" 2>/dev/null | sort -r | head -1 || echo "")
    fi

    # Фолбэк: используем последний стабильный бэкап
    if [[ -z "$BACKUP_ARCHIVE" ]]; then
        local stable="${INSTALL_DIR}/backups/kaza_backup_last_stable.tar.gz"
        if [[ -f "$stable" ]]; then
            BACKUP_ARCHIVE=$(readlink -f "$stable" 2>/dev/null || echo "$stable")
        fi
    fi

    local size_info="нет данных"
    [[ -f "$BACKUP_ARCHIVE" ]] && size_info=$(du -sh "$BACKUP_ARCHIVE" 2>/dev/null | cut -f1 || echo "?")

    local caption
    caption="🆘 <b>СЕРВИС УПАЛ — Аварийный бэкап</b>
📅 ${TIMESTAMP_DISPLAY}
⚠️ Причина: ${reason}
📦 Размер: ${size_info}

Это последняя стабильная копия данных.

<b>Для восстановления:</b>
1. Установите сервис: <code>bash install.sh</code>
2. Поместите этот файл в <code>/opt/kaza_shop/backups/</code>
3. Восстановите: <code>sudo bash /opt/kaza_shop/restore.sh</code>"

    if [[ -f "$BACKUP_ARCHIVE" ]]; then
        send_backup_document "$BACKUP_ARCHIVE" "$caption"
        echo "${LOG_PREFIX}: Аварийный бэкап отправлен в Telegram: ${BACKUP_ARCHIVE##*/}"
    else
        send_alert "🆘 <b>СЕРВИС УПАЛ</b>
📅 ${TIMESTAMP_DISPLAY}
⚠️ Причина: ${reason}

Создать бэкап не удалось (возможно, БД тоже недоступна).
Проверьте состояние сервера вручную."
        echo "${LOG_PREFIX}: Бэкап не удалось создать или найти"
    fi
}

ISSUES=0

# ── Проверка 1: API healthcheck ───────────────────────────────────────────────
echo "${LOG_PREFIX}: Проверка API..."
API_STATUS=$(curl -sf -o /dev/null -w "%{http_code}" \
    --max-time 10 "http://localhost:8000/health" 2>/dev/null || echo "000")

if [[ "$API_STATUS" == "200" ]]; then
    echo "${LOG_PREFIX}: API OK"
    if mark_recovered "api"; then
        # Удаляем флаг "аварийный бэкап отправлен" — инцидент завершён
        rm -f "${STATE_DIR}/emergency_backup.sent" 2>/dev/null || true
        send_alert "✅ <b>Магазин восстановлен</b>
API снова отвечает нормально.
📅 $(date '+%d.%m.%Y %H:%M')"
    fi
else
    echo "${LOG_PREFIX}: ПРОБЛЕМА — API вернул ${API_STATUS}"
    ISSUES=$((ISSUES + 1))

    # Первое обнаружение падения — отправляем аварийный бэкап
    if ! is_down "api"; then
        send_emergency_backup "API вернул HTTP ${API_STATUS}"
    fi

    mark_down "api"

    if should_alert "api_down"; then
        send_alert "🔴 <b>Магазин не отвечает!</b>
API статус: ${API_STATUS}
📅 $(date '+%d.%m.%Y %H:%M')

Попытка автоматического перезапуска..."

        # Попытка автовосстановления
        cd "$INSTALL_DIR"
        docker compose -f "$COMPOSE_FILE" restart app 2>/dev/null || true
        sleep 15
        RETRY=$(curl -sf -o /dev/null -w "%{http_code}" \
            --max-time 10 "http://localhost:8000/health" 2>/dev/null || echo "000")
        if [[ "$RETRY" == "200" ]]; then
            send_alert "✅ <b>Автовосстановление успешно</b>
API работает после перезапуска.
📅 $(date '+%d.%m.%Y %H:%M')"
            mark_recovered "api" >/dev/null 2>&1 || true
            rm -f "${STATE_DIR}/emergency_backup.sent" 2>/dev/null || true
        else
            send_alert "🆘 <b>Автовосстановление не помогло</b>
Требуется ручное вмешательство.

Диагностика (по SSH):
<code>cd /opt/kaza_shop &amp;&amp; docker compose -f docker-compose.prod.yml logs app --tail=50</code>"
        fi
    fi
fi

# ── Проверка 2: контейнеры Docker ────────────────────────────────────────────
echo "${LOG_PREFIX}: Проверка контейнеров..."
cd "$INSTALL_DIR"
STOPPED=$(docker compose -f "$COMPOSE_FILE" ps --status exited \
    --format json 2>/dev/null | grep -c '"Name"' || true)
STOPPED=${STOPPED//[^0-9]/}
STOPPED="${STOPPED:-0}"

if [[ "$STOPPED" -gt 0 ]]; then
    echo "${LOG_PREFIX}: ПРОБЛЕМА — упавших контейнеров: ${STOPPED}"
    mark_down "containers"
    ISSUES=$((ISSUES + 1))
    if should_alert "containers_down"; then
        NAMES=$(docker compose -f "$COMPOSE_FILE" ps --status exited \
            --format "{{.Name}}" 2>/dev/null | tr '\n' ', ' || echo "?")
        send_alert "⚠️ <b>Упавшие контейнеры: ${STOPPED}</b>
Контейнеры: ${NAMES}
📅 $(date '+%d.%m.%Y %H:%M')

Перезапуск..."
        docker compose -f "$COMPOSE_FILE" up -d 2>/dev/null || true
    fi
else
    echo "${LOG_PREFIX}: Все контейнеры работают"
    mark_recovered "containers" >/dev/null 2>&1 || true
fi

# ── Проверка 3: диск ──────────────────────────────────────────────────────────
echo "${LOG_PREFIX}: Проверка диска..."
DISK_USED=$(df -h / | awk 'NR==2{gsub("%",""); print $5}')
if [[ "$DISK_USED" -ge 90 ]]; then
    echo "${LOG_PREFIX}: ПРОБЛЕМА — диск заполнен на ${DISK_USED}%"
    ISSUES=$((ISSUES + 1))
    if should_alert "disk_full"; then
        DISK_INFO=$(df -h / | awk 'NR==2{print $3"/"$2}')
        send_alert "💾 <b>Диск почти полон: ${DISK_USED}%</b>
Использовано: ${DISK_INFO}

Почистите старые логи или бэкапы:
<code>ls -lh /opt/kaza_shop/backups/</code>
<code>ls -lh /opt/kaza_shop/logs/</code>"
    fi
elif [[ "$DISK_USED" -ge 80 ]]; then
    echo "${LOG_PREFIX}: ПРЕДУПРЕЖДЕНИЕ — диск на ${DISK_USED}%"
    if should_alert "disk_warn"; then
        send_alert "💾 <b>Внимание: диск заполнен на ${DISK_USED}%</b>
Рекомендуется проверить и освободить место."
    fi
else
    echo "${LOG_PREFIX}: Диск OK (${DISK_USED}%)"
fi

# ── Проверка 4: SSL-сертификат ────────────────────────────────────────────────
echo "${LOG_PREFIX}: Проверка SSL..."
CERT_FILE="/etc/letsencrypt/live/${DOMAIN}/cert.pem"
if [[ -f "$CERT_FILE" ]]; then
    EXPIRY=$(openssl x509 -enddate -noout -in "$CERT_FILE" 2>/dev/null \
        | cut -d= -f2 || echo "")
    if [[ -n "$EXPIRY" ]]; then
        EXPIRY_EPOCH=$(date -d "$EXPIRY" +%s 2>/dev/null \
            || date -j -f "%b %d %T %Y %Z" "$EXPIRY" +%s 2>/dev/null || echo 0)
        NOW_EPOCH=$(date +%s)
        DAYS_LEFT=$(( (EXPIRY_EPOCH - NOW_EPOCH) / 86400 ))
        echo "${LOG_PREFIX}: SSL истекает через ${DAYS_LEFT} дней"
        if [[ "$DAYS_LEFT" -le 14 && "$DAYS_LEFT" -gt 0 ]]; then
            if should_alert "ssl_expiry"; then
                send_alert "🔒 <b>SSL-сертификат истекает через ${DAYS_LEFT} дней</b>
Обновление должно происходить автоматически.
Если нет: <code>certbot renew</code>"
            fi
        fi
    fi
fi

# ── Проверка 5: RAM ───────────────────────────────────────────────────────────
echo "${LOG_PREFIX}: Проверка памяти..."
RAM_FREE_MB=$(free -m | awk '/^Mem:/{print $7}')
if [[ "$RAM_FREE_MB" -lt 100 ]]; then
    echo "${LOG_PREFIX}: ПРЕДУПРЕЖДЕНИЕ — свободной RAM: ${RAM_FREE_MB} MB"
    if should_alert "ram_low"; then
        send_alert "🧠 <b>Мало свободной памяти: ${RAM_FREE_MB} MB</b>
Если проблема повторяется — рассмотрите увеличение RAM на VDS."
    fi
else
    echo "${LOG_PREFIX}: RAM OK (свободно: ${RAM_FREE_MB} MB)"
fi

echo "${LOG_PREFIX}: Проверка завершена. Проблем: ${ISSUES}"
exit 0
