# syntax=docker/dockerfile:1

# Frontend do SAS: build com Vite, servido por nginx.
#
# Antes desta imagem não havia build step — os ES modules iam crus para o
# nginx. Com React + TypeScript o build passou a existir, e com ele os assets
# ganham hash no nome, que é o que permite cacheá-los como imutáveis
# (ver nginx.conf).

FROM node:22-alpine AS build
WORKDIR /app

# package*.json antes do resto: o `npm ci` só refaz quando as dependências
# mudam, não a cada arquivo de código editado.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

# Imagem unprivileged: a nginx oficial sobe o processo master como root
# (docs/14 §5). Escuta em 8080, porque uid 101 não pode abrir porta < 1024.
FROM nginxinc/nginx-unprivileged:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080
