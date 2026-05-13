#!/usr/bin/env bash
# Настройка канала обновлений для update.sh
# Использование: sudo bash configure-updates.sh
set -euo pipefail

INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${INSTALL_DIR}/.env"

[[ "$EUID" -ne 0 ]] && { echo "Запустите от root: sudo bash configure-updates.sh"; exit 1; }
[[ -f "$ENV_FILE" ]] || { echo ".env не найден: ${ENV_FILE}"; exit 1; }

upsert_env() {
    local key="$1"
    local val="$2"
    if grep -q "^${key}=" "$ENV_FILE"; then
        sed -i.bak "s#^${key}=.*#${key}=${val}#g" "$ENV_FILE"
    else
        echo "${key}=${val}" >> "$ENV_FILE"
    fi
}

echo "Kaza Shop — настройка обновлений"
echo "1) Git-канал (origin/main)"
echo "2) Архив по URL (release tar.gz)"
read -rp "Выберите режим (1/2): " mode

case "$mode" in
  1)
    read -rp "Ветка (по умолчанию main): " branch
    [[ -z "${branch}" ]] && branch="main"
    upsert_env "UPDATE_CHANNEL" "git"
    upsert_env "UPDATE_BRANCH" "$branch"
    upsert_env "UPDATE_ARCHIVE_URL" ""
    echo "Готово: UPDATE_CHANNEL=git, UPDATE_BRANCH=${branch}"
    ;;
  2)
    read -rp "URL архива обновления (tar.gz): " url
    [[ -z "${url}" ]] && { echo "URL не может быть пустым"; exit 1; }
    upsert_env "UPDATE_CHANNEL" "archive"
    upsert_env "UPDATE_ARCHIVE_URL" "$url"
    upsert_env "UPDATE_BRANCH" "main"
    echo "Готово: UPDATE_CHANNEL=archive, UPDATE_ARCHIVE_URL=${url}"
    ;;
  *)
    echo "Отмена: неверный выбор"
    exit 1
    ;;
esac

chmod 600 "$ENV_FILE" || true
echo "Теперь обновление выполняется одной командой: sudo bash ${INSTALL_DIR}/update.sh"
