# SPEC 01 — Preparar el repositorio y el entorno Docker

> **Estado:** Aprobado
> **Depende de:** —
> **Fecha:** 2026-11-09
> **Objetivo:** Dejar el repositorio con su estructura, `.env.example` y un `docker-compose.yml` que arranca PostgreSQL y PHP/Python, comprobado con `health.php`.

## Por qué existe este spec

Es la base de las etapas 1 a 5. Si Docker y las variables de entorno quedan bien ahora, las siguientes etapas solo añaden archivos dentro de una estructura ya fija.

## Alcance

**Dentro:**

- Estructura de carpetas por pieza (`db/`, `classifier/`, `docker/php/`, `public/`, `specs/`).
- `.env.example` con todas las variables del proyecto y valores falsos.
- `docker/php/Dockerfile`: PHP 8.3 + Apache + extensión `pdo_pgsql` + Python 3.
- `docker-compose.yml` con dos servicios: `db` (PostgreSQL) y `web` (PHP/Apache/Python).
- `public/health.php`: devuelve JSON con versión de PHP, versión de Python y estado de la conexión a la BD.
- Comprobar que `.gitignore` cubre `.env`.
- Commits por paso y push al terminar.

**Fuera (otros specs):**

- Tablas, `init.sql` y datos de ejemplo (SPEC 02, Etapa 1).
- Clasificador Python y librería de Gemini (Etapa 2).
- API `consultations.php` (Etapa 3).
- Frontend `index.html` / `app.js` (Etapa 4).
- README (Etapa 5).

## Estructura y datos

Estructura al terminar este spec:

    PT_Eciglogistica/
    ├── .env.example
    ├── .gitignore
    ├── docker-compose.yml
    ├── docker/php/Dockerfile
    ├── public/health.php
    └── specs/01-preparar-repositorio.md

Las carpetas `db/` y `classifier/` se crean en sus etapas (Git no guarda carpetas vacías).

Variables de `.env.example`:

    POSTGRES_DB=consultations_db
    POSTGRES_USER=app_user
    POSTGRES_PASSWORD=change_me
    GEMINI_API_KEY=your_api_key_here
    GEMINI_MODEL=gemini-model-name
    CLASSIFIER_MODE=keywords   # keywords | gemini

Servicios de `docker-compose.yml`:

| Servicio | Imagen | Puerto en el PC | Notas |
|----------|--------|-----------------|-------|
| `db` | `postgres:16` | `5433` → 5432 | Volumen con nombre `pgdata`. Lee `POSTGRES_*` de `.env`. Healthcheck con `pg_isready`. |
| `web` | build `docker/php/Dockerfile` | `8080` → 80 | Monta `./public` en `/var/www/html`. Lee todo `.env`. `depends_on: db` (condición healthy). Conecta a la BD con host `db`, puerto 5432. |

Respuesta de `health.php` (ejemplo):

    {"php": "8.3.x", "python": "Python 3.x.x", "database": "ok"}

Si la BD no conecta: `"database": "error"` y código HTTP 500. Nunca muestra contraseñas ni el mensaje interno de PDO.

## Plan de implementación

1. Crear `.env.example` y comprobar que `.env` está en `.gitignore`. Copiar a `.env` local. Commit.
2. Crear `docker-compose.yml` solo con el servicio `db`. Prueba: `docker compose up -d db` y TablePlus conecta a `localhost:5433`. Commit.
3. Crear `docker/php/Dockerfile` y añadir el servicio `web` al compose. Prueba: `docker compose up -d --build` y `docker compose exec web python3 --version` responde. Commit.
4. Crear `public/health.php`. Prueba: abrir `http://localhost:8080/health.php`. Commit.
5. Guardar este spec como `Implementado`. Revisar `git status` (sin `.env`). Push.

## Criterios de aceptación

- [ ] `docker compose up -d --build` termina sin errores y `docker compose ps` muestra `db` y `web` en marcha.
- [ ] TablePlus conecta a `localhost:5433` con los datos de `.env`.
- [ ] `http://localhost:8080/health.php` devuelve JSON con `php`, `python` y `"database": "ok"`.
- [ ] Con `db` parado, `health.php` devuelve `"database": "error"` y HTTP 500, sin mostrar contraseñas.
- [ ] `git ls-files` no incluye `.env` ni `PLAN_PRIVADO.md`.
- [ ] `.env.example` no contiene ninguna clave real.
- [ ] Hay un commit por paso y `origin` tiene los cambios.
- [ ] El código está en inglés básico y los comentarios en español.

## Decisiones

- **Sí:** estructura por pieza. Fácil de explicar en la entrevista.
- **No:** todo bajo `src/`. Añade un nivel sin aportar nada.
- **Sí:** los dos servicios arrancan ya en la Etapa 0. Las etapas siguientes no tocan Docker salvo para añadir librerías.
- **Sí:** puerto `5433` para la BD. Evita choque con un PostgreSQL local en 5432.
- **Sí:** `.env.example` con todas las variables desde el principio, incluidas las de Gemini y `CLASSIFIER_MODE`.
- **Sí:** `health.php` como prueba. Comprueba PHP, Python y BD a la vez. Se puede borrar en la Etapa 5.
- **No:** `index.html` de prueba. Solo probaría Apache.
- **Sí:** `PLAN_PRIVADO.md` en `.git/info/exclude`, no en `.gitignore`. Así no aparece su nombre en el repo público.
- **Sí:** un spec por etapa, escrito al empezar cada una.
- **Sí:** specs en español.

## Riesgos

| Riesgo | Mitigación |
|--------|------------|
| Se sube `.env` por error | Está en `.gitignore`. Antes del push se revisa `git ls-files`. |
| Puerto 8080 o 5433 ocupado | Cambiar el número en `docker-compose.yml`; documentarlo en el README. |
| `web` arranca antes que la BD | `depends_on` con `condition: service_healthy`. |
| `init.sql` (Etapa 1) no se ejecuta porque el volumen ya existe | Documentar en SPEC 02: `docker compose down -v` para empezar de cero. |

## Lo que **no** está en este spec

- Tablas y datos de ejemplo.
- Clasificador y Gemini.
- API y frontend.
- README.

Cada uno va en su propio spec.
