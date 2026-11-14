# SPEC 05 — API PHP para crear y listar consultas

> **Estado:** Implementado
> **Depende de:** SPEC 02 (Implementado), SPEC 03 (Implementado), SPEC 04 (Implementado)
> **Fecha:** 2026-11-14
> **Objetivo:** Una API en PHP que recibe una consulta, la guarda, llama al clasificador de Python, guarda el resultado y permite listar todas las consultas.

## Por qué existe este spec

Hasta ahora la base de datos (SPEC 02) y el clasificador (SPEC 03 y 04) funcionan por separado. La API los une. Es lo que usará el frontend (Etapa 4) y lo que cierra el flujo principal del proyecto: mensaje entra, departamento sale, todo queda guardado.

## Alcance

**Dentro:**

- `POST /api/consultations.php`: valida, guarda como `pending`, clasifica y actualiza a `classified` o `error`.
- `GET /api/consultations.php`: devuelve todas las consultas, la más reciente primero.
- Llamar a `classifier.py` desde PHP pasando el mensaje por entrada estándar.
- Traducir el resultado del clasificador a los campos de la tabla `consultations`.
- Respuestas siempre en JSON y con el código HTTP correcto.
- Consultas preparadas con PDO.

**Fuera (otros specs):**

- Frontend (Etapa 4).
- Filtros del listado y paginación (Bonus).
- Cambiar el clasificador o la base de datos.
- Autenticación, límite de peticiones y CORS (la web y la API comparten origen).
- Tests automáticos en PHP (no hay `composer`; se prueba con `curl`, ver criterios).

## Estructura y datos

Archivos nuevos o modificados:

    PT_Eciglogistica/
    ├── public/
    │   └── api/
    │       └── consultations.php      (nuevo)
    └── specs/05-api-php.md            (nuevo)

No cambian `docker-compose.yml`, el `Dockerfile` ni `init.sql`. El volumen `./public` ya se ve en `web` y el clasificador ya está en `/opt/classifier`.

### Contrato: crear consulta

    POST /api/consultations.php
    Content-Type: application/json

    {"client_name": "Cliente Ejemplo", "message": "gracias por todo"}

Respuesta correcta (`201`):

    {
      "ok": true,
      "consultation": {
        "id": 3,
        "client_name": "Cliente Ejemplo",
        "message": "gracias por todo",
        "department": "Agradecimientos",
        "status": "classified",
        "error_code": null,
        "created_at": "2026-11-14 10:00:00",
        "classified_at": "2026-11-14 10:00:01"
      }
    }

Si la consulta se guarda pero la clasificación falla, la respuesta también es `201` con `"status": "error"`, `"department": null` y `"error_code"` con el código (por ejemplo `"UNKNOWN"`). La petición ha tenido éxito: la consulta existe y queda marcada con error. El frontend decide qué mostrar según `status`.

Respuestas de error (nada se guarda):

    {"ok": false, "error_code": "INVALID_INPUT", "message": "client_name is required"}

| Caso | Código HTTP | `error_code` |
|------|-------------|--------------|
| Cuerpo que no es JSON válido | 400 | `INVALID_JSON` |
| `client_name` o `message` vacío, ausente, no es texto, o demasiado largo | 422 | `INVALID_INPUT` |
| Método distinto de `GET` y `POST` | 405 | `METHOD_NOT_ALLOWED` |
| Fallo de base de datos o error interno | 500 | `INTERNAL_ERROR` |

Estos códigos son de la API. No tienen nada que ver con la tabla `error_types`, que describe fallos de clasificación de una consulta ya guardada.

### Contrato: listar consultas

    GET /api/consultations.php

Respuesta (`200`):

    {"ok": true, "consultations": [ { ...mismos campos de arriba... }, ... ]}

Orden: `created_at` descendente y, si empatan, `id` descendente. Sin filtros ni paginación en este spec.

### Validación de entrada

- `client_name` y `message` deben ser texto. Se recortan los espacios de los extremos.
- No pueden quedar vacíos después de recortar.
- Longitud máxima: `client_name` 100 caracteres (límite de la columna), `message` 2000 caracteres.
- Se cuentan caracteres, no bytes (para que las tildes no cuenten doble).
- El mensaje de error dice qué campo falla, nunca incluye el texto recibido.

### Flujo de `POST`

1. Comprobar el método y leer el cuerpo. Si no es JSON válido: `INVALID_JSON`.
2. Validar los dos campos. Si falla: `INVALID_INPUT`. No se toca la base de datos.
3. `INSERT` con `status = 'pending'`. Queda guardada antes de llamar al clasificador, así no se pierde si algo falla después.
4. Ejecutar `python3 /opt/classifier/classifier.py` con el mensaje por stdin (sin pasar por el intérprete de comandos), con un tiempo máximo de 15 segundos (el clasificador espera hasta 10 a Gemini y después usa la reserva).
5. Interpretar la salida:
   - JSON con `"ok": true` y un departamento que existe en `departments`: `classified`.
   - JSON con `"ok": false` y un `error_code` que existe en `error_types`: `error` con ese código.
   - Departamento que no existe en `departments`: `error` con `AI_INVALID_RESPONSE`.
   - Tiempo máximo agotado: `error` con `AI_TIMEOUT`.
   - Código de salida distinto de `0`, salida que no es JSON o cualquier otra cosa: `error` con `UNKNOWN`.
6. `UPDATE` de la fila con el resultado y `classified_at = NOW()`. Respetar las restricciones de coherencia de la tabla (un `classified` lleva departamento y no error, un `error` lleva error y no departamento).
7. Responder `201` con la consulta completa, leída de la base de datos.

### Llamada a Python

- Se usa `proc_open` con la orden como lista de argumentos (`['python3', '/opt/classifier/classifier.py']`): no hay shell, no hay inyección de comandos.
- El mensaje se escribe en el `stdin` del proceso y se cierra. Nunca va por argumento.
- El proceso hereda el entorno del contenedor, así `CLASSIFIER_MODE`, `GEMINI_API_KEY` y `GEMINI_MODEL` llegan al clasificador sin leerlos en PHP.
- `stderr` del clasificador (por ejemplo `gemini failed: timeout`) se escribe en el registro de errores de PHP con `error_log`, nunca en la respuesta.

### Formato de fechas

PostgreSQL guarda `TIMESTAMP` sin zona horaria y con microsegundos. La API los devuelve como texto `YYYY-MM-DD HH:MM:SS`, sin microsegundos, formateados en la consulta con `to_char`. La zona horaria la define el servidor de base de datos y no se convierte en este spec.

## Plan de implementación

1. Crear `public/api/consultations.php` con la conexión PDO, las funciones de respuesta JSON y el método no permitido (`405`). Prueba: `GET` devuelve una respuesta JSON vacía de contenido y `DELETE` devuelve `405`. Comprobar de paso que `mbstring` está disponible. Commit.
2. Implementar `GET`: consulta con `JOIN` a `departments` y `error_types`, formato de salida, orden. Prueba: devuelve las 2 consultas del seed. Commit.
3. Implementar la validación de entrada y el `INSERT` en `pending` para `POST`, sin clasificar todavía. Prueba con `curl`: entradas inválidas dan `400` y `422`; una válida queda como `pending` en TablePlus. Commit.
4. Implementar la llamada a Python (`proc_open`), la interpretación del resultado y el `UPDATE`. Prueba con `curl`: `gracias por todo` queda `classified` en `Agradecimientos`. Commit.
5. Probar los caminos de fallo: clasificador con un departamento inexistente, tiempo agotado y salida no válida (usando una copia temporal del script fuera de Git, o variables de entorno). Revisar `GET` final. Commit si hay cambios.
6. Revisar los criterios de aceptación, marcar el spec como `Implementado` y push.

## Criterios de aceptación

- [x] `POST` con `{"client_name":"Cliente Ejemplo","message":"gracias por todo"}` devuelve `201`, `"status":"classified"` y `"department":"Agradecimientos"`.
- [x] La fila queda en la base de datos con `status = 'classified'`, `department_id` relleno, `error_type_id` vacío y `classified_at` relleno.
- [x] Con `CLASSIFIER_MODE=gemini` y clave válida, `POST` con `"me cobrasteis dos veces este mes"` devuelve `201` y un departamento coherente.
- [x] Con `CLASSIFIER_MODE=gemini` y clave falsa, `POST` sigue devolviendo `201` y `classified` (reserva por palabras clave).
- [x] `POST` con un mensaje de solo espacios devuelve `422` y no crea ninguna fila.
- [x] `POST` con `client_name` ausente, vacío, no texto o de más de 100 caracteres devuelve `422` y no crea ninguna fila.
- [x] `POST` con un mensaje de más de 2000 caracteres devuelve `422`.
- [x] `POST` con un cuerpo que no es JSON devuelve `400`.
- [x] Un método distinto de `GET` y `POST` devuelve `405` con cabecera `Allow`.
- [x] Si el clasificador falla (salida no válida, código de salida distinto de `0` o tiempo agotado), la consulta queda con `status = 'error'` y el `error_code` correspondiente, y `POST` devuelve `201`.
- [x] `GET` devuelve las consultas ordenadas de la más reciente a la más antigua, con el nombre del departamento (no el id) y el `error_code` (no el id).
- [x] Una consulta con comillas, `<script>` o `'; DROP TABLE` en el mensaje se guarda y se devuelve tal cual, sin romper nada (consultas preparadas).
- [x] Las tildes se guardan y se devuelven sin escapar (`Soporte Técnico`).
- [x] Ninguna respuesta de error incluye la clave, el texto de excepciones de PDO ni rutas internas.
- [x] Todas las respuestas llevan `Content-Type: application/json`.
- [x] `health.php` sigue devolviendo `"database": "ok"`.
- [x] Los tests del clasificador siguen en `OK`.
- [x] El código está en inglés básico y los comentarios en español.

## Decisiones

- **Sí:** guardar `pending` **antes** de clasificar. Si el clasificador o el servidor se caen, la consulta no se pierde.
- **Sí:** `201` también cuando la consulta queda en `error`. La petición se completó: se creó un recurso. El detalle va en `status` y `error_code`.
- **Sí:** un único archivo `consultations.php` con funciones pequeñas. Con dos endpoints no hace falta un framework ni una estructura de carpetas mayor. Si crece, se divide en un spec posterior.
- **Sí:** códigos de error de la API (`INVALID_INPUT`, etc.) separados de la tabla `error_types`. Unos son errores de la petición, los otros son fallos de clasificación de una consulta ya guardada.
- **Sí:** `proc_open` con lista de argumentos y mensaje por stdin. Evita la inyección de comandos y no deja el mensaje visible en la lista de procesos.
- **Sí:** devolver la consulta completa en el `POST`. El frontend no necesita una segunda petición para mostrar el resultado.
- **Sí:** el límite de 2000 caracteres para el mensaje. Es suficiente para una consulta y limita lo que se envía a Gemini.
- **Sí:** el tiempo máximo de 15 segundos para el script, mayor que los 10 de Gemini. El clasificador tiene su propio tiempo y su reserva; este es solo un seguro.
- **No:** reutilizar `health.php` para la conexión. Se copia la conexión PDO (pocas líneas) para no acoplar los dos archivos.
- **No:** filtros ni paginación. Son el Bonus.
- **No:** autenticación ni límite de peticiones. Fuera del alcance de una prueba técnica local.
- **No:** campo que indique si clasificó Gemini o la reserva (decisión del plan, ver `PLAN_PRIVADO.md`).

## Riesgos

| Riesgo | Mitigación |
|--------|------------|
| El proceso hijo no ve `GEMINI_API_KEY` o `CLASSIFIER_MODE` | Se comprueba en el Paso 4 con modo `gemini`. Si Apache no pasa el entorno, se pasa de forma explícita en `proc_open`. |
| `mbstring` no está en la imagen | Se comprueba en el Paso 1. Si falta, se cuenta la longitud con `preg_match_all('/./u', ...)`. |
| Un cuerpo enorme llena la memoria | `post_max_size` de PHP lo limita; además se valida la longitud del mensaje antes de guardar. |
| La respuesta tarda hasta 15 s y el navegador espera | Es el peor caso (Gemini caído). El frontend mostrará un estado de "enviando". La reserva suele responder mucho antes. |
| La fila queda en `pending` si falla el `UPDATE` | Se responde `500`. Es poco probable y queda visible en el listado como `pending`. |
| Una excepción de PDO muestra datos internos | Se captura y se responde con `INTERNAL_ERROR` genérico. El detalle va a `error_log`. |
| El texto del cliente rompe el HTML del frontend (XSS) | La API devuelve texto sin tocar. El frontend (Etapa 4) debe escapar al mostrar; se anota ahí. |
| En Git Bash, `curl` con JSON y comillas falla | Usar PowerShell (`Invoke-RestMethod`) o un archivo `.json` con `curl --data @archivo`. |

## Progreso de la implementación

Rama: `spec-05-api-php`. Última actualización: 2026-11-14. Sin commits todavía: se hacen todos juntos al terminar.

- [x] Paso 1: archivo base, conexión y `405`.
- [x] Paso 2: `GET`.
- [x] Paso 3: validación y `INSERT` en `pending`.
- [x] Paso 4: llamada a Python y `UPDATE`.
- [x] Paso 5: caminos de fallo.
- [ ] Paso 6: cierre y push. Criterios revisados (18/18). Falta marcar la spec como `Implementado`, el commit, el merge a `main` y el push (los hace el usuario).

### Notas de implementación

Decisiones que la spec no cubría y que se tomaron al implementar:

- **Paso 1:** un `set_exception_handler` responde `500 INTERNAL_ERROR` genérico y manda el detalle a `error_log`. Se desactiva `display_errors` para no filtrar rutas.
- **Paso 2:** las fechas se formatean con `to_char` (ver "Formato de fechas"), porque PostgreSQL las devuelve con microsegundos.
- **Paso 3:** un JSON válido que no es un objeto (por ejemplo `5`) se trata como objeto vacío y da `422`, no `400`. Un carácter nulo (`\u0000`) en medio del texto da `422`, porque PostgreSQL no lo admite. `json_encode` usa `JSON_UNESCAPED_SLASHES` para devolver el texto tal cual (`</script>` y no `<\/script>`).
- **Paso 4:** un JSON con `ok: true` cuyo `department` no es texto (falta o es otro tipo) se considera salida mal formada y da `UNKNOWN`. Solo un texto que no existe en `departments` da `AI_INVALID_RESPONSE`. Si el clasificador devuelve un `error_code` que no existe en `error_types`, también da `UNKNOWN`.
- **Paso 5, cómo se probaron los fallos:** se cambió `CLASSIFIER_COMMAND` solo durante cada prueba para apuntar a scripts falsos copiados a `/tmp` del contenedor (fuera del repositorio), y se restauró el archivo desde una copia de seguridad. Para probar Gemini sin tocar `.env` se usó `['env', 'CLASSIFIER_MODE=gemini', ...]`.
- **Paso 5, resultados:**

  | Caso | `status` | `error_code` |
  |------|----------|--------------|
  | Departamento que no existe (`Marketing`) | `error` | `AI_INVALID_RESPONSE` |
  | Tiempo agotado (15 s; el proceso se mata, no queda colgado) | `error` | `AI_TIMEOUT` |
  | Salida que no es JSON | `error` | `UNKNOWN` |
  | Código de salida `1` aunque la salida sea válida | `error` | `UNKNOWN` |
  | `ok: false` con código válido (`EMPTY_MESSAGE`) | `error` | `EMPTY_MESSAGE` |
  | `ok: false` con código que no existe | `error` | `UNKNOWN` |
  | `department` que no es texto | `error` | `UNKNOWN` |
  | Script o comando que no existe | `error` | `UNKNOWN` |
  | `stderr` con salida válida | `classified` | (el `stderr` va a `error_log`) |
  | Gemini con la clave real heredada del contenedor | `classified` | (el entorno llega al proceso hijo) |
  | Gemini con clave falsa | `classified` | (reserva por palabras clave; `gemini failed: http 400` en `error_log`) |

  Todos devuelven `201`. En el modo `gemini` el contenedor tiene `CLASSIFIER_MODE=keywords` por defecto; la prueba con Gemini real consumió 1 petición.
- **Datos de prueba:** las pruebas de los Pasos 3 a 6 dejaron filas en la tabla y se borraron al terminar cada fase (20 filas al cerrar el Paso 5 y 4 más en la revisión final). La tabla tiene solo las 2 del seed. Los ids nuevos siguen desde el 30 porque la secuencia no se reinicia.

## Lo que **no** está en este spec

- Frontend.
- Filtros, índices y migraciones.
- README.

Cada uno va en su propio spec.
