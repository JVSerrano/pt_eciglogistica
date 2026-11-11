# Imagen base: PHP 8.3 con el servidor Apache incluido
FROM php:8.3-apache

# Instala Python 3 y la librería de PostgreSQL necesaria para compilar pdo_pgsql
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 libpq-dev \
    && docker-php-ext-install pdo_pgsql \
    && rm -rf /var/lib/apt/lists/*
