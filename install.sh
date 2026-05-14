#!/usr/bin/env bash
# ==============================================================================
#  Kaza Shop - Универсальный установщик v3.0
#  Использование: bash install.sh
# ==============================================================================
set -euo pipefail

# ── Цвета ──────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

ok()   { echo -e "${GREEN}✓${NC} $*"; }
warn() { echo -e "${YELLOW}⚠${NC}  $*"; }
err()  { echo -e "${RED}✗ Ошибка:${NC} $*" >&2; exit 1; }
info() { echo -e "${BLUE}→${NC} $*"; }
step() { echo -e "\n${BOLD}$*${NC}"; echo "────────────────────────────────────────"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Утилиты: генерация секретов ────────────────────────────────────────────────
gen_secret() {
    if   command -v python3 &>/dev/null; then python3 -c "import secrets; print(secrets.token_hex(32))"
    elif command -v openssl &>/dev/null; then openssl rand -hex 32
    else cat /dev/urandom | tr -dc 'a-f0-9' | fold -w 64 | head -n 1; fi
}
gen_password() {
    if command -v python3 &>/dev/null; then
        python3 -c "import secrets,string; c=string.ascii_letters+string.digits; print(''.join(secrets.choice(c) for _ in range(24)))"
    elif command -v openssl &>/dev/null; then openssl rand -base64 18 | tr -dc 'a-zA-Z0-9' | head -c 24; echo
    else cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 24 | head -n 1; fi
}

# ── Утилита: проверка токена бота ──────────────────────────────────────────────
check_bot_token() {
    local token="$1" result
    result=$(curl -sf --max-time 10 "https://api.telegram.org/bot${token}/getMe" 2>/dev/null || echo '{"ok":false}')
    if echo "$result" | grep -q '"ok":true'; then
        if command -v python3 &>/dev/null; then
            BOT_NAME=$(echo "$result" | python3 -c \
                "import sys,json; d=json.load(sys.stdin); print(d.get('result',{}).get('username','bot'))" 2>/dev/null || echo "bot")
        else
            BOT_NAME=$(echo "$result" | sed 's/.*"username":"\([^"]*\)".*/\1/' 2>/dev/null || echo "bot")
        fi
        return 0
    fi
    return 1
}

# ── Баннер ─────────────────────────────────────────────────────────────────────
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
echo -e "  ${BOLD}Установщик Telegram-магазина для малого бизнеса${NC}"
echo -e "  Версия 3.0\n"

# ── Выбор режима ───────────────────────────────────────────────────────────────
step "Выберите режим установки"
echo ""
echo -e "  ${BOLD}1)${NC} 💻  ${BOLD}Локально${NC} — на этом компьютере"
echo -e "     Для тестирования и знакомства с магазином."
echo -e "     Нужен Docker Desktop. Покупатели бота не увидят."
echo ""
echo -e "  ${BOLD}2)${NC} 🌐  ${BOLD}На сервер VPS/VDS${NC} — для реальной работы"
echo -e "     Установщик сам подключится к серверу и настроит всё."
echo -e "     Нужны: IP сервера, SSH-доступ, токен бота."
echo ""
INSTALL_MODE=""
while true; do
    read -rp "  Ваш выбор (1 или 2): " MODE_CHOICE
    case "$MODE_CHOICE" in
        1) INSTALL_MODE="local";  break ;;
        2) INSTALL_MODE="server"; break ;;
        *) warn "Введите 1 или 2" ;;
    esac
done
echo ""

# ── Определяем способ установки на сервер ─────────────────────────────────────
# direct  - скрипт запущен прямо на сервере (Linux + root)
# remote  - скрипт запущен на локальной машине, деплой через SSH
DEPLOY_MODE="local"
if [[ "$INSTALL_MODE" == "server" ]]; then
    if [[ "$(uname -s)" == "Linux" ]] && [[ "$EUID" -eq 0 ]]; then
        DEPLOY_MODE="direct"
    else
        DEPLOY_MODE="remote"
        echo -e "  ${BLUE}→${NC} Режим удалённой установки: установщик подключится к серверу по SSH."
        if [[ "$(uname -s)" == "Linux" ]] && [[ "$EUID" -ne 0 ]]; then
            echo -e "  ${YELLOW}⚠${NC}  Если вы уже на сервере, запустите: ${BOLD}sudo bash install.sh${NC}"
        fi
        echo ""
    fi
fi

# ==============================================================================
#  ОБЩИЕ ВОПРОСЫ (задаются во всех режимах)
# ==============================================================================
step "Telegram-бот"
echo ""
echo -e "  ${YELLOW}Как получить токен бота:${NC}"
echo -e "  1. Telegram → @BotFather → /newbot → придумайте имя и username"
echo -e "  2. Скопируйте токен вида: 1234567890:ABCdef..."
echo ""
BOT_NAME="bot"
while true; do
    read -rp "  Токен Telegram-бота: " BOT_TOKEN
    BOT_TOKEN="${BOT_TOKEN// /}"
    [[ -z "$BOT_TOKEN" ]] && warn "Токен не может быть пустым" && continue
    info "Проверяем токен..."
    if check_bot_token "$BOT_TOKEN"; then ok "Токен валиден! Бот: @${BOT_NAME}"; break
    else warn "Токен недействителен или нет интернета. Попробуйте ещё раз."; fi
done

echo ""
echo -e "  ${YELLOW}Telegram ID:${NC} напишите @userinfobot — он пришлёт ваш числовой ID."
echo ""
while true; do
    read -rp "  Ваш Telegram ID (только цифры): " ADMIN_TG_ID
    ADMIN_TG_ID="${ADMIN_TG_ID// /}"
    [[ "$ADMIN_TG_ID" =~ ^[0-9]{5,12}$ ]] && break
    warn "Telegram ID — только цифры, обычно 8–10 знаков"
done
ok "Admin Telegram ID: $ADMIN_TG_ID"

echo ""
echo -e "  ${YELLOW}Пароль для панели управления.${NC} Минимум 10 символов, буквы + цифры."
echo ""
while true; do
    read -rsp "  Пароль администратора: " ADMIN_PASSWORD; echo ""
    [[ ${#ADMIN_PASSWORD} -lt 10 ]] && warn "Минимум 10 символов" && continue
    [[ ! "$ADMIN_PASSWORD" =~ [A-Za-z] ]] && warn "Нужна хотя бы одна буква" && continue
    [[ ! "$ADMIN_PASSWORD" =~ [0-9] ]] && warn "Нужна хотя бы одна цифра" && continue
    read -rsp "  Повторите пароль: " ADMIN_PASSWORD2; echo ""
    [[ "$ADMIN_PASSWORD" == "$ADMIN_PASSWORD2" ]] && break
    warn "Пароли не совпадают"
done
ok "Пароль задан"

# ==============================================================================
#  ВЕТКА А: ЛОКАЛЬНАЯ УСТАНОВКА
# ==============================================================================
if [[ "$INSTALL_MODE" == "local" ]]; then

    LOG_FILE="/tmp/kaza_install_$(date +%Y%m%d_%H%M%S).log"
    exec > >(tee -a "$LOG_FILE") 2>&1

    step "Шаг 1/3: Проверка Docker"
    command -v docker &>/dev/null \
        || err "Docker не установлен. Скачайте: https://docker.com/products/docker-desktop"
    docker info &>/dev/null 2>&1 \
        || err "Docker Desktop не запущен. Откройте его и дождитесь зелёной иконки в трее."
    ok "Docker: $(docker --version | cut -d' ' -f3 | tr -d ',')"
    docker compose version &>/dev/null 2>&1 \
        || err "Docker Compose V2 не найден. Обновите Docker Desktop."
    ok "Docker Compose: $(docker compose version --short 2>/dev/null || docker compose version)"

    echo ""
    echo -e "${BOLD}  Параметры:${NC}"
    echo -e "  Режим:   ${CYAN}Локально${NC}"
    echo -e "  Бот:     ${GREEN}@${BOT_NAME}${NC}"
    echo -e "  Панель:  ${GREEN}http://localhost:5173${NC}"
    echo ""
    read -rp "  Всё верно? Запустить? (y/N): " CONFIRM
    [[ "$CONFIRM" =~ ^[Yy]$ ]] || { info "Отменено."; exit 0; }

    step "Шаг 2/3: Создание конфигурации"

    # Если уже есть .env с DB_PASSWORD - переиспользуем его, чтобы не расходиться
    # с паролем, который уже записан в PostgreSQL-томе (повторный запуск / переустановка)
    EXISTING_ENV="${SCRIPT_DIR}/.env"
    VOLUME_NAME="$(basename "$SCRIPT_DIR")_postgres_data"
    if [[ -f "$EXISTING_ENV" ]] && docker volume ls -q | grep -qx "$VOLUME_NAME"; then
        OLD_DB_PASS=$(grep '^DB_PASSWORD=' "$EXISTING_ENV" | cut -d= -f2-)
        OLD_SECRET=$(grep '^SECRET_KEY='   "$EXISTING_ENV" | cut -d= -f2-)
        if [[ -n "$OLD_DB_PASS" && -n "$OLD_SECRET" ]]; then
            DB_PASSWORD="$OLD_DB_PASS"
            SECRET_KEY="$OLD_SECRET"
            BOT_API_TOKEN=$(grep '^BOT_API_TOKEN=' "$EXISTING_ENV" | cut -d= -f2-)
            [[ -z "$BOT_API_TOKEN" ]] && BOT_API_TOKEN=$(gen_secret)
            ok "Существующий PostgreSQL-том найден — переиспользуем пароль БД"
        else
            SECRET_KEY=$(gen_secret); DB_PASSWORD=$(gen_password); BOT_API_TOKEN=$(gen_secret)
            ok "Секреты сгенерированы"
        fi
    else
        SECRET_KEY=$(gen_secret); DB_PASSWORD=$(gen_password); BOT_API_TOKEN=$(gen_secret)
        ok "Секреты сгенерированы"
    fi

    {
        echo "# Kaza Shop — конфигурация (создано $(date))"
        echo "ENV=production"
        echo "DB_USER=kaza_user"
        printf 'DB_PASSWORD=%s\n' "$DB_PASSWORD"
        echo "DB_HOST=db"; echo "DB_PORT=5432"; echo "DB_NAME=kaza_shop"
        printf 'SECRET_KEY=%s\n'     "$SECRET_KEY"
        printf 'ADMIN_PASSWORD=%s\n' "$ADMIN_PASSWORD"
        printf 'ADMIN_TG_ID=%s\n'    "$ADMIN_TG_ID"
        printf 'BOT_TOKEN=%s\n'      "$BOT_TOKEN"
        printf 'BOT_API_TOKEN=%s\n'  "$BOT_API_TOKEN"
        echo "DOMAIN=localhost"
        echo "CORS_ORIGINS=http://localhost:5173"
        printf 'ALERT_BOT_TOKEN=%s\n' "$BOT_TOKEN"
        printf 'ALERT_CHAT_ID=%s\n'   "$ADMIN_TG_ID"
        echo "REDIS_URL=redis://redis:6379/0"
        echo "BACKUP_KEEP_DAYS=14"; echo "LOG_LEVEL=INFO"
        echo "UPDATE_CHANNEL=git"
        echo "UPDATE_BRANCH=main"
        echo "UPDATE_ARCHIVE_URL="
    } > "$EXISTING_ENV"
    chmod 600 "$EXISTING_ENV"
    ok ".env создан"

    step "Шаг 3/3: Запуск магазина"
    cd "$SCRIPT_DIR"
    info "Первый запуск занимает 3–7 минут..."
    echo ""
    docker compose up -d --build
    ok "Контейнеры запущены"
    echo ""
    info "Ожидаем готовности API (до 90 сек)..."
    API_READY=0
    for i in $(seq 1 18); do
        sleep 5
        if curl -sf "http://localhost:8000/health" &>/dev/null; then API_READY=1; ok "API отвечает"; break; fi
        echo -n "  ."
    done
    echo ""
    [[ $API_READY -eq 0 ]] && warn "API не ответил. Проверьте: docker compose ps && docker compose logs app"

    if [[ $API_READY -eq 1 ]]; then
        info "Проверяем авторизацию администратора..."
        sleep 2
        AUTH_TEST=$(curl -sf -X POST "http://localhost:8000/auth/login" \
            -H "Content-Type: application/json" \
            -d "{\"login\":\"admin\",\"password\":\"${ADMIN_PASSWORD}\"}" 2>/dev/null || echo '{}')
        if echo "$AUTH_TEST" | grep -q '"token"'; then
            ok "Администратор готов (логин: admin)"
        else
            warn "Не удалось проверить авторизацию. Войдите в панель с паролем, который вы задали."
        fi
    fi

    echo ""
    echo -e "${BOLD}${GREEN}════════════════════════════════════════${NC}"
    echo -e "${BOLD}${GREEN}  ✓ Магазин запущен!${NC}"
    echo -e "${BOLD}${GREEN}════════════════════════════════════════${NC}"
    echo ""
    echo -e "  🖥  Панель: ${CYAN}http://localhost:5173${NC}   логин ${GREEN}admin${NC}"
    echo -e "  🤖  Бот:    ${CYAN}@${BOT_NAME}${NC}"
    echo ""
    echo -e "  ${BOLD}Управление:${NC}"
    printf "  %-12s %s\n" "Запустить:"  "docker compose up -d"
    printf "  %-12s %s\n" "Остановить:" "docker compose down"
    printf "  %-12s %s\n" "Логи:"       "docker compose logs -f"
    echo ""
    echo -e "  ${YELLOW}⚠  Локальный запуск — покупатели магазин не видят.${NC}"
    echo -e "  Для реального запуска: ${BOLD}bash install.sh${NC} → выбрать ${BOLD}«На сервер»${NC}."
    echo ""
    echo -e "  Лог: ${LOG_FILE}"
    exit 0
fi

# ==============================================================================
#  ВЕТКА Б: ПРЯМАЯ УСТАНОВКА НА СЕРВЕРЕ (скрипт запущен на самом сервере)
# ==============================================================================
if [[ "$DEPLOY_MODE" == "direct" ]]; then

    LOG_FILE="/tmp/kaza_install_$(date +%Y%m%d_%H%M%S).log"
    exec > >(tee -a "$LOG_FILE") 2>&1
    INSTALL_DIR="/opt/kaza_shop"

    step "Шаг 1/9: Проверка системы"
    ok "Запущен от root"
    . /etc/os-release 2>/dev/null || true
    if [[ "${ID:-}" != "ubuntu" && "${ID:-}" != "debian" ]]; then
        warn "ОС: ${PRETTY_NAME:-unknown}. Протестировано на Ubuntu 22.04 / Debian 12."
        read -rp "  Продолжить? (y/N): " _c; [[ "$_c" =~ ^[Yy]$ ]] || exit 1
    fi
    ok "ОС: ${PRETTY_NAME:-Linux}"
    RAM_MB=$(free -m | awk '/^Mem:/{print $2}')
    DISK_GB=$(df -BG / | awk 'NR==2{gsub("G",""); print $4}')
    [[ "$RAM_MB" -lt 768 ]] && warn "RAM: ${RAM_MB} MB (рекомендуется 1 GB+)"
    [[ "$DISK_GB" -lt 5  ]] && warn "Диск: ${DISK_GB} GB (рекомендуется 10 GB+)"
    ok "RAM: ${RAM_MB} MB, диск: ${DISK_GB} GB"

    step "Шаг 2/9: Установка зависимостей"
    if ! command -v docker &>/dev/null; then
        info "Устанавливаем Docker..."
        curl -fsSL https://get.docker.com | sh || {
            warn "get.docker.com недоступен, пробуем apt..."
            apt-get update && apt-get install -y docker.io docker-compose-plugin
        }
        systemctl enable --now docker
        ok "Docker установлен"
    else ok "Docker: $(docker --version)"; fi
    docker compose version &>/dev/null 2>&1 || apt-get install -y docker-compose-plugin
    ok "Docker Compose готов"
    # Зеркала Docker Hub (на случай медленного или заблокированного доступа)
    info "Настраиваем зеркала Docker Hub..."
    mkdir -p /etc/docker
    cat > /etc/docker/daemon.json << 'DOCKERCFG'
{
  "registry-mirrors": [
    "https://huecker.io",
    "https://dockerhub.timeweb.cloud",
    "https://mirror.gcr.io"
  ],
  "dns": ["8.8.8.8", "1.1.1.1"]
}
DOCKERCFG
    systemctl restart docker
    ok "Зеркала Docker Hub настроены"
    if ! command -v nginx &>/dev/null; then
        info "Устанавливаем nginx и certbot..."
        apt-get update
        apt-get install -y --no-install-recommends nginx certbot python3-certbot-nginx curl ufw
        ok "Nginx и certbot установлены"
    else ok "Nginx: $(nginx -v 2>&1 | grep -o '[0-9.]*$' || echo ok)"; fi
    # Firewall
    if command -v ufw &>/dev/null; then
        ufw allow OpenSSH >/dev/null 2>&1 || true
        ufw allow 80/tcp  >/dev/null 2>&1 || true
        ufw allow 443/tcp >/dev/null 2>&1 || true
        ufw --force enable >/dev/null 2>&1 || true
        ok "Firewall: SSH + 80 + 443 открыты"
    fi

    step "Шаг 3/9: Настройка домена"
    echo ""
    echo -e "  ${YELLOW}A-запись домена должна уже указывать на IP этого сервера.${NC}"
    echo ""
    while true; do
        read -rp "  Домен (например myshop.ru): " DOMAIN
        DOMAIN="${DOMAIN// /}"; DOMAIN="${DOMAIN#https://}"; DOMAIN="${DOMAIN#http://}"; DOMAIN="${DOMAIN%%/*}"
        [[ -z "$DOMAIN" ]] && warn "Домен не может быть пустым" && continue
        [[ "$DOMAIN" =~ ^[a-zA-Z0-9]([a-zA-Z0-9.-]*[a-zA-Z0-9])?$ ]] && [[ "$DOMAIN" =~ \. ]] && break
        warn "Некорректный домен. Пример: myshop.ru"
    done
    ok "Домен: $DOMAIN"
    read -rp "  Email для SSL (Enter — пропустить): " SSL_EMAIL
    [[ -z "$SSL_EMAIL" ]] && SSL_EMAIL="admin@${DOMAIN}"

    echo ""
    echo -e "${BOLD}  Параметры:${NC}"
    echo -e "  Домен:   ${GREEN}${DOMAIN}${NC}"
    echo -e "  Бот:     ${GREEN}@${BOT_NAME}${NC}"
    echo -e "  Папка:   ${GREEN}${INSTALL_DIR}${NC}"
    echo ""
    read -rp "  Всё верно? Начать установку? (y/N): " CONFIRM
    [[ "$CONFIRM" =~ ^[Yy]$ ]] || { info "Отменено."; exit 0; }

    step "Шаг 4/9: Генерация секретов"
    # При переустановке на сервер с существующим PostgreSQL-томом сохраняем пароль БД.
    # Новый пароль не совпадёт со старым томом → app не сможет подключиться.
    EXISTING_ENV_DIRECT="${INSTALL_DIR}/.env"
    VOLUME_NAME_DIRECT="kaza_shop_postgres_data"
    if [[ -f "$EXISTING_ENV_DIRECT" ]] && docker volume ls -q | grep -qx "$VOLUME_NAME_DIRECT"; then
        OLD_DB_PASS_D=$(grep '^DB_PASSWORD=' "$EXISTING_ENV_DIRECT" | cut -d= -f2-)
        OLD_SECRET_D=$(grep '^SECRET_KEY='   "$EXISTING_ENV_DIRECT" | cut -d= -f2-)
        if [[ -n "$OLD_DB_PASS_D" && -n "$OLD_SECRET_D" ]]; then
            DB_PASSWORD="$OLD_DB_PASS_D"
            SECRET_KEY="$OLD_SECRET_D"
            BOT_API_TOKEN=$(grep '^BOT_API_TOKEN=' "$EXISTING_ENV_DIRECT" | cut -d= -f2-)
            [[ -z "$BOT_API_TOKEN" ]] && BOT_API_TOKEN=$(gen_secret)
            ok "Существующий PostgreSQL-том найден — переиспользуем пароль и ключ БД"
        else
            SECRET_KEY=$(gen_secret); DB_PASSWORD=$(gen_password); BOT_API_TOKEN=$(gen_secret)
            ok "Секреты сгенерированы"
        fi
    else
        SECRET_KEY=$(gen_secret); DB_PASSWORD=$(gen_password); BOT_API_TOKEN=$(gen_secret)
        ok "Секреты сгенерированы"
    fi

    step "Шаг 5/9: Копирование файлов"
    [[ "$SCRIPT_DIR" != "$INSTALL_DIR" ]] && mkdir -p "$INSTALL_DIR" && cp -r "${SCRIPT_DIR}/." "$INSTALL_DIR/" && ok "Файлы скопированы" || ok "Уже в $INSTALL_DIR"
    mkdir -p "${INSTALL_DIR}/media" "${INSTALL_DIR}/data" "${INSTALL_DIR}/logs" "${INSTALL_DIR}/backups"
    chown -R 1000:1000 "${INSTALL_DIR}/data" "${INSTALL_DIR}/media" "${INSTALL_DIR}/logs"
    chmod 755 "${INSTALL_DIR}/data" "${INSTALL_DIR}/media" "${INSTALL_DIR}/logs"
    chmod 755 "${INSTALL_DIR}/backup.sh" "${INSTALL_DIR}/healthcheck.sh" \
               "${INSTALL_DIR}/update.sh" "${INSTALL_DIR}/restore.sh" \
               "${INSTALL_DIR}/deploy.sh" 2>/dev/null || true
    ok "Директории созданы"

    step "Шаг 6/9: Создание конфигурации"
    {
        echo "# Kaza Shop — конфигурация (создано $(date))"
        echo "ENV=production"
        echo "DB_USER=kaza_user"
        printf 'DB_PASSWORD=%s\n' "$DB_PASSWORD"
        echo "DB_HOST=db"; echo "DB_PORT=5432"; echo "DB_NAME=kaza_shop"
        printf 'SECRET_KEY=%s\n' "$SECRET_KEY"
        printf 'ADMIN_PASSWORD=%s\n' "$ADMIN_PASSWORD"
        printf 'ADMIN_TG_ID=%s\n'   "$ADMIN_TG_ID"
        printf 'BOT_TOKEN=%s\n'     "$BOT_TOKEN"
        printf 'BOT_API_TOKEN=%s\n' "$BOT_API_TOKEN"
        printf 'DOMAIN=%s\n'        "$DOMAIN"
        printf 'CORS_ORIGINS=https://%s\n' "$DOMAIN"
        printf 'ALERT_BOT_TOKEN=%s\n' "$BOT_TOKEN"
        printf 'ALERT_CHAT_ID=%s\n'   "$ADMIN_TG_ID"
        echo "REDIS_URL=redis://redis:6379/0"
        echo "BACKUP_KEEP_DAYS=14"; echo "LOG_LEVEL=INFO"
        echo "UPDATE_CHANNEL=git"
        echo "UPDATE_BRANCH=main"
        echo "UPDATE_ARCHIVE_URL="
    } > "${INSTALL_DIR}/.env"
    chmod 600 "${INSTALL_DIR}/.env"
    ok ".env создан"

    step "Шаг 7/9: Настройка Nginx и SSL"
    printf 'server {\n    listen 80;\n    server_name %s;\n    location / { return 200 '"'"'ok'"'"'; add_header Content-Type text/plain; }\n}\n' \
        "$DOMAIN" > /etc/nginx/sites-available/kaza_shop
    ln -sf /etc/nginx/sites-available/kaza_shop /etc/nginx/sites-enabled/kaza_shop
    rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true
    nginx -t 2>/dev/null && systemctl reload nginx

    SSL_FAILED=0
    info "Получаем SSL-сертификат..."
    if certbot certonly --nginx --non-interactive --agree-tos --email "$SSL_EMAIL" -d "$DOMAIN" 2>&1; then
        ok "SSL получен"
        cp "${INSTALL_DIR}/nginx/kaza_shop.conf" /etc/nginx/sites-available/kaza_shop
        sed -i "s/YOUR_DOMAIN/${DOMAIN}/g" /etc/nginx/sites-available/kaza_shop
        nginx -t 2>/dev/null && systemctl reload nginx && ok "Nginx настроен с SSL"
        (crontab -l 2>/dev/null || echo "") | grep -v certbot > /tmp/crontab_ssl
        echo "0 3 * * * certbot renew --quiet --post-hook 'systemctl reload nginx'" >> /tmp/crontab_ssl
        crontab /tmp/crontab_ssl
    else
        SSL_FAILED=1
        warn "SSL не получен. Проверьте DNS домена $DOMAIN."
        warn "Настройте позже: certbot --nginx -d $DOMAIN"
        cp "${INSTALL_DIR}/nginx/kaza_shop_nossl.conf" /etc/nginx/sites-available/kaza_shop
        nginx -t 2>/dev/null && systemctl reload nginx && ok "Nginx настроен (без SSL)"
    fi

    step "Шаг 8/9: Запуск магазина"
    cd "$INSTALL_DIR"
    info "Проверяем файлы миграций Alembic..."
    python3 - <<'PY'
from pathlib import Path
import sys

base = Path("/opt/kaza_shop/alembic/versions")
files = sorted(
    p for p in base.glob("*.py")
    if not p.name.startswith("._")
)
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
    ok "Миграции Alembic валидны"
    echo ""
    echo -e "${YELLOW}  ⏳ Скачиваем и собираем образы - это займёт 5-15 минут.${NC}"
    echo -e "${YELLOW}  Пожалуйста, не прерывайте процесс.${NC}"
    echo ""
    BUILD_OK=0
    for attempt in 1 2 3; do
        [[ $attempt -gt 1 ]] && warn "Повтор попытки ${attempt}/3..." && sleep 10
        if docker compose -f docker-compose.prod.yml build 2>&1; then
            BUILD_OK=1; break
        fi
    done
    if [[ $BUILD_OK -eq 0 ]]; then
        warn "Сборка образов не удалась после 3 попыток."
        warn "Запустите вручную: cd $INSTALL_DIR && docker compose -f docker-compose.prod.yml build"
    else
        ok "Образы собраны"
        docker compose -f docker-compose.prod.yml up -d; ok "Сервисы запущены"
    fi
    step "Шаг 9/9: Автоматизация"
    cat > /etc/systemd/system/kaza_shop.service << SYSTEMD_EOF
[Unit]
Description=Kaza Shop Telegram Store
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=${INSTALL_DIR}
ExecStart=/usr/bin/docker compose -f docker-compose.prod.yml up -d
ExecStop=/usr/bin/docker compose -f docker-compose.prod.yml down
TimeoutStartSec=120

[Install]
WantedBy=multi-user.target
SYSTEMD_EOF
    systemctl daemon-reload; systemctl enable kaza_shop.service
    ok "Автозапуск при перезагрузке настроен"
    (crontab -l 2>/dev/null | grep -v kaza_shop) > /tmp/crontab_kaza || true
    # Ежедневный бэкап в 02:00 (хранится 14 дней)
    printf '0 2 * * *   bash %s/backup.sh           >> %s/logs/backup.log        2>&1 # kaza_shop\n' "$INSTALL_DIR" "$INSTALL_DIR" >> /tmp/crontab_kaza
    # Почасовой бэкап — перезаписывает предыдущий, отправляет файл в Telegram
    printf '0 * * * *   bash %s/backup.sh --hourly  >> %s/logs/backup_hourly.log 2>&1 # kaza_shop\n' "$INSTALL_DIR" "$INSTALL_DIR" >> /tmp/crontab_kaza
    # Мониторинг каждые 5 минут
    printf '*/5 * * * * bash %s/healthcheck.sh       >> %s/logs/monitor.log       2>&1 # kaza_shop\n' "$INSTALL_DIR" "$INSTALL_DIR" >> /tmp/crontab_kaza
    crontab /tmp/crontab_kaza
    ok "Cron: ежедневный бэкап в 02:00 (в Telegram), почасовой локально, мониторинг каждые 5 мин"

    echo ""
    info "Ожидаем готовности API (до 2 мин)..."
    API_READY=0
    for i in $(seq 1 24); do
        sleep 5
        if curl -sf "http://localhost:8000/health" &>/dev/null; then API_READY=1; ok "API отвечает"; break; fi
        echo -n "."
    done
    echo ""
    if [[ $API_READY -eq 0 ]]; then
        warn "API не ответил в течение 2 минут. Проверьте: docker compose -f docker-compose.prod.yml logs app"
    fi

    if [[ $API_READY -eq 1 ]]; then
        info "Проверяем авторизацию администратора..."
        sleep 2
        AUTH_TEST=$(curl -sf -X POST "http://localhost:8000/auth/login" \
            -H "Content-Type: application/json" \
            -d "{\"login\":\"admin\",\"password\":\"${ADMIN_PASSWORD}\"}" 2>/dev/null || echo '{}')
        if echo "$AUTH_TEST" | grep -q '"token"'; then
            ok "Администратор готов (логин: admin)"
        else
            warn "Не удалось проверить авторизацию. Войдите в панель с паролем, который вы задали."
        fi
    fi

    PANEL_URL="https://${DOMAIN}"
    [[ $SSL_FAILED -eq 1 ]] && PANEL_URL="http://${DOMAIN}"
    echo ""
    echo -e "${BOLD}${GREEN}════════════════════════════════════════${NC}"
    echo -e "${BOLD}${GREEN}  ✓ Установка завершена!${NC}"
    [[ $SSL_FAILED -eq 1 ]] && echo -e "${BOLD}${YELLOW}  ⚠  SSL не настроен - настройте вручную${NC}"
    echo -e "${BOLD}${GREEN}════════════════════════════════════════${NC}"
    echo ""
    echo -e "  🌐  Панель: ${CYAN}${PANEL_URL}${NC}   логин ${GREEN}admin${NC}"
    echo -e "  🤖  Бот:    ${CYAN}@${BOT_NAME}${NC}"
    echo ""
    echo -e "  Лог: ${LOG_FILE}"
    echo ""
    curl -sf "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
        -d "chat_id=${ADMIN_TG_ID}" -d "parse_mode=HTML" \
        --data-urlencode "text=🎉 <b>Kaza Shop установлен!</b>

🌐 Панель: ${PANEL_URL}
🤖 Бот: @${BOT_NAME}

Логин: <code>admin</code>
Пароль: тот что вы задали" >/dev/null 2>&1 || true
    exit 0
fi

# ==============================================================================
#  ВЕТКА В: УДАЛЁННАЯ УСТАНОВКА ЧЕРЕЗ SSH (со своей машины на VPS)
# ==============================================================================
# Лог-файл определяем заранее, но редирект включаем только ПОСЛЕ всех вопросов
LOG_FILE="/tmp/kaza_install_$(date +%Y%m%d_%H%M%S).log"

# ── Данные сервера ─────────────────────────────────────────────────────────────
step "Шаг 1/5: Данные сервера"
echo ""
while true; do
    read -rp "  IP-адрес сервера: " SERVER_IP
    SERVER_IP="${SERVER_IP// /}"
    [[ -n "$SERVER_IP" ]] && break
    warn "IP не может быть пустым"
done

read -rp "  SSH пользователь (Enter = root): " SSH_USER
SSH_USER="${SSH_USER:-root}"

read -rp "  SSH порт (Enter = 22): " SSH_PORT
SSH_PORT="${SSH_PORT:-22}"

echo ""
echo -e "  ${YELLOW}Способ подключения:${NC}"
echo -e "  ${BOLD}1)${NC} Пароль"
echo -e "  ${BOLD}2)${NC} SSH-ключ (файл)"
echo ""
while true; do
    read -rp "  Выбор (1/2): " AUTH_CHOICE
    case "$AUTH_CHOICE" in 1|2) break ;; *) warn "Введите 1 или 2" ;; esac
done

SSH_OPTS=(
    -p "$SSH_PORT"
    -o StrictHostKeyChecking=no
    -o ConnectTimeout=10
    -o ServerAliveInterval=5
    -o ServerAliveCountMax=2
    -o NumberOfPasswordPrompts=1
)
SCP_OPTS=(-P "$SSH_PORT" -o StrictHostKeyChecking=no -o ConnectTimeout=10)
AUTH_METHOD=""
SSH_PASS=""
SSH_KEY=""

if [[ "$AUTH_CHOICE" == "1" ]]; then
    AUTH_METHOD="password"
    # Проверяем наличие sshpass
    if ! command -v sshpass &>/dev/null; then
        warn "Утилита sshpass не установлена."
        if command -v brew &>/dev/null; then
            info "Устанавливаем через Homebrew..."
            brew install hudochenkov/sshpass/sshpass 2>/dev/null \
                || brew install sshpass 2>/dev/null \
                || err "Не удалось установить sshpass. Используйте SSH-ключ."
        elif command -v apt-get &>/dev/null; then
            apt-get install -y -q sshpass
        else
            err "Установите sshpass или выберите метод SSH-ключ."
        fi
    fi
    read -rsp "  SSH-пароль для ${SSH_USER}@${SERVER_IP}: " SSH_PASS; echo ""
else
    AUTH_METHOD="key"
    read -rp "  Путь к SSH-ключу (Enter = ~/.ssh/id_rsa): " SSH_KEY
    SSH_KEY="${SSH_KEY:-${HOME}/.ssh/id_rsa}"
    [[ -f "$SSH_KEY" ]] || err "Файл ключа не найден: $SSH_KEY"
    SSH_OPTS+=(-i "$SSH_KEY" -o BatchMode=yes)
    SCP_OPTS+=(-i "$SSH_KEY")
fi

# Функции-обёртки для ssh и scp
# run_ssh      - короткие команды (проверка соединения, OS), таймаут 25 сек
# run_ssh_long - долгие команды (установка), без таймаута; ServerAlive держит сессию
_timeout_cmd() {
    if command -v timeout &>/dev/null; then
        timeout "$@"
    elif command -v gtimeout &>/dev/null; then
        gtimeout "$@"
    else
        shift; "$@"
    fi
}

# SSH_OPTS для долгих сессий: увеличиваем ServerAliveCountMax чтобы не дропать при долгих apt/docker операциях
SSH_LONG_OPTS=(
    -p "$SSH_PORT"
    -o StrictHostKeyChecking=no
    -o ConnectTimeout=10
    -o ServerAliveInterval=30
    -o ServerAliveCountMax=60
    -o NumberOfPasswordPrompts=1
)
[[ "$AUTH_METHOD" == "key" ]] && SSH_LONG_OPTS+=(-i "$SSH_KEY" -o BatchMode=yes)

run_ssh() {
    if [[ "$AUTH_METHOD" == "password" ]]; then
        SSHPASS="$SSH_PASS" _timeout_cmd 25 sshpass -e ssh "${SSH_OPTS[@]}" "${SSH_USER}@${SERVER_IP}" "$@"
    else
        _timeout_cmd 25 ssh "${SSH_OPTS[@]}" "${SSH_USER}@${SERVER_IP}" "$@"
    fi
}
run_ssh_long() {
    # Без внешнего таймаута - установка может идти 20–40 минут
    if [[ "$AUTH_METHOD" == "password" ]]; then
        SSHPASS="$SSH_PASS" sshpass -e ssh "${SSH_LONG_OPTS[@]}" "${SSH_USER}@${SERVER_IP}" "$@"
    else
        ssh "${SSH_LONG_OPTS[@]}" "${SSH_USER}@${SERVER_IP}" "$@"
    fi
}
run_scp() {
    if [[ "$AUTH_METHOD" == "password" ]]; then
        SSHPASS="$SSH_PASS" sshpass -e scp "${SCP_OPTS[@]}" "$@"
    else
        scp "${SCP_OPTS[@]}" "$@"
    fi
}

# Проверка соединения
info "Проверяем подключение к ${SERVER_IP}:${SSH_PORT}..."
set +e   # временно отключаем выход при ошибке - нужно поймать код возврата
SSH_TEST_OUTPUT=$(run_ssh "echo ok" 2>&1)
SSH_TEST_RC=$?
set -e

# Автоисправление: конфликт host key (сервер переустановлен или сменился IP)
if [[ $SSH_TEST_RC -ne 0 ]] && echo "$SSH_TEST_OUTPUT" | grep -qi "Host key verification\|REMOTE HOST IDENTIFICATION"; then
    warn "Ключ сервера изменился (сервер переустановлен?). Удаляем старый ключ..."
    ssh-keygen -R "${SERVER_IP}" -f "${HOME}/.ssh/known_hosts" >/dev/null 2>&1 || true
    # Удаляем также запись по порту, если нестандартный
    [[ "$SSH_PORT" != "22" ]] && ssh-keygen -R "[${SERVER_IP}]:${SSH_PORT}" -f "${HOME}/.ssh/known_hosts" >/dev/null 2>&1 || true
    ok "Старый ключ удалён. Повторяем подключение..."
    set +e
    SSH_TEST_OUTPUT=$(run_ssh "echo ok" 2>&1)
    SSH_TEST_RC=$?
    set -e
fi

if [[ $SSH_TEST_RC -ne 0 ]]; then
    echo ""
    echo -e "${RED}Не удалось подключиться к серверу.${NC}"
    echo -e "Вывод SSH:\n${YELLOW}${SSH_TEST_OUTPUT}${NC}"
    echo ""
    if echo "$SSH_TEST_OUTPUT" | grep -qi "Permission denied\|Authentication failed\|invalid password"; then
        echo -e "  ${YELLOW}→ Неверный пароль или пользователь.${NC}"
    elif echo "$SSH_TEST_OUTPUT" | grep -qi "Connection refused"; then
        echo -e "  ${YELLOW}→ Сервер не принимает SSH на порту ${SSH_PORT}. Проверьте порт.${NC}"
    elif echo "$SSH_TEST_OUTPUT" | grep -qi "No route to host\|Network is unreachable\|timed out"; then
        echo -e "  ${YELLOW}→ Сервер недоступен. Проверьте IP и firewall.${NC}"
    elif echo "$SSH_TEST_OUTPUT" | grep -qi "Host key verification\|REMOTE HOST IDENTIFICATION"; then
        echo -e "  ${YELLOW}→ Конфликт host key. Выполните вручную: ssh-keygen -R ${SERVER_IP}${NC}"
    fi
    exit 1
fi
ok "Подключение установлено"

# Проверка ОС на сервере
set +e
REMOTE_OS=$(run_ssh "source /etc/os-release 2>/dev/null && echo \$ID" 2>/dev/null)
[[ -z "$REMOTE_OS" ]] && REMOTE_OS="unknown"
set -e
if [[ "$REMOTE_OS" != "ubuntu" && "$REMOTE_OS" != "debian" ]]; then
    warn "ОС сервера: ${REMOTE_OS}. Протестировано на Ubuntu 22.04 / Debian 12."
    read -rp "  Продолжить? (y/N): " _c; [[ "$_c" =~ ^[Yy]$ ]] || exit 1
fi
ok "ОС сервера: ${REMOTE_OS}"

# ── Топология развёртывания ────────────────────────────────────────────────────
step "Шаг 2/6: Топология развёртывания"
echo ""
echo -e "  ${BOLD}1)${NC} 🖥  ${BOLD}Один сервер${NC} — приложение и данные вместе"
echo -e "     Проще. Подходит, если сервер находится в России"
echo -e "     или требования 152-ФЗ неактуальны."
echo ""
echo -e "  ${BOLD}2)${NC} 🌐+🇷🇺  ${BOLD}Два сервера${NC} — приложение и данные раздельно"
echo -e "     Приложение/бот: ${SERVER_IP} (может быть за рубежом — для доступа к Telegram)"
echo -e "     База данных/Redis: отдельный российский сервер (152-ФЗ)"
echo -e "     Оба сервера могут иметь один и тот же IP — тогда поведение как в режиме 1."
echo ""
TOPOLOGY=""
while true; do
    read -rp "  Выбор (1 или 2): " TOP_CHOICE
    case "$TOP_CHOICE" in
        1) TOPOLOGY="single"; break ;;
        2) TOPOLOGY="split";  break ;;
        *) warn "Введите 1 или 2" ;;
    esac
done
ok "Топология: ${TOPOLOGY}"

# ── DATA-сервер (только для split-топологии) ───────────────────────────────────
DATA_SERVER_IP=""
DATA_SERVER_USER="root"
DATA_SERVER_PORT="22"
DATA_SERVER_PASS=""
DATA_SERVER_KEY=""
DATA_AUTH_METHOD="password"

if [[ "$TOPOLOGY" == "split" ]]; then
    echo ""
    echo -e "  ${YELLOW}Данные для подключения к DATA-серверу (Россия):${NC}"
    echo ""
    while true; do
        read -rp "  IP DATA-сервера: " DATA_SERVER_IP
        DATA_SERVER_IP="${DATA_SERVER_IP// /}"
        [[ -n "$DATA_SERVER_IP" ]] && break
        warn "IP не может быть пустым"
    done
    read -rp "  SSH пользователь DATA-сервера (Enter = root): " DATA_SERVER_USER
    DATA_SERVER_USER="${DATA_SERVER_USER:-root}"
    read -rp "  SSH порт DATA-сервера (Enter = 22): " DATA_SERVER_PORT
    DATA_SERVER_PORT="${DATA_SERVER_PORT:-22}"

    echo ""
    echo -e "  ${YELLOW}Аутентификация на DATA-сервере:${NC}"
    echo -e "  ${BOLD}1)${NC} Пароль   ${BOLD}2)${NC} SSH-ключ"
    while true; do
        read -rp "  Выбор (1/2): " DATA_AUTH_CHOICE
        case "$DATA_AUTH_CHOICE" in 1|2) break ;; *) warn "Введите 1 или 2" ;; esac
    done
    DATA_SSH_OPTS=(-p "$DATA_SERVER_PORT" -o StrictHostKeyChecking=no -o ConnectTimeout=10
                   -o ServerAliveInterval=30 -o ServerAliveCountMax=60)
    DATA_SCP_OPTS=(-P "$DATA_SERVER_PORT" -o StrictHostKeyChecking=no)
    if [[ "$DATA_AUTH_CHOICE" == "1" ]]; then
        DATA_AUTH_METHOD="password"
        read -rsp "  SSH-пароль для ${DATA_SERVER_USER}@${DATA_SERVER_IP}: " DATA_SERVER_PASS; echo ""
    else
        DATA_AUTH_METHOD="key"
        read -rp "  Путь к SSH-ключу (Enter = ~/.ssh/id_rsa): " DATA_SERVER_KEY
        DATA_SERVER_KEY="${DATA_SERVER_KEY:-${HOME}/.ssh/id_rsa}"
        [[ -f "$DATA_SERVER_KEY" ]] || err "Файл ключа не найден: $DATA_SERVER_KEY"
        DATA_SSH_OPTS+=(-i "$DATA_SERVER_KEY" -o BatchMode=yes)
        DATA_SCP_OPTS+=(-i "$DATA_SERVER_KEY")
    fi

    # Обёртки для DATA-сервера
    run_data_ssh() {
        if [[ "$DATA_AUTH_METHOD" == "password" ]]; then
            SSHPASS="$DATA_SERVER_PASS" sshpass -e ssh "${DATA_SSH_OPTS[@]}" \
                "${DATA_SERVER_USER}@${DATA_SERVER_IP}" "$@"
        else
            ssh "${DATA_SSH_OPTS[@]}" "${DATA_SERVER_USER}@${DATA_SERVER_IP}" "$@"
        fi
    }
    run_data_scp() {
        if [[ "$DATA_AUTH_METHOD" == "password" ]]; then
            SSHPASS="$DATA_SERVER_PASS" sshpass -e scp "${DATA_SCP_OPTS[@]}" "$@"
        else
            scp "${DATA_SCP_OPTS[@]}" "$@"
        fi
    }

    # Проверяем подключение к DATA-серверу
    info "Проверяем подключение к DATA-серверу ${DATA_SERVER_IP}:${DATA_SERVER_PORT}..."
    set +e
    DATA_SSH_TEST=$(run_data_ssh "echo ok" 2>&1)
    DATA_SSH_RC=$?
    set -e
    if [[ $DATA_SSH_RC -ne 0 ]]; then
        err "Не удалось подключиться к DATA-серверу: ${DATA_SSH_TEST}"
    fi
    ok "DATA-сервер: подключение установлено"

    # Одинаковый IP = фактически один сервер → переключаем в single
    if [[ "$DATA_SERVER_IP" == "$SERVER_IP" ]]; then
        warn "DATA-сервер совпадает с APP-сервером — автоматически переключаемся в режим «один сервер»"
        TOPOLOGY="single"
    fi
fi

# ── Настройка домена ───────────────────────────────────────────────────────────
step "Шаг 3/6: Домен и SSL (APP-сервер)"
echo ""
echo -e "  Домен необязателен — панель управления работает и по IP."
echo -e "  Домен нужен для HTTPS. Если используете домен, его A-запись"
echo -e "  должна уже указывать на ${SERVER_IP}."
echo ""
read -rp "  Домен (Enter — использовать IP ${SERVER_IP}): " DOMAIN
DOMAIN="${DOMAIN// /}"; DOMAIN="${DOMAIN#https://}"; DOMAIN="${DOMAIN#http://}"; DOMAIN="${DOMAIN%%/*}"

USE_SSL=0
SSL_EMAIL=""
if [[ -z "$DOMAIN" ]]; then
    DOMAIN="$SERVER_IP"
    ok "Будет использован IP: $SERVER_IP (без SSL)"
elif [[ "$DOMAIN" =~ ^[a-zA-Z0-9]([a-zA-Z0-9.-]*[a-zA-Z0-9])?$ ]] && [[ "$DOMAIN" =~ \. ]]; then
    USE_SSL=1
    read -rp "  Email для SSL (Enter — пропустить): " SSL_EMAIL
    [[ -z "$SSL_EMAIL" ]] && SSL_EMAIL="admin@${DOMAIN}"
    ok "Домен: $DOMAIN, SSL: да"
else
    DOMAIN="$SERVER_IP"
    warn "Некорректный домен — используем IP: $SERVER_IP"
fi

# ── Итог и подтверждение ───────────────────────────────────────────────────────
PANEL_URL="http://${SERVER_IP}"
[[ $USE_SSL -eq 1 ]] && PANEL_URL="https://${DOMAIN}"

echo ""
echo -e "${BOLD}  Параметры установки:${NC}"
echo -e "  Топология: ${CYAN}${TOPOLOGY}${NC}"
echo -e "  APP-сервер:  ${GREEN}${SSH_USER}@${SERVER_IP}:${SSH_PORT}${NC}"
[[ "$TOPOLOGY" == "split" ]] && \
    echo -e "  DATA-сервер: ${YELLOW}${DATA_SERVER_USER}@${DATA_SERVER_IP}:${DATA_SERVER_PORT}${NC}"
echo -e "  Домен:   ${GREEN}${DOMAIN}${NC}  SSL: $( [[ $USE_SSL -eq 1 ]] && echo 'да' || echo 'нет' )"
echo -e "  Бот:     ${GREEN}@${BOT_NAME}${NC}"
echo -e "  Панель:  ${GREEN}${PANEL_URL}${NC}"
echo ""
read -rp "  Всё верно? Начать установку? (y/N): " CONFIRM
[[ "$CONFIRM" =~ ^[Yy]$ ]] || { info "Отменено."; exit 0; }

# Все интерактивные вопросы позади — теперь включаем лог
exec > >(tee -a "$LOG_FILE") 2>&1

# ── Подготовка файлов ──────────────────────────────────────────────────────────
step "Шаг 4/6: Подготовка"
SECRET_KEY=$(gen_secret); DB_PASSWORD=$(gen_password); BOT_API_TOKEN=$(gen_secret)
REDIS_PASSWORD=$(gen_password)   # нужен для split-топологии (Redis с паролем)
ok "Секреты сгенерированы"

# ── .env для APP-сервера ───────────────────────────────────────────────────────
ENV_FILE=$(mktemp /tmp/kaza_env_XXXXXX)
{
    echo "# Kaza Shop — конфигурация APP-сервера (создано $(date))"
    echo "ENV=production"
    echo "DB_USER=kaza_user"
    printf 'DB_PASSWORD=%s\n' "$DB_PASSWORD"
    # В split-топологии DB_HOST указывает на DATA-сервер, иначе — локальный контейнер
    if [[ "$TOPOLOGY" == "split" ]]; then
        printf 'DB_HOST=%s\n' "$DATA_SERVER_IP"
    else
        echo "DB_HOST=db"
    fi
    echo "DB_PORT=5432"; echo "DB_NAME=kaza_shop"
    printf 'SECRET_KEY=%s\n'      "$SECRET_KEY"
    printf 'ADMIN_PASSWORD=%s\n'  "$ADMIN_PASSWORD"
    printf 'ADMIN_TG_ID=%s\n'     "$ADMIN_TG_ID"
    printf 'BOT_TOKEN=%s\n'       "$BOT_TOKEN"
    printf 'BOT_API_TOKEN=%s\n'   "$BOT_API_TOKEN"
    printf 'DOMAIN=%s\n'          "$DOMAIN"
    if [[ $USE_SSL -eq 1 ]]; then
        printf 'CORS_ORIGINS=https://%s\n' "$DOMAIN"
    else
        printf 'CORS_ORIGINS=http://%s\n' "$DOMAIN"
    fi
    printf 'ALERT_BOT_TOKEN=%s\n' "$BOT_TOKEN"
    printf 'ALERT_CHAT_ID=%s\n'   "$ADMIN_TG_ID"
    if [[ "$TOPOLOGY" == "split" ]]; then
        # Redis на DATA-сервере — с паролем
        printf 'REDIS_URL=redis://:%s@%s:6379/0\n' "$REDIS_PASSWORD" "$DATA_SERVER_IP"
        printf 'REDIS_PASSWORD=%s\n' "$REDIS_PASSWORD"
    else
        echo "REDIS_URL=redis://redis:6379/0"
    fi
    echo "BACKUP_KEEP_DAYS=14"; echo "LOG_LEVEL=INFO"
    echo "UPDATE_CHANNEL=git"
    echo "UPDATE_BRANCH=main"
    echo "UPDATE_ARCHIVE_URL="
    # Флаг топологии (используется скриптами обновления)
    printf 'KAZA_TOPOLOGY=%s\n' "$TOPOLOGY"
} > "$ENV_FILE"
ok ".env APP-сервера подготовлен"

# ── .env для DATA-сервера (только для split) ───────────────────────────────────
DATA_ENV_FILE=""
if [[ "$TOPOLOGY" == "split" ]]; then
    DATA_ENV_FILE=$(mktemp /tmp/kaza_data_env_XXXXXX)
    {
        echo "# Kaza Shop — конфигурация DATA-сервера (создано $(date))"
        echo "DB_USER=kaza_user"
        printf 'DB_PASSWORD=%s\n' "$DB_PASSWORD"
        echo "DB_NAME=kaza_shop"
        printf 'REDIS_PASSWORD=%s\n' "$REDIS_PASSWORD"
        printf 'APP_SERVER_IP=%s\n' "$SERVER_IP"
    } > "$DATA_ENV_FILE"
    ok ".env DATA-сервера подготовлен"
fi

# Создаём архив проекта
ARCHIVE_DIR_NAME="$(basename "$SCRIPT_DIR")"
TEMP_DIR=$(mktemp -d)
TEMP_ARCHIVE="${TEMP_DIR}/kaza_deploy.tar.gz"
COPYFILE_DISABLE=1 tar --exclude='._*' --exclude='.DS_Store' -czf "$TEMP_ARCHIVE" \
    --exclude='.env' --exclude='.env.example' --exclude='media' --exclude='data' \
    --exclude='logs' --exclude='backups' --exclude='*.pyc' \
    --exclude='__pycache__' --exclude='.git' --exclude='node_modules' \
    -C "$(dirname "$SCRIPT_DIR")" "$ARCHIVE_DIR_NAME" 2>/dev/null
ok "Архив создан: $(du -sh "$TEMP_ARCHIVE" | cut -f1)"

# Создаём скрипт удалённой установки
REMOTE_SCRIPT=$(mktemp /tmp/kaza_remote_XXXXXX.sh)

# Часть 1: переменные (подставляются локально)
cat > "$REMOTE_SCRIPT" << HEADER_EOF
#!/bin/bash
set -euo pipefail
INSTALL_DIR="/opt/kaza_shop"
DOMAIN="${DOMAIN}"
SSL_EMAIL="${SSL_EMAIL}"
USE_SSL="${USE_SSL}"
BOT_NAME="${BOT_NAME}"
BOT_TOKEN="${BOT_TOKEN}"
ADMIN_TG_ID="${ADMIN_TG_ID}"
ARCHIVE_DIR_NAME="${ARCHIVE_DIR_NAME}"
HEADER_EOF

# Часть 2: логика установки (переменные раскрываются на сервере)
cat >> "$REMOTE_SCRIPT" << 'BODY_EOF'
# Цвета
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓${NC} $*"; }
warn() { echo -e "${YELLOW}⚠${NC}  $*"; }
info() { echo -e "${BLUE}→${NC} $*"; }
err()  { echo -e "${RED}✗${NC} $*"; exit 1; }

echo ""
echo -e "${BOLD}═══ Kaza Shop: установка на сервере ═══${NC}"

# Ресурсы
RAM_MB=$(free -m | awk '/^Mem:/{print $2}')
DISK_GB=$(df -BG / | awk 'NR==2{gsub("G",""); print $4}')
[[ "$RAM_MB" -lt 768 ]] && warn "RAM: ${RAM_MB} MB (рекомендуется 1 GB+)"
[[ "$DISK_GB" -lt 5  ]] && warn "Диск: ${DISK_GB} GB (рекомендуется 10 GB+)"
ok "Ресурсы: RAM ${RAM_MB} MB, диск ${DISK_GB} GB"

# Docker
if ! command -v docker &>/dev/null; then
    info "Устанавливаем Docker..."
    curl -fsSL https://get.docker.com | sh || {
        warn "get.docker.com недоступен, пробуем apt..."
        apt-get update && apt-get install -y docker.io docker-compose-plugin
    }
    systemctl enable --now docker
    ok "Docker установлен"
else ok "Docker: $(docker --version | cut -d' ' -f3 | tr -d ',')"; fi
docker compose version &>/dev/null 2>&1 || apt-get install -y docker-compose-plugin
ok "Docker Compose готов"

# Зеркала Docker Hub (резервные источники образов на случай медленного доступа)
info "Настраиваем зеркала Docker Hub..."
mkdir -p /etc/docker
cat > /etc/docker/daemon.json << 'DOCKERCFG'
{
  "registry-mirrors": [
    "https://huecker.io",
    "https://dockerhub.timeweb.cloud",
    "https://mirror.gcr.io"
  ],
  "dns": ["8.8.8.8", "1.1.1.1"]
}
DOCKERCFG
systemctl restart docker
ok "Зеркала Docker Hub настроены"

# Nginx + certbot
info "Устанавливаем nginx и certbot..."
apt-get update
apt-get install -y --no-install-recommends nginx certbot python3-certbot-nginx curl unzip ufw
ok "nginx и certbot готовы"

# Firewall
if command -v ufw &>/dev/null; then
    ufw allow OpenSSH   >/dev/null 2>&1 || true
    ufw allow 80/tcp    >/dev/null 2>&1 || true
    ufw allow 443/tcp   >/dev/null 2>&1 || true
    ufw --force enable  >/dev/null 2>&1 || true
    ok "Firewall настроен (SSH + 80 + 443)"
fi

# Распаковка архива
info "Распаковываем файлы..."
mkdir -p "$INSTALL_DIR"
tar -xzf /tmp/kaza_deploy.tar.gz -C /tmp/
cp -r "/tmp/${ARCHIVE_DIR_NAME}/." "$INSTALL_DIR/"
rm -rf "/tmp/${ARCHIVE_DIR_NAME}" /tmp/kaza_deploy.tar.gz
mkdir -p "${INSTALL_DIR}/media" "${INSTALL_DIR}/data" "${INSTALL_DIR}/logs" "${INSTALL_DIR}/backups"
chown -R 1000:1000 "${INSTALL_DIR}/data" "${INSTALL_DIR}/media" "${INSTALL_DIR}/logs"
chmod 755 "${INSTALL_DIR}/data" "${INSTALL_DIR}/media" "${INSTALL_DIR}/logs"
chmod 755 "${INSTALL_DIR}/backup.sh" "${INSTALL_DIR}/healthcheck.sh" \
           "${INSTALL_DIR}/update.sh"  "${INSTALL_DIR}/restore.sh" \
           "${INSTALL_DIR}/deploy.sh" 2>/dev/null || true
ok "Файлы установлены → $INSTALL_DIR"

# .env — сохраняем старый DB_PASSWORD если том PostgreSQL уже существует
EXISTING_REMOTE_ENV="${INSTALL_DIR}/.env"
REMOTE_VOLUME="kaza_shop_postgres_data"
if [[ -f "$EXISTING_REMOTE_ENV" ]] && docker volume ls -q | grep -qx "$REMOTE_VOLUME"; then
    OLD_DB_PASS_R=$(grep '^DB_PASSWORD=' "$EXISTING_REMOTE_ENV" | cut -d= -f2-)
    OLD_SECRET_R=$(grep '^SECRET_KEY='   "$EXISTING_REMOTE_ENV" | cut -d= -f2-)
    if [[ -n "$OLD_DB_PASS_R" && -n "$OLD_SECRET_R" ]]; then
        # Заменяем в новом .env старые пароль и ключ
        sed -i "s#^DB_PASSWORD=.*#DB_PASSWORD=${OLD_DB_PASS_R}#" /tmp/kaza_env
        sed -i "s#^SECRET_KEY=.*#SECRET_KEY=${OLD_SECRET_R}#"    /tmp/kaza_env
        ok "Существующий PostgreSQL-том найден — переиспользуем пароль БД"
    fi
fi
cp /tmp/kaza_env "${INSTALL_DIR}/.env"
chmod 600 "${INSTALL_DIR}/.env"
rm -f /tmp/kaza_env
ok ".env установлен"

# Nginx (временный конфиг для certbot challenge)
printf 'server {\n    listen 80;\n    server_name %s;\n    location / { return 200 '"'"'ok'"'"'; add_header Content-Type text/plain; }\n}\n' \
    "$DOMAIN" > /etc/nginx/sites-available/kaza_shop
ln -sf /etc/nginx/sites-available/kaza_shop /etc/nginx/sites-enabled/kaza_shop
rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true
nginx -t 2>/dev/null && systemctl reload nginx

# SSL
SSL_FAILED=0
if [[ "$USE_SSL" == "1" ]]; then
    info "Получаем SSL-сертификат..."
    if certbot certonly --nginx --non-interactive --agree-tos \
       --email "$SSL_EMAIL" -d "$DOMAIN"; then
        ok "SSL получен"
        cp "${INSTALL_DIR}/nginx/kaza_shop.conf" /etc/nginx/sites-available/kaza_shop
        sed -i "s/YOUR_DOMAIN/${DOMAIN}/g" /etc/nginx/sites-available/kaza_shop
        nginx -t 2>/dev/null && systemctl reload nginx && ok "Nginx настроен с SSL"
        (crontab -l 2>/dev/null || echo "") | grep -v certbot > /tmp/crt
        echo "0 3 * * * certbot renew --quiet --post-hook 'systemctl reload nginx'" >> /tmp/crt
        crontab /tmp/crt && rm -f /tmp/crt
    else
        SSL_FAILED=1
        warn "SSL не получен — DNS ещё не обновился?"
        warn "Настройте позже: certbot --nginx -d ${DOMAIN}"
        cp "${INSTALL_DIR}/nginx/kaza_shop_nossl.conf" /etc/nginx/sites-available/kaza_shop
        nginx -t 2>/dev/null && systemctl reload nginx && ok "Nginx настроен (без SSL, порт 80)"
    fi
else
    # Нет SSL — настраиваем nginx с прокси-конфигом для IP-доступа
    cp "${INSTALL_DIR}/nginx/kaza_shop_nossl.conf" /etc/nginx/sites-available/kaza_shop
    nginx -t 2>/dev/null && systemctl reload nginx
    ok "Nginx настроен (без SSL, порт 80)"
fi

# Docker build + запуск
cd "$INSTALL_DIR"
info "Проверяем файлы миграций Alembic..."
python3 - <<'PY'
from pathlib import Path
import sys

base = Path("/opt/kaza_shop/alembic/versions")
files = sorted(
    p for p in base.glob("*.py")
    if not p.name.startswith("._")
)
if not files:
    print("ERROR: alembic/versions пуст")
    sys.exit(1)

for p in files:
    b = p.read_bytes()
    if b"\\x00" in b:
        print(f"ERROR: null bytes detected in {p}")
        sys.exit(1)
    try:
        compile(b.decode("utf-8"), str(p), "exec")
    except Exception as e:
        print(f"ERROR: invalid migration file {p}: {e}")
        sys.exit(1)
print("Alembic migrations: OK")
PY
ok "Миграции Alembic валидны"
echo ""
echo -e "${YELLOW}  ⏳ Скачиваем и собираем образы — это займёт 5–15 минут.${NC}"
echo -e "${YELLOW}  Пожалуйста, не прерывайте процесс.${NC}"
echo ""
BUILD_OK=0
for attempt in 1 2 3; do
    [[ $attempt -gt 1 ]] && warn "Повтор попытки ${attempt}/3..." && sleep 10
    if docker compose -f docker-compose.prod.yml build 2>&1; then
        BUILD_OK=1; break
    fi
done
if [[ $BUILD_OK -eq 0 ]]; then
    warn "Сборка образов не удалась после 3 попыток."
    warn "Запустите вручную: cd /opt/kaza_shop && docker compose -f docker-compose.prod.yml build"
else
    ok "Образы собраны"
    docker compose -f docker-compose.prod.yml up -d
    ok "Сервисы запущены"
fi

# Ожидание API
info "Ожидаем готовности API (до 2 мин)..."
API_READY=0
for i in $(seq 1 24); do
    sleep 5
    if curl -sf "http://localhost:8000/health" &>/dev/null; then API_READY=1; ok "API отвечает"; break; fi
    echo -n "."
done
echo ""
if [[ $API_READY -eq 0 ]]; then
    warn "API не ответил в течение 2 минут. Установка продолжается."
    warn "Проверьте позже: docker compose -f docker-compose.prod.yml logs app"
fi

# Проверка авторизации администратора
if [[ $API_READY -eq 1 ]]; then
    info "Проверяем авторизацию администратора..."
    sleep 2
    AUTH_TEST=$(curl -sf -X POST "http://localhost:8000/auth/login" \
        -H "Content-Type: application/json" \
        -d "{\"login\":\"admin\",\"password\":\"${ADMIN_PASSWORD}\"}" 2>/dev/null || echo '{}')
    if echo "$AUTH_TEST" | grep -q '"token"'; then
        ok "Администратор готов (логин: admin)"
    else
        warn "Не удалось проверить авторизацию. Войдите в панель с паролем, который вы задали."
    fi
fi

# Systemd
cat > /etc/systemd/system/kaza_shop.service << __SYSTEMD__
[Unit]
Description=Kaza Shop Telegram Store
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/kaza_shop
ExecStart=/usr/bin/docker compose -f docker-compose.prod.yml up -d
ExecStop=/usr/bin/docker compose -f docker-compose.prod.yml down
TimeoutStartSec=120

[Install]
WantedBy=multi-user.target
__SYSTEMD__
systemctl daemon-reload
systemctl enable kaza_shop.service
ok "Автозапуск при перезагрузке настроен"

# Cron
(crontab -l 2>/dev/null | grep -v kaza_shop) > /tmp/ctab || true
printf '0 2 * * *   bash %s/backup.sh           >> %s/logs/backup.log        2>&1 # kaza_shop\n' "$INSTALL_DIR" "$INSTALL_DIR" >> /tmp/ctab
printf '0 * * * *   bash %s/backup.sh --hourly  >> %s/logs/backup_hourly.log 2>&1 # kaza_shop\n' "$INSTALL_DIR" "$INSTALL_DIR" >> /tmp/ctab
printf '*/5 * * * * bash %s/healthcheck.sh       >> %s/logs/monitor.log       2>&1 # kaza_shop\n' "$INSTALL_DIR" "$INSTALL_DIR" >> /tmp/ctab
crontab /tmp/ctab && rm -f /tmp/ctab
ok "Cron: ежедневный бэкап в 02:00 (в Telegram), почасовой локально, мониторинг каждые 5 мин"

echo ""
echo -e "${GREEN}═══ Установка на сервере завершена ═══${NC}"
BODY_EOF

ok "Скрипт установки APP-сервера подготовлен"

# ── Скрипт установки DATA-сервера (только для split) ──────────────────────────
DATA_REMOTE_SCRIPT=""
if [[ "$TOPOLOGY" == "split" ]]; then
    DATA_REMOTE_SCRIPT=$(mktemp /tmp/kaza_data_setup_XXXXXX.sh)

    # Часть 1: переменные
    cat > "$DATA_REMOTE_SCRIPT" << DATA_HEADER_EOF
#!/bin/bash
set -euo pipefail
DATA_DIR="/opt/kaza_data"
APP_SERVER_IP="${SERVER_IP}"
DATA_HEADER_EOF

    # Часть 2: логика DATA-сервера
    cat >> "$DATA_REMOTE_SCRIPT" << 'DATA_BODY_EOF'
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓${NC} $*"; }
warn() { echo -e "${YELLOW}⚠${NC}  $*"; }
info() { echo -e "${BLUE}→${NC} $*"; }

echo ""
echo -e "${BOLD}═══ Kaza Shop DATA-сервер: установка ═══${NC}"

# Docker
if ! command -v docker &>/dev/null; then
    info "Устанавливаем Docker..."
    curl -fsSL https://get.docker.com | sh || apt-get update && apt-get install -y docker.io docker-compose-plugin
    systemctl enable --now docker
    ok "Docker установлен"
else ok "Docker: $(docker --version | cut -d' ' -f3 | tr -d ',')"; fi
docker compose version &>/dev/null 2>&1 || apt-get install -y -q docker-compose-plugin
ok "Docker Compose готов"

# Зеркала Docker Hub
mkdir -p /etc/docker
cat > /etc/docker/daemon.json << 'DOCKERCFG'
{
  "registry-mirrors": ["https://huecker.io","https://dockerhub.timeweb.cloud"],
  "dns": ["8.8.8.8","1.1.1.1"]
}
DOCKERCFG
systemctl restart docker
ok "Зеркала Docker Hub настроены"

# Директории
mkdir -p "${DATA_DIR}/deploy/postgres"
chown -R 1000:1000 "${DATA_DIR}" 2>/dev/null || true
ok "Директории созданы: ${DATA_DIR}"

# .env
cp /tmp/kaza_data_env "${DATA_DIR}/.env"
chmod 600 "${DATA_DIR}/.env"
rm -f /tmp/kaza_data_env
ok ".env DATA-сервера установлен"

# docker-compose.data-only.yml
cp /tmp/kaza_data_compose "${DATA_DIR}/docker-compose.data-only.yml"
rm -f /tmp/kaza_data_compose

# pg_hba_remote.conf
cp /tmp/kaza_pg_hba "${DATA_DIR}/deploy/postgres/pg_hba_remote.conf" 2>/dev/null || true
rm -f /tmp/kaza_pg_hba

ok "Файлы конфигурации DATA-сервера установлены"

# Firewall — открываем 5432 и 6379 только для APP-сервера
if command -v ufw &>/dev/null || apt-get install -y -q ufw 2>/dev/null; then
    ufw allow OpenSSH >/dev/null 2>&1 || true
    ufw allow from "${APP_SERVER_IP}" to any port 5432 comment 'Kaza APP → PostgreSQL' >/dev/null 2>&1 || true
    ufw allow from "${APP_SERVER_IP}" to any port 6379 comment 'Kaza APP → Redis' >/dev/null 2>&1 || true
    ufw --force enable >/dev/null 2>&1 || true
    ok "Firewall: 5432 и 6379 открыты только для APP-сервера (${APP_SERVER_IP})"
else
    warn "ufw не найден — настройте firewall вручную: порты 5432, 6379 только для ${APP_SERVER_IP}"
fi

# Запускаем PostgreSQL + Redis
cd "${DATA_DIR}"
info "Запускаем PostgreSQL и Redis..."
docker compose -f docker-compose.data-only.yml up -d
ok "PostgreSQL и Redis запущены"

# Ожидаем готовности PostgreSQL
info "Ожидаем готовности PostgreSQL (до 60 сек)..."
DB_USER=$(grep '^DB_USER=' "${DATA_DIR}/.env" | cut -d= -f2-)
DB_NAME=$(grep '^DB_NAME=' "${DATA_DIR}/.env" | cut -d= -f2-)
for i in $(seq 1 12); do
    sleep 5
    if docker compose -f docker-compose.data-only.yml exec -T db \
            pg_isready -U "$DB_USER" -d "$DB_NAME" &>/dev/null; then
        ok "PostgreSQL готов"
        break
    fi
    echo -n "."
done

echo ""
echo -e "${GREEN}═══ DATA-сервер настроен ═══${NC}"
echo -e "  PostgreSQL :5432"
echo -e "  Redis      :6379"
DATA_BODY_EOF

    ok "Скрипт установки DATA-сервера подготовлен"
fi

# ── Загрузка файлов на сервер ──────────────────────────────────────────────────
step "Шаг 5/6: Загрузка на серверы"

# --- DATA-сервер (только split) ---
if [[ "$TOPOLOGY" == "split" ]]; then
    info "Загружаем конфигурацию на DATA-сервер (${DATA_SERVER_IP})..."
    run_data_scp "$DATA_ENV_FILE" "${DATA_SERVER_USER}@${DATA_SERVER_IP}:/tmp/kaza_data_env"
    ok "DATA .env загружен"
    run_data_scp "${SCRIPT_DIR}/docker-compose.data-only.yml" \
        "${DATA_SERVER_USER}@${DATA_SERVER_IP}:/tmp/kaza_data_compose" 2>/dev/null \
        || warn "docker-compose.data-only.yml не найден рядом — скопируйте на DATA-сервер вручную"
    run_data_scp "${SCRIPT_DIR}/deploy/postgres/pg_hba_remote.conf" \
        "${DATA_SERVER_USER}@${DATA_SERVER_IP}:/tmp/kaza_pg_hba" 2>/dev/null || true
    run_data_scp "$DATA_REMOTE_SCRIPT" "${DATA_SERVER_USER}@${DATA_SERVER_IP}:/tmp/kaza_data_setup.sh"
    ok "Скрипт DATA-сервера загружен"
fi

# --- APP-сервер ---
info "Загружаем архив проекта на APP-сервер (${SERVER_IP})..."
run_scp "$TEMP_ARCHIVE" "${SSH_USER}@${SERVER_IP}:/tmp/kaza_deploy.tar.gz"
ok "Архив загружен"

info "Загружаем .env на APP-сервер..."
run_scp "$ENV_FILE" "${SSH_USER}@${SERVER_IP}:/tmp/kaza_env"
ok ".env загружен"

info "Загружаем скрипт установки APP-сервера..."
run_scp "$REMOTE_SCRIPT" "${SSH_USER}@${SERVER_IP}:/tmp/kaza_setup.sh"
ok "Скрипт загружен"

# Очистка временных файлов
rm -f "$ENV_FILE" "$REMOTE_SCRIPT" "$DATA_REMOTE_SCRIPT" "$DATA_ENV_FILE"
rm -rf "$TEMP_DIR"

# ── Установка на серверах ──────────────────────────────────────────────────────
step "Шаг 6/6: Установка на серверах"
echo ""

# Сначала DATA-сервер (в split-топологии APP зависит от него)
if [[ "$TOPOLOGY" == "split" ]]; then
    info "Устанавливаем DATA-сервер (${DATA_SERVER_IP})..."
    echo ""
    if [[ "$DATA_AUTH_METHOD" == "password" ]]; then
        DATA_LONG_OPTS=(-p "$DATA_SERVER_PORT" -o StrictHostKeyChecking=no
                        -o ConnectTimeout=10 -o ServerAliveInterval=30 -o ServerAliveCountMax=60)
        SSHPASS="$DATA_SERVER_PASS" sshpass -e ssh "${DATA_LONG_OPTS[@]}" \
            "${DATA_SERVER_USER}@${DATA_SERVER_IP}" "bash /tmp/kaza_data_setup.sh" || true
    else
        DATA_LONG_OPTS=(-p "$DATA_SERVER_PORT" -o StrictHostKeyChecking=no -i "$DATA_SERVER_KEY"
                        -o BatchMode=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=60)
        ssh "${DATA_LONG_OPTS[@]}" "${DATA_SERVER_USER}@${DATA_SERVER_IP}" \
            "bash /tmp/kaza_data_setup.sh" || true
    fi
    run_data_ssh "rm -f /tmp/kaza_data_setup.sh" 2>/dev/null || true

    # Ждём доступности PostgreSQL с APP-сервера
    info "Проверяем доступность PostgreSQL с APP-сервера..."
    sleep 5
    set +e
    PG_CHECK=$(run_ssh "nc -z -w5 ${DATA_SERVER_IP} 5432 2>/dev/null && echo ok || echo fail")
    set -e
    if [[ "$PG_CHECK" == "ok" ]]; then
        ok "PostgreSQL на DATA-сервере доступен с APP-сервера"
    else
        warn "PostgreSQL не доступен с APP-сервера. Проверьте firewall DATA-сервера."
        warn "Ожидаемая команда: ufw allow from ${SERVER_IP} to any port 5432"
    fi
    echo ""
fi

# Теперь APP-сервер (используем app-only compose в split-режиме)
# Подставляем правильный docker-compose файл в REMOTE_SCRIPT уже на сервере
if [[ "$TOPOLOGY" == "split" ]]; then
    info "Устанавливаем APP-сервер (${SERVER_IP}) — приложение без локальной БД..."
    # Патчим удалённый скрипт: заменяем docker-compose.prod.yml на docker-compose.app-only.yml
    run_ssh "sed -i 's/docker-compose\.prod\.yml/docker-compose.app-only.yml/g' /tmp/kaza_setup.sh" 2>/dev/null || true
else
    info "Устанавливаем сервер (${SERVER_IP})..."
fi
echo ""
run_ssh_long "bash /tmp/kaza_setup.sh" || true
run_ssh "rm -f /tmp/kaza_setup.sh" 2>/dev/null || true

# Проверяем реальный результат — SSH может вернуть ненулевой код из-за разрыва
# соединения во время долгой сборки, даже если установка прошла успешно
info "Проверяем результат установки..."
sleep 5
INSTALL_OK=0
if run_ssh "test -f /opt/kaza_shop/docker-compose.prod.yml" 2>/dev/null; then
    RUNNING=$(run_ssh "docker compose -f /opt/kaza_shop/docker-compose.prod.yml ps --status running --quiet 2>/dev/null | wc -l" 2>/dev/null || echo "0")
    [[ "$RUNNING" -ge 3 ]] && INSTALL_OK=1
fi

if [[ $INSTALL_OK -eq 0 ]]; then
    echo ""
    echo -e "${RED}✗ Установка не завершена — сервисы не запущены.${NC}"
    echo -e "  Проверьте вывод выше и логи на сервере:"
    echo -e "    ssh ${SSH_USER}@${SERVER_IP}"
    echo -e "    docker compose -f /opt/kaza_shop/docker-compose.prod.yml logs --tail=50"
    exit 1
fi

# ── Итог ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}════════════════════════════════════════${NC}"
echo -e "${BOLD}${GREEN}  ✓ Установка завершена!${NC}"
if [[ "$TOPOLOGY" == "split" ]]; then
    echo -e "${BOLD}${CYAN}  Топология: два сервера (152-ФЗ)${NC}"
fi
echo -e "${BOLD}${GREEN}════════════════════════════════════════${NC}"
echo ""
echo -e "  🌐  Панель: ${CYAN}${PANEL_URL}${NC}   логин ${GREEN}admin${NC}"
echo -e "  🤖  Бот:    ${CYAN}@${BOT_NAME}${NC}"
echo ""
if [[ "$TOPOLOGY" == "split" ]]; then
    APP_COMPOSE_FILE="docker-compose.app-only.yml"
    echo -e "  ${BOLD}Серверы:${NC}"
    echo -e "  APP-сервер (приложение): ${GREEN}${SERVER_IP}${NC}"
    echo -e "  DATA-сервер (данные):    ${YELLOW}${DATA_SERVER_IP}${NC}  ← персональные данные в России"
    echo ""
    echo -e "  ${BOLD}Управление APP-сервером:${NC}"
    printf "  %-14s %s\n" "Статус:"   "cd /opt/kaza_shop && docker compose -f ${APP_COMPOSE_FILE} ps"
    printf "  %-14s %s\n" "Логи:"     "cd /opt/kaza_shop && docker compose -f ${APP_COMPOSE_FILE} logs -f"
    echo ""
    echo -e "  ${BOLD}Управление DATA-сервером:${NC}"
    printf "  %-14s %s\n" "Статус:"   "cd /opt/kaza_data && docker compose -f docker-compose.data-only.yml ps"
    printf "  %-14s %s\n" "Логи PG:"  "cd /opt/kaza_data && docker compose -f docker-compose.data-only.yml logs db"
    echo ""
    echo -e "  ${BOLD}Перенос DATA-сервера:${NC}"
    echo -e "  bash scripts/migrate_data_server.sh"
else
    APP_COMPOSE_FILE="docker-compose.prod.yml"
    echo -e "  ${BOLD}Управление (по SSH):${NC}"
    printf "  %-14s %s\n" "Статус:"   "cd /opt/kaza_shop && docker compose -f ${APP_COMPOSE_FILE} ps"
    printf "  %-14s %s\n" "Логи:"     "cd /opt/kaza_shop && docker compose -f ${APP_COMPOSE_FILE} logs -f"
    printf "  %-14s %s\n" "Обновить:" "bash /opt/kaza_shop/update.sh"
    printf "  %-14s %s\n" "Бэкап:"    "bash /opt/kaza_shop/backup.sh"
fi
echo ""
echo -e "  Лог: ${LOG_FILE}"
echo ""

# Telegram-уведомление
TGTEXT="🎉 <b>Kaza Shop установлен!</b>

🌐 Панель: ${PANEL_URL}
🤖 Бот: @${BOT_NAME}
"
if [[ "$TOPOLOGY" == "split" ]]; then
    TGTEXT+="
🗄 DATA-сервер (152-ФЗ): ${DATA_SERVER_IP}
🖥 APP-сервер: ${SERVER_IP}
"
fi
TGTEXT+="
Логин: <code>admin</code>
Пароль: тот что вы задали"

curl -sf "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
    -d "chat_id=${ADMIN_TG_ID}" -d "parse_mode=HTML" \
    --data-urlencode "text=${TGTEXT}" >/dev/null 2>&1 || true
