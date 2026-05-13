# Этап 1: сборка
FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
# Для production: не задавать VITE_API_URL — используются относительные URL через nginx
# Для local dev: передать через build arg: --build-arg VITE_API_URL=http://localhost:8000
ARG VITE_API_URL=""
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# Этап 2: раздача статики через nginx (мгновенная загрузка)
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
