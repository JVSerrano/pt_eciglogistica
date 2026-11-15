# SPEC 09 — Mostrar en el listado quién clasificó cada consulta

> **Estado:** Implementado 
> **Depende de:** SPEC 02, SPEC 04, SPEC 05, SPEC 06, SPEC 08 (todos Implementado)
> **Fecha:** 2026-11-15
> **Objetivo:** Que el listado de consultas tenga una columna que diga si el departamento lo decidió la IA (Gemini) o las palabras clave.

## Por qué existe este spec

Hoy el método que decide el departamento solo se ve en las trazas de consola (SPEC 08) y no se guarda. Para verlo en el listado hay que **guardarlo** con cada consulta. Eso toca los cuatro niveles: clasificador, base de datos, API y frontend. Por eso es un spec nuevo y no un cambio dentro del SPEC 08 (que dice "guardar trazas" y "mostrarlas en el frontend" fuera de alcance).

## Alcance

**Dentro:**

- El clasificador añade el campo `method` (`gemini` o `keywords`) a su salida JSON.
- Nueva columna `classified_by` en `consultations` (nula si no está clasificada).
- La API guarda el método y lo devuelve en `GET` y `POST`.
- Nueva columna "Clasificado por" en el listado: `IA` o `Palabras clave`, y `—` si no aplica.
- Tests nuevos y ajuste de los tests que comparan la salida JSON exacta.

**Fuera (otros specs):**

- Cambiar qué departamento se elige, el prompt o la lista de palabras clave.
- Guardar el motivo de la reserva, las palabras que coincidieron o el tiempo.
- Filtrar el listado por método.
- Rellenar las consultas antiguas (quedan en `—`).

## Estructura y datos

    PT_Eciglogistica/
    ├── classifier/classifier.py          (modificado: devuelve "method")
    ├── classifier/test_classifier.py     (modificado)
    ├── db/init.sql                       (modificado: columna classified_by)
    ├── public/api/consultations.php      (modificado: guarda y devuelve classified_by)
    ├── public/index.html                 (modificado: nueva cabecera)
    ├── public/scripts/app.js             (modificado: nueva celda)
    └── specs/09-metodo-clasificacion-listado.md  (nuevo)

### Salida del clasificador

    {"ok": true, "department": "Comercial", "method": "gemini"}

`method` es `gemini` solo si Gemini respondió; si Gemini falló y se usó la reserva, o el modo es `keywords`, es `keywords`. Los errores (`ok: false`) no llevan `method`.

### Base de datos

    classified_by VARCHAR(10)
        CHECK (classified_by IN ('gemini', 'keywords'))

La restricción de coherencia existente se amplía: `classified` exige `classified_by` NOT NULL; `pending` y `error` exigen que sea NULL. Los 2 datos de ejemplo se ajustan (el primero lleva `keywords`).

Como indica el SPEC 02, no hay migraciones: para aplicar el cambio se borra el volumen (`docker compose down -v`) y se vuelve a levantar. **Se pierden las consultas guardadas.**

### API

Campo nuevo en cada consulta: `"classified_by": "gemini" | "keywords" | null`. Si la API recibe un `method` que no es uno de los dos valores, la consulta pasa a `error` con `AI_INVALID_RESPONSE`, igual que con un departamento inválido.

### Frontend

Nueva columna entre "Departamento" y "Estado":

| `classified_by` | Texto |
|-----------------|-------|
| `gemini` | IA |
| `keywords` | Palabras clave |
| `null` | — |

## Plan de implementación

1. Clasificador: devolver `method` y ajustar sus tests.
2. Base de datos: columna, restricciones y datos de ejemplo.
3. API: guardar y devolver `classified_by`, validar el valor.
4. Frontend: cabecera y celda (con estilo responsive igual que las demás).
5. Recrear la base de datos y probar en vivo en modo `keywords` y en modo `gemini` (incluyendo un fallo de Gemini).
6. Revisar criterios y marcar como `Implementado`.

## Criterios de aceptación

- [x] La salida del clasificador incluye `method` en las clasificaciones correctas.
- [x] Con Gemini respondiendo, el listado muestra `IA`.
- [x] En modo `keywords`, o con Gemini fallando, el listado muestra `Palabras clave`.
- [x] Consultas `pending` o `error` muestran `—`.
- [x] La base de datos rechaza un estado incoherente con `classified_by`.
- [x] El departamento elegido no cambia respecto al SPEC 07.
- [x] Los tests anteriores siguen pasando y hay tests nuevos.
- [x] Código en inglés básico y comentarios en español.

## Decisiones

- **Sí:** guardar el método en la base de datos. Es la única forma de verlo en el listado después.
- **Sí:** fallo de Gemini cuenta como `keywords`, porque fueron las palabras clave quienes decidieron.
- **Sí:** columna propia en vez de reutilizar `status`. El estado y el método son cosas distintas.
- **No:** migración ni relleno de datos antiguos. Es una prueba técnica y el SPEC 02 ya fija "borrar el volumen".

## Riesgos

| Riesgo | Mitigación |
|--------|------------|
| Borrar el volumen pierde las consultas actuales | Son datos de prueba; se avisa antes de hacerlo. |
| Tests que comparan el JSON exacto fallan | Se ajustan en el Paso 1. |

## Lo que **no** está en este spec

- Filtros y paginación del listado, motivo de la reserva, tiempos.

## Progreso de la implementación

Rama: `spec-09-metodo-clasificacion-listado`. Última actualización: 2026-11-15.

- [x] Paso 1: clasificador devuelve `method`.
- [x] Paso 2: columna `classified_by` y restricciones en `init.sql`.
- [x] Paso 3: API guarda y devuelve `classified_by`.
- [x] Paso 4: columna "Clasificado por" en el listado.
- [x] Paso 5: base recreada (`down -v`) y prueba en vivo en modo `gemini` y `keywords`.
- [x] Paso 6: cierre.

### Notas de la implementación

- **Orden de columnas:** "Clasificado por" es la última, después de "Fecha / hora" (ajuste pedido tras ver el primer resultado).
- **Ancho:** `.container` pasa de 960px a 1200px para que la tabla quepa sin barra horizontal. El formulario no cambia, tiene su propio límite de 600px.
- **Móvil (hasta 640px):** la columna de etiquetas pasa de 110px a 130px (cabe "Clasificado por") y cada fila tiene 14px de relleno vertical para separar mejor unas etiquetas de otras.
- **Pruebas:** la API se probó contra una base temporal (Gemini real, clave inválida con reserva) y luego en vivo tras recrear el volumen. No hay tests automáticos de PHP en el proyecto, así que el caso de un `method` inválido (`AI_INVALID_RESPONSE`) no tiene test.
- **Consultas antiguas:** al recrear el volumen se perdieron las consultas de prueba. No hay datos antiguos que rellenar.
