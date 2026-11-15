# SPEC 08 — Trazas del clasificador por consola

> **Estado:** Implementado
> **Depende de:** SPEC 03 (Implementado), SPEC 04 (Implementado), SPEC 05 (Implementado), SPEC 07 (Implementado)
> **Fecha:** 2026-11-15
> **Objetivo:** Ver por consola, en tiempo real, cómo clasifica cada consulta: qué modo está activo, qué método ha decidido (Gemini o palabras clave), qué ha respondido Gemini y qué palabras clave han coincidido, para poder comprobar si la IA hace bien su trabajo.

## Por qué existe este spec

Hoy el clasificador solo escribe en `stderr` cuando Gemini **falla** (`gemini failed: timeout`). Cuando Gemini responde bien, o cuando se usan las palabras clave, no queda ninguna señal de qué ha pasado. Con `CLASSIFIER_MODE=gemini` no hay forma de saber si el departamento lo decidió la IA o la reserva, ni de comparar lo que dijo la IA con lo que habrían dicho las palabras clave.

El camino de las trazas ya existe: la API PHP recoge el `stderr` del script y lo escribe en el registro de PHP (`error_log('classifier: ...')`), que se ve con `docker compose logs -f web`. Este spec añade **qué** se escribe en ese `stderr`.

## Alcance

**Dentro:**

- Una traza de una sola línea por cada clasificación, escrita en `stderr` del script.
- La traza indica: modo activo, método que decidió (`gemini` o `keywords`), departamento, tiempo en milisegundos y, según el caso, el motivo de la reserva o las palabras clave que coincidieron.
- En modo `gemini`, cuando Gemini responde, se registra también el departamento que dijo la IA y el que habrían dado las palabras clave, para compararlos.
- Un interruptor `CLASSIFIER_TRACE` (`true` o `false`) en `.env` y `.env.example`. Apagado por defecto en el código.
- Tests con `unittest` para las trazas y para comprobar que el interruptor las apaga.
- Documentar en el spec cómo ver las trazas (`docker compose logs -f web`).

**Fuera (otros specs):**

- Cambiar el prompt de Gemini o la lógica de reserva del SPEC 04.
- Cambiar qué departamento se elige. Las trazas solo observan.
- Guardar las trazas en la base de datos o en ficheros.
- Mostrar las trazas en el frontend.
- Cambiar el formato de la salida JSON por `stdout`.
- Cambiar la lista de palabras clave (por ejemplo `roto`, anotado en el SPEC 07).

## Estructura y datos

    PT_Eciglogistica/
    ├── classifier/
    │   ├── classifier.py            (modificado: función de traza y datos de decisión)
    │   └── test_classifier.py       (modificado: tests de trazas)
    ├── .env                         (modificado: CLASSIFIER_TRACE)
    ├── .env.example                 (modificado: CLASSIFIER_TRACE)
    └── specs/08-trazas-clasificador.md   (nuevo)

No cambian el formato de entrada ni el de salida del script. No cambia la API PHP: ya vuelca el `stderr` en el registro.

### Formato de la traza

Una línea por clasificación, con pares `clave=valor`. Todo en inglés básico.

| Caso | Ejemplo de línea |
|------|------------------|
| Modo `keywords` | `trace mode=keywords method=keywords department=Comercial matches=oferta,descuento ms=1` |
| Modo `gemini`, Gemini responde | `trace mode=gemini method=gemini department=Comercial gemini=Comercial keywords=Soporte Técnico ms=640` |
| Modo `gemini`, Gemini falla | `trace mode=gemini method=keywords department=Soporte Técnico reason=timeout matches=none ms=10003` |

- `matches` lista las palabras clave que han coincidido, o `none`.
- `keywords=` en la línea de Gemini es lo que habrían dado las palabras clave, para detectar desacuerdos.
- **Nunca** se escribe la clave de API ni el texto completo del mensaje del cliente.

### Variable de entorno

    CLASSIFIER_TRACE=true

Solo `true` (sin importar mayúsculas) activa las trazas. Cualquier otro valor, o su ausencia, las apaga. Igual que `CLASSIFIER_MODE`, se lee en cada ejecución.

## Plan de implementación

1. Añadir `CLASSIFIER_TRACE` a `.env` y `.env.example`, y la función que lee el interruptor. Prueba: apagado no escribe nada en `stderr`.
2. Hacer que la clasificación por palabras clave pueda devolver también las palabras que coincidieron, sin cambiar lo que ya devuelve a quien la llama.
3. Escribir la traza del modo `keywords`. Medir el tiempo con `time.monotonic()`.
4. Escribir las trazas del modo `gemini`: respuesta correcta (con la comparación con las palabras clave) y reserva por fallo.
5. Tests: una traza por caso, el interruptor apagado, y que la traza no contiene la clave ni el mensaje. Comprobar que los tests anteriores siguen en verde.
6. Probar en vivo con `docker compose logs -f web` enviando mensajes desde el frontend, en modo `keywords` y en modo `gemini`.
7. Revisar los criterios de aceptación y marcar el spec como `Implementado`.

## Criterios de aceptación

- [x] Con `CLASSIFIER_TRACE=true`, cada consulta escribe una línea de traza en `docker compose logs -f web`.
- [x] En modo `keywords` la traza muestra el departamento y las palabras que coincidieron.
- [x] En modo `gemini`, si Gemini responde, la traza muestra lo que dijo la IA y lo que habrían dado las palabras clave.
- [x] En modo `gemini`, si Gemini falla, la traza muestra el motivo y que se usó la reserva.
- [x] Con `CLASSIFIER_TRACE=false` o sin la variable, el `stderr` queda como antes (solo `gemini failed: ...` si falla).
- [x] La traza nunca contiene la clave de API ni el texto completo del mensaje.
- [x] El departamento elegido no cambia respecto al SPEC 07 en ningún caso.
- [x] El formato de salida JSON del script no cambia.
- [x] Todos los tests anteriores siguen pasando y hay tests nuevos para las trazas.
- [x] El código está en inglés básico y los comentarios en español.

## Decisiones

- **Sí:** usar `stderr`. El SPEC 05 ya lo recoge y lo escribe en el registro de PHP, así que no hay que tocar la API.
- **Sí:** una sola línea por clasificación con `clave=valor`. Es fácil de leer y de filtrar con `grep`.
- **Sí:** interruptor `CLASSIFIER_TRACE`, apagado por defecto en el código. Así los tests y el comportamiento actual no cambian si nadie lo activa.
- **Sí:** registrar el desacuerdo entre Gemini y las palabras clave. Es lo que permite juzgar si la IA acierta.
- **No:** guardar el mensaje del cliente en las trazas. Es dato de clientes y el registro puede acabar en otro sitio.
- **No:** guardar trazas en la base de datos ni en ficheros. Con la consola basta para este objetivo.

## Riesgos

| Riesgo | Mitigación |
|--------|------------|
| Un test existente comprueba el contenido de `stderr` y las trazas lo cambian | Las trazas están apagadas por defecto. Se revisan los tests de `stderr` (como el de la clave) en el Paso 5. |
| La traza filtra la clave de API o el mensaje del cliente | Nunca se escriben. Hay un test que lo comprueba. |
| Calcular las palabras clave en modo `gemini` añade trabajo extra | Es una búsqueda de texto muy barata. Solo se hace con las trazas activas. |
| PHP junta varias líneas del `stderr` en una sola entrada del registro | Se escribe una única línea de traza por ejecución. |

## Progreso de la implementación

Rama: `spec-08-trazas-clasificador`. Última actualización: 2026-11-15.

- [x] Paso 1: interruptor `CLASSIFIER_TRACE`.
- [x] Paso 2: palabras clave que coincidieron.
- [x] Paso 3: traza del modo `keywords`.
- [x] Paso 4: trazas del modo `gemini`.
- [x] Paso 5: tests.
- [x] Paso 6: prueba en vivo.
- [x] Paso 7: cierre.

### Notas de la implementación

- **Cómo ver las trazas:** poner `CLASSIFIER_TRACE=true` en `.env`, recrear el contenedor con `docker compose up -d` y ejecutar `docker compose logs -f web`. Las líneas salen con el prefijo `classifier: trace ...`. Para ver el flujo de la IA hace falta además `CLASSIFIER_MODE=gemini`.
- **Causa de la duda inicial:** `.env` tenía `CLASSIFIER_MODE=keywords`, así que Gemini nunca se llamaba. Con `gemini` la IA responde en unos 600-800 ms.
- **Prueba en vivo:** con Gemini real las trazas llegan al registro de PHP. Si Gemini falla, PHP escribe en una sola entrada el aviso `gemini failed: ...` y la traza (probado en el script, no en vivo).
- **Cosmético:** Apache escapa las tildes UTF-8 en el registro (`T\xc3\xa9cnico`). El dato es correcto.
- **Pendiente, fuera de este spec:** que el modo por defecto del código sea `gemini` con reserva por palabras clave (hoy es `keywords` si falta la variable, como fija el SPEC 04). Va en otro spec.
- **Estado final de `.env`:** `CLASSIFIER_MODE=gemini` y `CLASSIFIER_TRACE=false`.

## Lo que **no** está en este spec

- Mostrar las trazas en el frontend o guardarlas.
- Cambiar el prompt de Gemini, la reserva o las palabras clave.
- Filtros y paginación del listado (Bonus).
- README y despliegue (Etapa 5).

Cada uno va en su propio spec.
