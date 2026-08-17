# syntax=docker/dockerfile:1

# Frontend estático do SAS. Não há build step (ES modules servidos crus),
# então a imagem é só nginx + os arquivos.
FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY . /usr/share/nginx/html

EXPOSE 8080
