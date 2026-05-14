#!/usr/bin/env bash
# ==============================================================================
#  Kaza Shop — Перенос DATA-сервера на другой сервер
#
#  Перемещает базу данных, Redis-снимок и медиафайлы с одного DATA-сервера
#  на другой без потери данных. После переноса обновляет конфигурацию
#  APP-сервера и перезапускает приложение.
#
#  Сценарии использования:
#    1. Перенос данных на новый российский сервер
#    2. Объединение двух серверов в один (split → single)
#    3. Перенос всего на один зарубежный сервер (например, для отладки)
#    4. Плановая миграция на сервер с большим объёмом диска/RAM
#
#  Использование:
#    bash scripts/migrate_data_server.sh
#
#  Требования на локальной машине:
#    ssh, scp (или sshpass для парольной аутентификации)
# ==============================================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

ok()    { echo -e "${GREEN}✓${NC} $*"; }
warn()  { echo -e "${YELLOW}⚠${NC}  $*"; }
err()   { echo -e "${RED}✗ Ошибка:${NC} $*" >&2; exit 1; }
info()  { echo -e "${BLUE}→${NC} $*"; }
step()  { echo -e "\n${BOLD}$*${NC}"; echo "────────────────────────────────────────"; }
ask()   { read -rp "  $1: " "$2"; }
askp()  { read -rsp "  $1: " "$2"; echo ""; }

clear
echo -e "${BOLD}${CYAN}"
cat << 'BANNER'
  ___  ___ ___ ___   __  __ ___ ___ ___    _ _____ ___
 |   \| _ \_  _  \ |  \/  |_ _/ __| _ \  /_\_   _| __|
 | |) |   / | || | | |\/| || | (_ |   / / _ \| | | _|
 |___/|_|_\___/_/ |_|  |_|___|\___|_|_\/_/ \_\_| |___|
BANNER
echo -e "${NC}"
echo -e "  ${BOLD}Перенос данных на новый DATA-сервер${NC}"
echo -e "  Kaza Shop · $(date '+%Y-%m-%d')\n"

# ==============================================================================
# 1. Параметры ИСТОЧНИКА (старый DATA-сервер или single-server)
# ==============================================================================
step "1/6  Источник (откуда переносим)"
echo ""
echo -e "  Это ${BOLD}старый${NC} DATA-сервер, с которого нужно перенести данные."
echo -e "  Если сейчас используется один сервер — укажите его."
echo ""
ask "IP старого DATA-сервера" SRC_IP
ask "SSH пользователь (Enter = root)" SRC_USER
SRC_USER="${SRC_USER:-root}"
ask "SSH порт (Enter = 22)" SRC_PORT
SRC_PORT="${SRC_PORT:-22}"

echo ""
echo -e "  ${YELLOW}Аутентификация на ИСТОЧНИКЕ:${NC}"
echo -e "  1) Пароль   2) SSH-ключ"
read -rp "  Выбор (1/2): " SRC_AUTH
SRC_AUTH="${SRC_AUTH:-1}"
SRC_PASS=""; SRC_KEY=""
if [[ "$SRC_AUTH" == "1" ]]; then
    askp "SSH-пароль для ${SRC_USER}@${SRC_IP}" SRC_PASS
else
    ask "Путь к SSH-ключу (Enter = ~/.ssh/id_rsa)" SRC_KEY
    SRC_KEY="${SRC_KEY:-${HOME}/.ssh/id_rsa}"
    [[ -f "$SRC_KEY" ]] || err "Файл ключа не найден: $SRC_KEY"
fi

echo ""
echo -e "  ${YELLOW}Путь к директории Kaza Shop на ИСТОЧНИКЕ:${NC}"
ask "Путь (Enter = /opt/kaza_shop)" SRC_DIR
SRC_DIR="${SRC_DIR:-/opt/kaza_shop}"

# ==============================================================================
# 2. Параметры НАЗНАЧЕНИЯ (новый DATA-сервер)
# ==============================================================================
step "2/6  Назначение (куда переносим)"
echo ""
echo -e "  Это ${BOLD}новый${NC} сервер, на который переносим данные."
echo ""
ask "IP нового DATA-сервера" DST_IP
ask "SSH пользователь (Enter = root)" DST_USER
DST_USER="${DST_USER:-root}"
ask "SSH порт (Enter = 22)" DST_PORT
DST_PORT="${DST_PORT:-22}"

echo ""
echo -e "  ${YELLOW}Аутентификация на НАЗНАЧЕНИИ:${NC}"
echo -e "  1) Пароль   2) SSH-ключ"
read -rp "  Выбор (1/2): " DST_AUTH
DST_AUTH="${DST_AUTH:-1}"
DST_PASS=""; DST_KEY=""
if [[ "$DST_AUTH" == "1" ]]; then
    askp "SSH-пароль для ${DST_USER}@${DST_IP}" DST_PASS
else
    ask "Путь к SSH-ключу (Enter = ~/.ssh/id_rsa)" DST_KEY
    DST_KEY="${DST_KEY:-${HOME}/.ssh/id_rsa}"
    [[ -f "$DST_KEY" ]] || err "Файл ключа не найден: $DST_KEY"
fi

ask "Путь для установки на НАЗНАЧЕНИИ (Enter = /opt/kaza_data)" DST_DIR
DST_DIR="${DST_DIR:-/opt/kaza_data}"

# ==============================================================================
# 3. Параметры APP-сервера (для обновления конфига после переноса)
# ==============================================================================
step "3/6  APP-сервер (для обновления конфигурации)"
echo ""
echo -e "  После переноса данных скрипт обновит .env на APP-сервере"
echo -e "  и перезапустит приложение. Если APP-сервер совпадает с ИСТОЧНИКОМ,"
echo -e "  введите тот же IP."
echo ""
ask "IP APP-сервера (Enter — не обновлять)" APP_IP
APP_IP="${APP_IP:-}"
APP_USER=""; APP_PORT=""; APP_PASS=""; APP_KEY=""; APP_DIR=""
if [[ -n "$APP_IP" ]]; then
    ask "SSH пользователь APP-сервера (Enter = root)" APP_USER
    APP_USER="${APP_USER:-root}"
    ask "SSH порт APP-сервера (Enter = 22)" APP_PORT
    APP_PORT="${APP_PORT:-22}"
    echo ""
    echo -e "  ${YELLOW}Аутентификация на APP-сервере:${NC}"
    echo -e "  1) Пароль   2) SSH-ключ"
    read -rp "  Выбор (1/2): " APP_AUTH
    APP_AUTH="${APP_AUTH:-1}"
    if [[ "$APP_AUTH" == "1" ]]; then
        askp "SSH-пароль для ${APP_USER}@${APP_IP}" APP_PASS
    else
        ask "Путь к SSH-ключу (Enter = ~/.ssh/id_rsa)" APP_KEY
        APP_KEY="${APP_KEY:-${HOME}/.ssh/id_rsa}"
    fi
    ask "Путь к Kaza Shop на APP-сервере (Enter = /opt/kaza_shop)" APP_DIR
    APP_DIR="${APP_DIR:-/opt/kaza_shop}"
fi

# ==============================================================================
# Подтверждение
# ==============================================================================
echo ""
echo -e "${BOLD}  Параметры переноса:${NC}"
echo -e "  Источник:    ${YELLOW}${SRC_USER}@${SRC_IP}:${SRC_PORT}${NC}  →  ${SRC_DIR}"
echo -e "  Назначение:  ${GREEN}${DST_USER}@${DST_IP}:${DST_PORT}${NC}  →  ${DST_DIR}"
[[ -n "$APP_IP" ]] && echo -e "  APP-сервер:  ${CYAN}${APP_USER}@${APP_IP}:${APP_PORT}${NC}  →  ${APP_DIR}"
echo ""
echo -e "  ${YELLOW}⚠  Данные на НАЗНАЧЕНИИ будут перезаписаны, если существуют.${NC}"
echo ""
read -rp "  Начать перенос? (y/N): " CONFIRM
[[ "$CONFIRM" =~ ^[Yy]$ ]] || { info "Отменено."; exit 0; }

LOG_FILE="/tmp/kaza_migrate_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOG_FILE") 2>&1

# ==============================================================================
# Вспомогательные функции SSH/SCP
# ==============================================================================
_ssh_opts() {
    local port="$1" key="$2"
    local opts=(-p "$port" -o StrictHostKeyChecking=no -o ConnectTimeout=15
                -o ServerAliveInterval=30 -o ServerAliveCountMax=60)
    [[ -n "$key" ]] && opts+=(-i "$key" -o BatchMode=yes)
    echo "${opts[@]}"
}

run_src()  {
    local opts; opts=($(_ssh_opts "$SRC_PORT" "$SRC_KEY"))
    if [[ "$SRC_AUTH" == "1" ]]; then
        SSHPASS="$SRC_PASS" sshpass -e ssh "${opts[@]}" "${SRC_USER}@${SRC_IP}" "$@"
    else
        ssh "${opts[@]}" "${SRC_USER}@${SRC_IP}" "$@"
    fi
}
run_dst()  {
    local opts; opts=($(_ssh_opts "$DST_PORT" "$DST_KEY"))
    if [[ "$DST_AUTH" == "1" ]]; then
        SSHPASS="$DST_PASS" sshpass -e ssh "${opts[@]}" "${DST_USER}@${DST_IP}" "$@"
    else
        ssh "${opts[@]}" "${DST_USER}@${DST_IP}" "$@"
    fi
}
run_app()  {
    [[ -z "$APP_IP" ]] && return 0
    local opts; opts=($(_ssh_opts "$APP_PORT" "$APP_KEY"))
    if [[ "$APP_AUTH" == "1" ]]; then
        SSHPASS="$APP_PASS" sshpass -e ssh "${opts[@]}" "${APP_USER}@${APP_IP}" "$@"
    else
        ssh "${opts[@]}" "${APP_USER}@${APP_IP}" "$@"
    fi
}
scp_to_dst() {
    local opts; opts=(-P "$DST_PORT" -o StrictHostKeyChecking=no)
    [[ -n "$DST_KEY" ]] && opts+=(-i "$DST_KEY")
    if [[ "$DST_AUTH" == "1" ]]; then
        SSHPASS="$DST_PASS" sshpass -e scp "${opts[@]}" "$@"
    else
        scp "${opts[@]}" "$@"
    fi
}

# Проверка sshpass
if [[ "$SRC_AUTH" == "1" ]] || [[ "$DST_AUTH" == "1" ]] || [[ "${APP_AUTH:-1}" == "1" ]]; then
    command -v sshpass &>/dev/null || err "Установите sshpass: brew install sshpass / apt-get install sshpass"
fi

# ==============================================================================
# 4. Создание дампа PostgreSQL на источнике
# ==============================================================================
step "4/6  Дамп базы данных"

# Читаем параметры БД с источника
DB_USER_SRC=$(run_src "grep '^DB_USER=' ${SRC_DIR}/.env | cut -d= -f2-" 2>/dev/null || echo "kaza_user")
DB_NAME_SRC=$(run_src "grep '^DB_NAME=' ${SRC_DIR}/.env | cut -d= -f2-" 2>/dev/null || echo "kaza_shop")
DB_PASS_SRC=$(run_src "grep '^DB_PASSWORD=' ${SRC_DIR}/.env | cut -d= -f2-" 2>/dev/null || echo "")
ok "Параметры БД получены: ${DB_USER_SRC}@${DB_NAME_SRC}"

DUMP_FILE="/tmp/kaza_db_$(date +%Y%m%d_%H%M%S).dump"
info "Создаём дамп на источнике (это может занять несколько минут)..."

# Определяем docker-compose файл на источнике
SRC_COMPOSE=$(run_src "
    if   [[ -f ${SRC_DIR}/docker-compose.data-only.yml ]]; then echo 'docker-compose.data-only.yml'
    elif [[ -f ${SRC_DIR}/docker-compose.prod.yml ]];      then echo 'docker-compose.prod.yml'
    else echo 'docker-compose.yml'; fi" 2>/dev/null || echo "docker-compose.prod.yml")
info "Файл compose на источнике: ${SRC_COMPOSE}"

run_src "
    cd ${SRC_DIR}
    PGPASSWORD='${DB_PASS_SRC}' docker compose -f ${SRC_COMPOSE} exec -T db \
        pg_dump -U '${DB_USER_SRC}' --format=custom --compress=9 '${DB_NAME_SRC}' \
        > /tmp/kaza_migrate.dump
"
ok "Дамп создан на источнике: /tmp/kaza_migrate.dump"

# Скачиваем дамп локально
TEMP_DIR=$(mktemp -d)
info "Скачиваем дамп..."
if [[ "$SRC_AUTH" == "1" ]]; then
    SSHPASS="$SRC_PASS" sshpass -e scp \
        -P "$SRC_PORT" -o StrictHostKeyChecking=no \
        "${SRC_USER}@${SRC_IP}:/tmp/kaza_migrate.dump" "${TEMP_DIR}/db.dump"
else
    scp -P "$SRC_PORT" -o StrictHostKeyChecking=no -i "$SRC_KEY" \
        "${SRC_USER}@${SRC_IP}:/tmp/kaza_migrate.dump" "${TEMP_DIR}/db.dump"
fi
DUMP_SIZE=$(du -sh "${TEMP_DIR}/db.dump" | cut -f1)
ok "Дамп скачан: ${DUMP_SIZE}"

# Удаляем временный файл на источнике
run_src "rm -f /tmp/kaza_migrate.dump" 2>/dev/null || true

# ==============================================================================
# 5. Перенос медиафайлов
# ==============================================================================
step "5/6  Медиафайлы"

MEDIA_SIZE=$(run_src "du -sh ${SRC_DIR}/media 2>/dev/null | cut -f1 || echo '0B'")
info "Размер медиафайлов на источнике: ${MEDIA_SIZE}"

if [[ "$MEDIA_SIZE" != "0B" ]] && [[ "$MEDIA_SIZE" != "0" ]]; then
    info "Создаём архив медиафайлов..."
    run_src "tar -czf /tmp/kaza_media.tar.gz -C ${SRC_DIR} media" 2>/dev/null || true
    MEDIA_ARCHIVE_SIZE=$(run_src "du -sh /tmp/kaza_media.tar.gz 2>/dev/null | cut -f1 || echo '0'")
    ok "Архив медиафайлов: ${MEDIA_ARCHIVE_SIZE}"

    info "Скачиваем медиафайлы..."
    if [[ "$SRC_AUTH" == "1" ]]; then
        SSHPASS="$SRC_PASS" sshpass -e scp \
            -P "$SRC_PORT" -o StrictHostKeyChecking=no \
            "${SRC_USER}@${SRC_IP}:/tmp/kaza_media.tar.gz" "${TEMP_DIR}/media.tar.gz" || true
    else
        scp -P "$SRC_PORT" -o StrictHostKeyChecking=no -i "$SRC_KEY" \
            "${SRC_USER}@${SRC_IP}:/tmp/kaza_media.tar.gz" "${TEMP_DIR}/media.tar.gz" || true
    fi
    [[ -f "${TEMP_DIR}/media.tar.gz" ]] && ok "Медиафайлы скачаны" || warn "Медиафайлы не скачаны (продолжаем)"
    run_src "rm -f /tmp/kaza_media.tar.gz" 2>/dev/null || true
else
    info "Медиафайлы отсутствуют — пропускаем"
fi

# Читаем .env с источника (понадобится для настройки назначения)
SRC_ENV_CONTENT=$(run_src "cat ${SRC_DIR}/.env" 2>/dev/null || echo "")
if [[ -z "$SRC_ENV_CONTENT" ]]; then
    warn "Не удалось прочитать .env с источника — часть параметров нужно задать вручную"
fi
echo "$SRC_ENV_CONTENT" > "${TEMP_DIR}/src.env"

# ==============================================================================
# 6. Восстановление на сервере назначения
# ==============================================================================
step "6/6  Восстановление на новом DATA-сервере"

# Убеждаемся, что Docker установлен на назначении
info "Проверяем Docker на новом сервере..."
run_dst "command -v docker &>/dev/null || { curl -fsSL https://get.docker.com | sh && systemctl enable --now docker; }"
run_dst "docker compose version &>/dev/null 2>&1 || apt-get install -y docker-compose-plugin"
ok "Docker готов"

# Копируем файлы на назначение
info "Копируем файлы конфигурации..."
run_dst "mkdir -p ${DST_DIR}/deploy/postgres"

# Загружаем .env (используем env с источника как основу)
scp_to_dst "${TEMP_DIR}/src.env" "${DST_USER}@${DST_IP}:${DST_DIR}/.env"

# Загружаем docker-compose.data-only.yml
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "${SCRIPT_DIR}/docker-compose.data-only.yml" ]]; then
    scp_to_dst "${SCRIPT_DIR}/docker-compose.data-only.yml" \
        "${DST_USER}@${DST_IP}:${DST_DIR}/docker-compose.data-only.yml"
    ok "docker-compose.data-only.yml загружен"
else
    warn "docker-compose.data-only.yml не найден локально — скопируйте вручную"
fi

# Загружаем pg_hba_remote.conf
if [[ -f "${SCRIPT_DIR}/deploy/postgres/pg_hba_remote.conf" ]]; then
    scp_to_dst "${SCRIPT_DIR}/deploy/postgres/pg_hba_remote.conf" \
        "${DST_USER}@${DST_IP}:${DST_DIR}/deploy/postgres/pg_hba_remote.conf"
fi

# Добавляем REDIS_PASSWORD в .env если его нет
run_dst "
    grep -q '^REDIS_PASSWORD=' ${DST_DIR}/.env 2>/dev/null \
    || echo 'REDIS_PASSWORD=${REDIS_PASSWORD:-$(openssl rand -hex 16)}' >> ${DST_DIR}/.env
"

# Запускаем контейнеры данных
info "Запускаем PostgreSQL и Redis на новом сервере..."
run_dst "
    cd ${DST_DIR}
    docker compose -f docker-compose.data-only.yml up -d
"
info "Ожидаем готовности PostgreSQL (до 60 сек)..."
run_dst "
    for i in \$(seq 1 12); do
        sleep 5
        if docker compose -f ${DST_DIR}/docker-compose.data-only.yml exec -T db \
                pg_isready -U \$(grep '^DB_USER=' ${DST_DIR}/.env | cut -d= -f2-) &>/dev/null; then
            echo 'PostgreSQL готов'
            break
        fi
        echo -n '.'
    done
"
ok "Контейнеры данных запущены"

# Загружаем дамп на назначение
info "Загружаем дамп на новый сервер..."
scp_to_dst "${TEMP_DIR}/db.dump" "${DST_USER}@${DST_IP}:/tmp/kaza_migrate.dump"
ok "Дамп загружен"

# Восстанавливаем БД
info "Восстанавливаем базу данных..."
DB_USER_DST=$(run_dst "grep '^DB_USER=' ${DST_DIR}/.env | cut -d= -f2-" 2>/dev/null || echo "kaza_user")
DB_NAME_DST=$(run_dst "grep '^DB_NAME=' ${DST_DIR}/.env | cut -d= -f2-" 2>/dev/null || echo "kaza_shop")
DB_PASS_DST=$(run_dst "grep '^DB_PASSWORD=' ${DST_DIR}/.env | cut -d= -f2-" 2>/dev/null || echo "")

run_dst "
    cd ${DST_DIR}
    # Пересоздаём БД чтобы получить чистое восстановление
    docker compose -f docker-compose.data-only.yml exec -T db \
        psql -U '${DB_USER_DST}' -c 'DROP DATABASE IF EXISTS \"${DB_NAME_DST}\";' postgres
    docker compose -f docker-compose.data-only.yml exec -T db \
        psql -U '${DB_USER_DST}' -c 'CREATE DATABASE \"${DB_NAME_DST}\" OWNER \"${DB_USER_DST}\";' postgres
    # Восстанавливаем
    PGPASSWORD='${DB_PASS_DST}' docker compose -f docker-compose.data-only.yml exec -T db \
        pg_restore -U '${DB_USER_DST}' -d '${DB_NAME_DST}' --no-owner --role='${DB_USER_DST}' \
        < /tmp/kaza_migrate.dump
    rm -f /tmp/kaza_migrate.dump
"
ok "База данных восстановлена"

# Восстанавливаем медиафайлы
if [[ -f "${TEMP_DIR}/media.tar.gz" ]]; then
    info "Восстанавливаем медиафайлы..."
    scp_to_dst "${TEMP_DIR}/media.tar.gz" "${DST_USER}@${DST_IP}:/tmp/kaza_media.tar.gz"
    run_dst "tar -xzf /tmp/kaza_media.tar.gz -C ${DST_DIR}/ && rm -f /tmp/kaza_media.tar.gz"
    ok "Медиафайлы восстановлены"
fi

# Настройка firewall на новом DATA-сервере
if [[ -n "$APP_IP" ]]; then
    info "Настраиваем firewall на DATA-сервере (разрешаем только APP-сервер)..."
    run_dst "
        if command -v ufw &>/dev/null; then
            ufw allow from ${APP_IP} to any port 5432 comment 'Kaza app → postgres'
            ufw allow from ${APP_IP} to any port 6379 comment 'Kaza app → redis'
            ufw --force enable >/dev/null 2>&1 || true
            echo 'UFW: порты 5432 и 6379 открыты только для ${APP_IP}'
        else
            echo 'ufw не найден — настройте firewall вручную'
        fi
    "
fi

# Обновляем APP-сервер (DATABASE_URL и REDIS_URL)
if [[ -n "$APP_IP" ]]; then
    info "Обновляем .env на APP-сервере..."
    REDIS_PASS_NEW=$(run_dst "grep '^REDIS_PASSWORD=' ${DST_DIR}/.env | cut -d= -f2-" 2>/dev/null || echo "")
    run_app "
        ENV_FILE=${APP_DIR}/.env
        [[ -f \"\$ENV_FILE\" ]] || { echo 'ERROR: .env не найден на APP-сервере'; exit 1; }
        # Обновляем DB_HOST
        sed -i 's|^DB_HOST=.*|DB_HOST=${DST_IP}|' \"\$ENV_FILE\"
        # Обновляем REDIS_URL
        sed -i 's|^REDIS_URL=.*|REDIS_URL=redis://:${REDIS_PASS_NEW}@${DST_IP}:6379/0|' \"\$ENV_FILE\"
        echo '.env обновлён'
        echo \"  DB_HOST=${DST_IP}\"
        echo \"  REDIS_URL=redis://:***@${DST_IP}:6379/0\"
    "
    ok "Конфигурация APP-сервера обновлена"

    # Перезапускаем приложение
    read -rp "  Перезапустить приложение на APP-сервере сейчас? (y/N): " RESTART_APP
    if [[ "$RESTART_APP" =~ ^[Yy]$ ]]; then
        info "Перезапускаем приложение..."
        # Определяем compose файл на app сервере
        APP_COMPOSE=$(run_app "
            if   [[ -f ${APP_DIR}/docker-compose.app-only.yml ]]; then echo 'docker-compose.app-only.yml'
            elif [[ -f ${APP_DIR}/docker-compose.prod.yml ]];      then echo 'docker-compose.prod.yml'
            else echo 'docker-compose.yml'; fi" 2>/dev/null || echo "docker-compose.prod.yml")
        run_app "cd ${APP_DIR} && docker compose -f ${APP_COMPOSE} restart app bot"
        ok "Приложение перезапущено"

        # Ждём /health
        info "Проверяем /health на APP-сервере..."
        run_app "
            for i in \$(seq 1 12); do
                sleep 5
                if curl -sf http://localhost:8000/health &>/dev/null; then
                    echo 'API отвечает'
                    break
                fi
                echo -n '.'
            done
        " || warn "API не ответил — проверьте логи: docker compose logs app"
    fi
fi

# Чистим временные файлы
rm -rf "$TEMP_DIR"

# ==============================================================================
# Итог
# ==============================================================================
echo ""
echo -e "${BOLD}${GREEN}════════════════════════════════════════${NC}"
echo -e "${BOLD}${GREEN}  ✓ Перенос данных завершён!${NC}"
echo -e "${BOLD}${GREEN}════════════════════════════════════════${NC}"
echo ""
echo -e "  ${BOLD}Новый DATA-сервер:${NC}  ${GREEN}${DST_IP}${NC}  →  ${DST_DIR}"
echo ""
echo -e "  ${BOLD}Что было перенесено:${NC}"
echo -e "  📦  База данных PostgreSQL"
[[ -n "${MEDIA_SIZE:-}" ]] && echo -e "  🖼   Медиафайлы (${MEDIA_SIZE})"
echo ""
if [[ -n "$APP_IP" ]]; then
    echo -e "  ${BOLD}APP-сервер обновлён:${NC}  ${CYAN}${APP_IP}${NC}"
    echo -e "  DATABASE_URL → ${DST_IP}:5432"
    echo -e "  REDIS_URL    → ${DST_IP}:6379"
else
    echo -e "  ${YELLOW}⚠  Обновите .env на APP-сервере вручную:${NC}"
    echo -e "     DB_HOST=${DST_IP}"
    REDIS_P=$(run_dst "grep '^REDIS_PASSWORD=' ${DST_DIR}/.env | cut -d= -f2-" 2>/dev/null || echo "<redis_password>")
    echo -e "     REDIS_URL=redis://:${REDIS_P}@${DST_IP}:6379/0"
fi
echo ""
echo -e "  ${BOLD}Управление DATA-сервером:${NC}"
echo -e "  Статус:   ssh ${DST_USER}@${DST_IP} 'docker compose -f ${DST_DIR}/docker-compose.data-only.yml ps'"
echo -e "  Логи PG:  ssh ${DST_USER}@${DST_IP} 'docker compose -f ${DST_DIR}/docker-compose.data-only.yml logs db'"
echo ""
echo -e "  Лог: ${LOG_FILE}"
echo ""
