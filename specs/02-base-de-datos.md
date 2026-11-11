# SPEC 02 — Base de datos: tablas y datos de ejemplo

> **Estado:** Aprobado 
> **Depende de:** SPEC 01 (Implementado)
> **Fecha:** 2026-11-11
> **Objetivo:** Que PostgreSQL cree solo las 3 tablas y cargue los datos de ejemplo en el primer arranque, y que TablePlus los muestre.

## Por qué existe este spec

La API (Etapa 3) y el clasificador (Etapa 2) necesitan unas tablas fijas. Si el esquema queda bien ahora, las etapas siguientes solo leen y escriben datos.

## Alcance

**Dentro:**

- Carpeta `db/` con el archivo `init.sql`.
- Tablas `departments`, `error_types` y `consultations`, con claves primarias, claves foráneas y restricciones.
- Datos de ejemplo: 3 departamentos, 5 tipos de error, 2 consultas.
- Cambio en `docker-compose.yml`: montar `init.sql` en el servicio `db` para que se ejecute solo.

**Fuera (otros specs):**

- Clasificador Python y Gemini (Etapa 2).
- API `consultations.php` (Etapa 3).
- Frontend (Etapa 4).
- Índices y filtros (Bonus). Con 2 filas no aportan nada.
- Migraciones. Para cambiar el esquema se borra el volumen.

## Estructura y datos

Archivos nuevos o modificados:

    PT_Eciglogistica/
    ├── db/init.sql                  (nuevo)
    ├── docker-compose.yml           (modificado: volumen de init.sql)
    └── specs/02-base-de-datos.md    (nuevo)

Cambio en el servicio `db` de `docker-compose.yml`:

    volumes:
      - pgdata:/var/lib/postgresql/data
      # Se ejecuta solo la primera vez, cuando el volumen está vacío
      - ./db/init.sql:/docker-entrypoint-initdb.d/init.sql:ro

### Tabla `departments`

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `id` | `SERIAL` | clave primaria |
| `name` | `VARCHAR(100)` | `NOT NULL`, `UNIQUE` |

### Tabla `error_types`

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `id` | `SERIAL` | clave primaria |
| `code` | `VARCHAR(50)` | `NOT NULL`, `UNIQUE` |
| `description` | `VARCHAR(255)` | `NOT NULL` |

### Tabla `consultations`

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `id` | `SERIAL` | clave primaria |
| `client_name` | `VARCHAR(100)` | `NOT NULL` |
| `message` | `TEXT` | `NOT NULL` |
| `department_id` | `INTEGER` | FK a `departments(id)`. Permite `NULL` |
| `status` | `VARCHAR(20)` | `NOT NULL`, `DEFAULT 'pending'`, `CHECK` en (`pending`, `classified`, `error`) |
| `error_type_id` | `INTEGER` | FK a `error_types(id)`. Permite `NULL` |
| `created_at` | `TIMESTAMP` | `NOT NULL`, `DEFAULT NOW()` |
| `classified_at` | `TIMESTAMP` | Permite `NULL` |

Regla de coherencia (un `CHECK` a nivel de tabla):

- `pending`: sin departamento ni error.
- `classified`: con departamento y sin error.
- `error`: con tipo de error y sin departamento.

### Datos de ejemplo

`departments`:

| id | name |
|----|------|
| 1 | Soporte Técnico |
| 2 | Comercial |
| 3 | Agradecimientos |

`error_types`:

| id | code | description |
|----|------|-------------|
| 1 | `EMPTY_MESSAGE` | El mensaje está vacío |
| 2 | `API_KEY_MISSING` | Falta la clave de la API de IA |
| 3 | `AI_TIMEOUT` | La IA tardó demasiado en responder |
| 4 | `AI_INVALID_RESPONSE` | La IA devolvió un departamento no válido |
| 5 | `UNKNOWN` | Error no previsto |

`consultations` (nombres y textos ficticios y neutros):

| client_name | message | status | department | error |
|-------------|---------|--------|------------|-------|
| Cliente Ejemplo 1 | Quiero información sobre los precios de vuestros servicios. | `classified` | Comercial | — |
| Cliente Ejemplo 2 | La aplicación no me deja iniciar sesión. | `error` | — | `AI_TIMEOUT` |

## Plan de implementación

1. Crear la rama `spec-02-base-de-datos`. Crear `db/init.sql` solo con `departments` y `error_types` y sus datos. Commit.
2. Añadir la tabla `consultations` con sus restricciones y las 2 consultas de ejemplo. Commit.
3. Montar `init.sql` en el servicio `db` de `docker-compose.yml`. Empezar de cero con `docker compose down -v` y `docker compose up -d`. Comprobar en TablePlus. Commit.
4. Probar las restricciones con inserciones inválidas (ver criterios). Marcar el spec como `Implementado`. Push.

## Criterios de aceptación

- [ ] Tras `docker compose down -v` y `docker compose up -d`, TablePlus muestra las tablas `departments`, `error_types` y `consultations`.
- [ ] `departments` tiene 3 filas, `error_types` 5 y `consultations` 2.
- [ ] Reiniciar los contenedores sin `-v` no duplica los datos.
- [ ] Insertar una consulta con `status = 'otro'` falla.
- [ ] Insertar una consulta `classified` sin `department_id` falla.
- [ ] Insertar una consulta con `department_id = 99` falla.
- [ ] Insertar un departamento repetido falla.
- [ ] `health.php` sigue devolviendo `"database": "ok"`.
- [ ] `init.sql` no contiene datos reales de nadie.
- [ ] El código está en inglés básico y los comentarios en español.

## Decisiones

- **Sí:** un único `init.sql`. Es lo más simple para un proyecto de este tamaño.
- **No:** tabla `categories`. La categoría es el departamento.
- **No:** campo `classified_by`. Si Gemini falla, las palabras clave hacen de reserva sin dejar marca.
- **Sí:** `status` como `VARCHAR` con `CHECK`, no como `ENUM`. Es más fácil de cambiar y de explicar.
- **Sí:** `CHECK` de coherencia entre `status`, `department_id` y `error_type_id`. La base de datos impide estados imposibles aunque falle el código PHP.
- **Sí:** `error_types` con `code` único. PHP usará el código (`AI_TIMEOUT`) y buscará su `id`; si no existe, usará `UNKNOWN`.
- **Sí:** una consulta de ejemplo con error, para que el listado muestre los dos estados desde el principio.
- **No:** índices ni migraciones por ahora.

## Riesgos

| Riesgo | Mitigación |
|--------|------------|
| `init.sql` no se ejecuta porque el volumen `pgdata` ya existe | Es normal. Empezar de cero con `docker compose down -v` y `docker compose up -d`. Esto borra todos los datos de la BD. |
| Error de sintaxis en `init.sql` y la BD queda a medias | Mirar `docker compose logs db`. Corregir y repetir `down -v`. |
| Tildes mal guardadas (`Técnico`) | PostgreSQL usa UTF-8 por defecto en la imagen oficial. Guardar `init.sql` en UTF-8 y comprobar en TablePlus. |
| Cambiar el esquema más adelante | Editar `init.sql` y repetir `down -v`. Aceptable en una prueba técnica sin datos reales. |

## Progreso de la implementación

Rama: `spec-02-base-de-datos` (aún sin crear). Última actualización: 2026-11-11.

- [ ] Paso 1: `init.sql` con `departments` y `error_types`.
- [ ] Paso 2: tabla `consultations` y datos de ejemplo.
- [ ] Paso 3: montar `init.sql` en `docker-compose.yml` y probar desde cero.
- [ ] Paso 4: probar restricciones, cierre y push.

## Lo que **no** está en este spec

- Clasificador y Gemini.
- API y frontend.
- Índices, filtros y migraciones.
- README.

Cada uno va en su propio spec.
