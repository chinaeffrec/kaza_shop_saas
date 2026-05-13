#!/bin/bash
# Настройка nginx для kaza_shop.
# Вызывается из установщика один раз после копирования файлов проекта.

set -e

INSTALL_DIR="$(cd "$(dirname "$0")" && pwd)"

# Устанавливаем nginx если не установлен
if ! command -v nginx &>/dev/null; then
    echo "Устанавливаем nginx..."
    apt-get update -qq && apt-get install -y nginx
fi

# Копируем конфиг сайта
cp "$INSTALL_DIR/nginx-site.conf" /etc/nginx/sites-enabled/kaza_shop

# Убираем дефолтный конфиг если мешает
rm -f /etc/nginx/sites-enabled/default

# Проверяем конфиг и перезагружаем
nginx -t && systemctl enable nginx && systemctl reload nginx

echo "nginx настроен успешно"
