#!/usr/bin/env bash
# ==============================================================================
#  Kaza Shop — Деплой обновлений с локальной машины на сервер
#
#  Использование:
#    bash deploy.sh                           — интерактивный режим
#    bash deploy.sh --ip 1.2.3.4 --pass PASS  — с параметрами командной строки
#
#  Что делает:
#    1. Создаёт архив текущего кода (без данных и медиа)
#    2. Загружает на сервер
#    3. На сервере: создаёт бэкап данных и отправляет его в Telegram
#    4. Останавливает app/bot, заменяет код, пересобирает образы
#    5. Запускает, проверяет. При ошибке — откатывает
#
#  Данные (БД, медиа, настройки) НЕ затрагиваются.
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Цвета ─────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓${NC} $*"; }
warn() { echo -e "${YELLOW}⚠${NC}  $*"; }
err()  { echo -e "${RED}✗ Ошибка:${NC} $*" >&2; exit 1; }
info() { echo -e "${BLUE}→${NC} $*"; }
step() { echo -e "\n${BOLD}$*${NC}"; echo "────────────────────────────────────────"; }

# ── Разбор аргументов ─────────────────────────────────────────────────────────
SERVER_IP=""
SSH_USER="root"
SSH_PORT="22"
SSH_PASS=""
SSH_KEY=""
AUTH_METHOD="password"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --ip)     SERVER_IP="$2"; shift 2 ;;
        --port)   SSH_PORT="$2"; shift 2 ;;
        --user)   SSH_USER="$2"; shift 2 ;;
        --pass)   SSH_PASS="$2"; AUTH_METHOD="password"; shift 2 ;;
        --key)    SSH_KEY="$2"; AUTH_METHOD="key"; shift 2 ;;
        *) warn "Неизвестный аргумент: $1"; shift ;;
    esac
done

# ── Баннер ────────────────────────────────────────────────────────────────────
clear
echo -e "${BOLD}${CYAN}"
cat << 'BANNER'
  _  __                  ____  _
 | |/ /__ _ ______ _   / ___|| |__   ___  _ __
 | ' // _` |_  / _` |  \___ \| '_ \ / _ \| '_ \
 | . \ (_| |/ / (_| |   ___) | | | | (_) | |_) |
 |_|\_\__,_/___\__,_|  |____/|_| |_|\___/| .__/
                                          |_|
BANNER
echo -e "${NC}"
echo -e "  ${BOLD}Деплой обновлений на сервер${NC}"
echo ""

# ── Утилиты SSH ───────────────────────────────────────────────────────────────
_timeout_cmd() {
    if command -v timeout &>/dev/null; then timeout "$@"
    elif command -v gtimeout &>/dev/null; then gtimeout "$@"
    else shift; "$@"; fi
}

build_ssh_opts() {
    SSH_OPTS=(
        -p "$SSH_PORT"
        -o StrictHostKeyChecking=no
        -o ConnectTimeout=10
        -o ServerAliveInterval=30
        -o ServerAliveCountMax=60
        -o NumberOfPasswordPrompts=1
    )
    SCP_OPTS=(-P "$SSH_PORT" -o StrictHostKeyChecking=no -o ConnectTimeout=10)
    if [[ "$AUTH_METHOD" == "key" ]]; then
        SSH_OPTS+=(-i "$SSH_KEY" -o BatchMode=yes)
        SCP_OPTS+=(-i "$SSH_KEY")
    fi
}

run_ssh() {
    if [[ "$AUTH_METHOD" == "password" ]]; then
        SSHPASS="$SSH_PASS" _timeout_cmd 30 sshpass -e ssh "${SSH_OPTS[@]}" "${SSH_USER}@${SERVER_IP}" "$@"
    else
        _timeout_cmd 30 ssh "${SSH_OPTS[@]}" "${SSH_USER}@${SERVER_IP}" "$@"
    fi
}

run_ssh_long() {
    if [[ "$AUTH_METHOD" == "password" ]]; then
        SSHPASS="$SSH_PASS" sshpass -e ssh "${SSH_OPTS[@]}" "${SSH_USER}@${SERVER_IP}" "$@"
    else
        ssh "${SSH_OPTS[@]}" "${SSH_USER}@${SERVER_IP}" "$@"
    fi
}

run_scp() {
    if [[ "$AUTH_METHOD" == "password" ]]; then
        SSHPASS="$SSH_PASS" sshpass -e scp "${SCP_OPTS[@]}" "$@"
    else
        scp "${SCP_OPTS[@]}" "$@"
    fi
}

# ── Шаг 1: Данные сервера ─────────────────────────────────────────────────────
step "Шаг 1/5: Данные сервера"

if [[ -z "$SERVER_IP" ]]; then
    read -rp "  IP-адрес сервера: " SERVER_IP
    SERVER_IP="${SERVER_IP// /}"
fi
[[ -z "$SERVER_IP" ]] && err "IP сервера не указан"

if [[ -z "$SSH_PASS" && "$AUTH_METHOD" == "password" ]]; then
    echo ""
    echo -e "  ${YELLOW}Способ подключения:${NC}"
    echo -e "  ${BOLD}1)${NC} Пароль"
    echo -e "  ${BOLD}2)${NC} SSH-ключ (файл)"
    echo ""
    read -rp "  Выбор (1/2): " AUTH_CHOICE
    case "$AUTH_CHOICE" in
        1)
            AUTH_METHOD="password"
            if ! command -v sshpass &>/dev/null; then
                warn "sshpass не установлен."
                if command -v brew &>/dev/null; then
                    info "Устанавливаем через Homebrew..."
                    brew install hudochenkov/sshpass/sshpass 2>/dev/null \
                        || brew install sshpass 2>/dev/null \
                        || err "Установите sshpass или используйте SSH-ключ."
                else
                    err "Установите sshpass или используйте SSH-ключ."
                fi
            fi
            read -rsp "  SSH-пароль для ${SSH_USER}@${SERVER_IP}: " SSH_PASS; echo ""
            ;;
        2)
            AUTH_METHOD="key"
            read -rp "  Путь к ключу (Enter = ~/.ssh/id_rsa): " SSH_KEY
            SSH_KEY="${SSH_KEY:-${HOME}/.ssh/id_rsa}"
            [[ -f "$SSH_KEY" ]] || err "Файл ключа не найден: $SSH_KEY"
            ;;
        *) err "Неверный выбор" ;;
    esac
fi

build_ssh_opts

# Проверяем соединение
info "Проверяем подключение..."
set +e
SSH_TEST=$(run_ssh "echo ok" 2>&1); SSH_RC=$?
set -e

if [[ $SSH_RC -ne 0 ]]; then
    if echo "$SSH_TEST" | grep -qi "Host key verification\|REMOTE HOST IDENTIFICATION"; then
        warn "Ключ сервера изменился. Удаляем старый..."
        ssh-keygen -R "${SERVER_IP}" -f "${HOME}/.ssh/known_hosts" >/dev/null 2>&1 || true
        [[ "$SSH_PORT" != "22" ]] && ssh-keygen -R "[${SERVER_IP}]:${SSH_PORT}" -f "${HOME}/.ssh/known_hosts" >/dev/null 2>&1 || true
        set +e; SSH_TEST=$(run_ssh "echo ok" 2>&1); SSH_RC=$?; set -e
    fi
fi
[[ $SSH_RC -ne 0 ]] && err "Нет подключения к серверу.\n${SSH_TEST}"
ok "Подключение установлено"

# ── Шаг 2: Подтверждение ─────────────────────────────────────────────────────
step "Шаг 2/5: Подтверждение"
echo ""
echo -e "  Сервер:  ${GREEN}${SSH_USER}@${SERVER_IP}:${SSH_PORT}${NC}"
echo -e "  Папка:   ${GREEN}/opt/kaza_shop${NC}"
echo -e "  Данные:  ${CYAN}сохранятся (БД, медиа, настройки НЕ затрагиваются)${NC}"
echo ""
warn "Перед деплоем будет создан бэкап данных и отправлен в Telegram."
echo ""
read -rp "  Начать деплой? (y/N): " CONFIRM
[[ "$CONFIRM" =~ ^[Yy]$ ]] || { info "Отменено."; exit 0; }

# ── Шаг 3: Подготовка архива ─────────────────────────────────────────────────
step "Шаг 3/5: Подготовка архива"

ARCHIVE_DIR_NAME="$(basename "$SCRIPT_DIR")"
TEMP_DIR=$(mktemp -d)
TEMP_ARCHIVE="${TEMP_DIR}/kaza_deploy.tar.gz"
trap 'rm -rf "$TEMP_DIR"' EXIT
COPYFILE_DISABLE=1 tar \
    --exclude='._*' \
    --exclude='.DS_Store' \
    --exclude='.env' \
    --exclude='.env.example' \
    --exclude='media' \
    --exclude='data' \
    --exclude='logs' \
    --exclude='backups' \
    --exclude='*.pyc' \
    --exclude='__pycache__' \
    --exclude='.git' \
    --exclude='node_modules' \
    --exclude='*.tar.gz' \
    -czf "$TEMP_ARCHIVE" \
    -C "$(dirname "$SCRIPT_DIR")" "$ARCHIVE_DIR_NAME" 2>/dev/null
ARCHIVE_SIZE=$(du -sh "$TEMP_ARCHIVE" | cut -f1)
ok "Архив кода: ${ARCHIVE_SIZE}"

# ── Шаг 4: Загрузка на сервер ─────────────────────────────────────────────────
step "Шаг 4/5: Загрузка файлов на сервер"
info "Загружаем архив кода..."
run_scp "$TEMP_ARCHIVE" "${SSH_USER}@${SERVER_IP}:/tmp/kaza_deploy_update.tar.gz"
ok "Архив загружен"

# ── Шаг 5: Деплой на сервере ──────────────────────────────────────────────────
step "Шаг 5/5: Деплой на сервере"
echo ""

DEPLOY_SCRIPT="${TEMP_DIR}/deploy_remote.sh"
cat > "$DEPLOY_SCRIPT" << HEREDOC
#!/bin/bash
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'
ok()   { echo -e "\${GREEN}✓\${NC} \$*"; }
warn() { echo -e "\${YELLOW}⚠\${NC}  \$*"; }
info() { echo -e "\${BLUE}→\${NC} \$*"; }
err()  { echo -e "\${RED}✗ Ошибка:\${NC} \$*"; exit 1; }

INSTALL_DIR="/opt/kaza_shop"
ARCHIVE_NAME="${ARCHIVE_DIR_NAME}"
COMPOSE_FILE="\${INSTALL_DIR}/docker-compose.prod.yml"

[[ -d "\$INSTALL_DIR" ]] || err "\$INSTALL_DIR не найден. Сначала запустите install.sh"

echo ""
echo -e "\${BOLD}═══ Kaza Shop: деплой обновлений ═══\${NC}"
echo ""

# 1. Бэкап данных перед деплоем
info "Создаём бэкап данных перед обновлением..."
if bash "\${INSTALL_DIR}/backup.sh" --silent 2>/dev/null; then
    ok "Бэкап создан"
    # Находим только что созданный бэкап
    LATEST_BACKUP=\$(find "\${INSTALL_DIR}/backups" -name "kaza_backup_2*.tar.gz" | sort -r | head -1 || echo "")
    if [[ -n "\$LATEST_BACKUP" ]]; then
        source "\${INSTALL_DIR}/.env" 2>/dev/null || true
        ALERT_BOT_TOKEN="\${ALERT_BOT_TOKEN:-\${BOT_TOKEN:-}}"
        ALERT_CHAT_ID="\${ALERT_CHAT_ID:-\${ADMIN_TG_ID:-}}"
        BACKUP_SIZE=\$(du -sh "\$LATEST_BACKUP" 2>/dev/null | cut -f1 || echo "?")
        TIMESTAMP_DISPLAY=\$(date '+%d.%m.%Y %H:%M')
        if [[ -n "\$ALERT_BOT_TOKEN" && -n "\$ALERT_CHAT_ID" ]]; then
            FILE_SIZE=\$(stat -c%s "\$LATEST_BACKUP" 2>/dev/null || stat -f%z "\$LATEST_BACKUP" 2>/dev/null || echo 0)
            CAPTION="📦 <b>Бэкап перед обновлением Kaza Shop</b>
📅 \${TIMESTAMP_DISPLAY}
📦 Размер: \${BACKUP_SIZE}

Это резервная копия данных ПЕРЕД установкой обновления.
Если обновление пройдёт с ошибкой, используйте её для восстановления."
            if [[ "\$FILE_SIZE" -le 47185920 ]]; then
                curl -sf "https://api.telegram.org/bot\${ALERT_BOT_TOKEN}/sendDocument" \\
                    -F "chat_id=\${ALERT_CHAT_ID}" \\
                    -F "parse_mode=HTML" \\
                    -F "caption=\${CAPTION}" \\
                    -F "document=@\${LATEST_BACKUP}" >/dev/null 2>&1 && ok "Бэкап отправлен в Telegram" || warn "Не удалось отправить бэкап в Telegram"
            else
                curl -sf "https://api.telegram.org/bot\${ALERT_BOT_TOKEN}/sendMessage" \\
                    -d "chat_id=\${ALERT_CHAT_ID}" -d "parse_mode=HTML" \\
                    --data-urlencode "text=📦 <b>Бэкап перед обновлением создан (слишком велик для Telegram)</b>
Размер: \${BACKUP_SIZE}
Файл: \${LATEST_BACKUP}" >/dev/null 2>&1 || true
            fi
        fi
    fi
else
    warn "Бэкап не удался (продолжаем деплой)"
fi

# 2. Снимок кода для отката
TS="\$(date +%Y%m%d_%H%M%S)"
CODE_BACKUP="/tmp/kaza_code_bak_\${TS}.tar.gz"
cd "\$INSTALL_DIR"
tar -czf "\$CODE_BACKUP" \\
    --exclude './media' --exclude './data' --exclude './logs' \\
    --exclude './backups' --exclude './.git' --exclude './.venv' .
ok "Снимок кода для отката: \$CODE_BACKUP"
OLD_IMAGE="\$(docker compose -f "\$COMPOSE_FILE" images -q app 2>/dev/null | head -1 || echo "")"
[[ -n "\$OLD_IMAGE" ]] && docker tag "\$OLD_IMAGE" kaza_rollback:pre-deploy >/dev/null 2>&1 || true

# 3. Остановка app и bot
info "Останавливаем app и bot..."
docker compose -f "\$COMPOSE_FILE" stop app bot 2>/dev/null || true
sleep 2

# 4. Распаковка нового кода (данные не трогаем)
info "Применяем обновление кода..."
TMP_EXTRACT=\$(mktemp -d)
tar -xzf /tmp/kaza_deploy_update.tar.gz -C "\$TMP_EXTRACT"
SRC_DIR=\$(find "\$TMP_EXTRACT" -mindepth 1 -maxdepth 1 -type d | head -1)
[[ -z "\$SRC_DIR" ]] && SRC_DIR="\$TMP_EXTRACT"

rsync -a --delete \\
    --exclude '.env' \\
    --exclude 'media/' \\
    --exclude 'data/' \\
    --exclude 'logs/' \\
    --exclude 'backups/' \\
    --exclude '.git/' \\
    --exclude '.venv/' \\
    "\${SRC_DIR}/" "\${INSTALL_DIR}/"

rm -rf "\$TMP_EXTRACT" /tmp/kaza_deploy_update.tar.gz
chmod 755 "\${INSTALL_DIR}/backup.sh" "\${INSTALL_DIR}/healthcheck.sh" \\
           "\${INSTALL_DIR}/update.sh" "\${INSTALL_DIR}/restore.sh" \\
           "\${INSTALL_DIR}/deploy.sh" 2>/dev/null || true
ok "Код обновлён"

# 5. Сборка образов
info "Пересобираем Docker-образы..."
cd "\$INSTALL_DIR"
if docker compose -f "\$COMPOSE_FILE" build --no-cache 2>&1; then
    ok "Образы пересобраны"
else
    warn "Ошибка сборки — откатываем..."
    tar -xzf "\$CODE_BACKUP" -C "\$INSTALL_DIR"
    docker compose -f "\$COMPOSE_FILE" up -d || true
    rm -f "\$CODE_BACKUP"
    err "Деплой отменён, предыдущая версия восстановлена"
fi

# 6. Запуск
info "Запускаем сервисы..."
docker compose -f "\$COMPOSE_FILE" up -d --remove-orphans

# 7. Health check
info "Проверяем работоспособность..."
sleep 10
DEPLOY_OK=0
for i in \$(seq 1 6); do
    HTTP=\$(curl -sf -o /dev/null -w "%{http_code}" --max-time 10 "http://localhost:8000/health" 2>/dev/null || echo "000")
    if [[ "\$HTTP" == "200" ]]; then
        DEPLOY_OK=1; break
    fi
    warn "Попытка \${i}/6: HTTP \${HTTP}, ждём 10 сек..."
    sleep 10
done

if [[ \$DEPLOY_OK -eq 1 ]]; then
    echo ""
    echo -e "\${BOLD}\${GREEN}════════════════════════════════════════\${NC}"
    echo -e "\${BOLD}\${GREEN}  ✓ Деплой завершён успешно!\${NC}"
    echo -e "\${BOLD}\${GREEN}════════════════════════════════════════\${NC}"
    echo ""
    ok "Сервис работает"
    rm -f "\$CODE_BACKUP"
    # Уведомление об успешном деплое
    source "\${INSTALL_DIR}/.env" 2>/dev/null || true
    ALERT_BOT_TOKEN="\${ALERT_BOT_TOKEN:-\${BOT_TOKEN:-}}"
    ALERT_CHAT_ID="\${ALERT_CHAT_ID:-\${ADMIN_TG_ID:-}}"
    if [[ -n "\$ALERT_BOT_TOKEN" && -n "\$ALERT_CHAT_ID" ]]; then
        curl -sf "https://api.telegram.org/bot\${ALERT_BOT_TOKEN}/sendMessage" \\
            -d "chat_id=\${ALERT_CHAT_ID}" -d "parse_mode=HTML" \\
            --data-urlencode "text=✅ <b>Обновление Kaza Shop установлено</b>
📅 \$(date '+%d.%m.%Y %H:%M')
Все данные сохранены." >/dev/null 2>&1 || true
    fi
else
    warn "Сервис не ответил. Выполняем откат..."
    docker compose -f "\$COMPOSE_FILE" down || true
    tar -xzf "\$CODE_BACKUP" -C "\$INSTALL_DIR"
    if docker image inspect kaza_rollback:pre-deploy >/dev/null 2>&1; then
        TGT="\$(docker compose -f "\$COMPOSE_FILE" config --images 2>/dev/null | head -1 || echo kaza_shop_app)"
        docker tag kaza_rollback:pre-deploy "\$TGT" >/dev/null 2>&1 || true
    fi
    docker compose -f "\$COMPOSE_FILE" up -d || true
    sleep 15
    RC=\$(curl -sf -o /dev/null -w "%{http_code}" --max-time 10 "http://localhost:8000/health" 2>/dev/null || echo "000")
    rm -f "\$CODE_BACKUP"
    if [[ "\$RC" == "200" ]]; then
        warn "Откат выполнен. Сервис восстановлен до предыдущей версии."
    else
        err "Откат не помог. Проверьте логи: docker compose -f \$COMPOSE_FILE logs app --tail=50"
    fi
fi
HEREDOC

run_scp "$DEPLOY_SCRIPT" "${SSH_USER}@${SERVER_IP}:/tmp/kaza_deploy_run.sh"
# TEMP_DIR очищается автоматически через trap EXIT

info "Выполняем деплой на сервере..."
echo ""
run_ssh_long "bash /tmp/kaza_deploy_run.sh; rm -f /tmp/kaza_deploy_run.sh"

echo ""
echo -e "${BOLD}${GREEN}════════════════════════════════════════${NC}"
echo -e "${BOLD}${GREEN}  Деплой завершён!${NC}"
echo -e "${BOLD}${GREEN}════════════════════════════════════════${NC}"
echo ""
echo -e "  Сервер: ${CYAN}${SERVER_IP}${NC}"
echo ""
