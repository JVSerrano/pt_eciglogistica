# SPEC 03 — Clasificador por palabras clave (Python)

> **Estado:** Implementado
> **Depende de:** SPEC 01 (Implementado), SPEC 02 (Implementado)
> **Fecha:** 2026-11-11
> **Objetivo:** Un script de Python que recibe un mensaje por entrada estándar y devuelve en JSON el departamento que le corresponde, usando solo palabras clave.

## Por qué existe este spec

La API (Etapa 3) necesita un clasificador al que llamar. Si empezamos con palabras clave, el flujo completo funciona sin red ni claves. Gemini (SPEC 04) se añadirá después sobre el mismo script, sin cambiar el formato de entrada y salida.

## Alcance

**Dentro:**

- Carpeta `classifier/` con `classifier.py` y `test_classifier.py`.
- Entrada: el mensaje por entrada estándar (stdin). Salida: JSON por salida estándar (stdout).
- Clasificación por palabras clave en español, sin distinguir mayúsculas ni tildes.
- Mensaje vacío o solo espacios: error `EMPTY_MESSAGE`.
- Tests con `unittest` (librería estándar de Python).
- Cambio en `docker-compose.yml`: montar `./classifier` en el servicio `web`.

**Fuera (otros specs):**

- Gemini y la reserva ante fallos (SPEC 04). El script ignora por ahora `CLASSIFIER_MODE`.
- Llamar al script desde PHP y guardar el resultado (Etapa 3).
- Validar la longitud máxima del mensaje (lo hace la API).
- Instalar librerías con `pip`. Este spec usa solo la librería estándar.

## Estructura y datos

Archivos nuevos o modificados:

    PT_Eciglogistica/
    ├── classifier/
    │   ├── classifier.py            (nuevo)
    │   └── test_classifier.py       (nuevo)
    ├── docker-compose.yml           (modificado: volumen de classifier)
    └── specs/03-clasificador-palabras-clave.md   (nuevo)

Cambio en el servicio `web` de `docker-compose.yml`:

    volumes:
      - ./public:/var/www/html
      # El clasificador queda fuera de la carpeta pública de la web
      - ./classifier:/opt/classifier:ro

### Contrato del script

Uso:

    echo "gracias por todo" | docker compose exec -T web python3 /opt/classifier/classifier.py

Salida correcta:

    {"ok": true, "department": "Agradecimientos"}

Salida con error:

    {"ok": false, "error_code": "EMPTY_MESSAGE"}

Reglas:

- El nombre del departamento es exactamente el de la tabla `departments` (`Soporte Técnico`, `Comercial`, `Agradecimientos`).
- El JSON se escribe en UTF-8 y sin escapar las tildes.
- Si el script termina bien, el código de salida es `0`, también cuando devuelve `"ok": false`.
- Si el script se rompe de forma inesperada, termina con código distinto de `0`. PHP lo tratará como `UNKNOWN`.

### Reglas de clasificación

1. Si el mensaje, sin espacios, está vacío: `EMPTY_MESSAGE`.
2. Se pasa el mensaje a minúsculas y se quitan las tildes.
3. Se cuentan las palabras clave de cada departamento que aparecen como palabra completa.
4. Gana el departamento con más coincidencias.
5. Si hay empate, gana el primero de este orden: Soporte Técnico, Comercial, Agradecimientos.
6. Si no hay ninguna coincidencia: `Soporte Técnico` (departamento por defecto).

### Palabras clave iniciales

| Departamento | Palabras clave (sin tildes) |
|--------------|-----------------------------|
| Soporte Técnico | `error`, `fallo`, `problema`, `ayuda`, `roto`, `bloqueado`, `no funciona`, `no puedo`, `no me deja`, `sesion`, `contrasena` |
| Comercial | `precio`, `precios`, `presupuesto`, `tarifa`, `oferta`, `descuento`, `comprar`, `contratar`, `informacion` |
| Agradecimientos | `gracias`, `agradezco`, `agradecido`, `felicidades`, `enhorabuena`, `excelente`, `genial`, `buen trabajo` |

Las listas finales viven en el código. Se pueden ampliar sin cambiar el spec.

## Plan de implementación

1. Crear `classifier/classifier.py` con la lectura de stdin, la salida JSON y solo el caso `EMPTY_MESSAGE`. Montar `./classifier` en `web` (`docker-compose.yml`) y recrear con `docker compose up -d`. Prueba: un mensaje vacío devuelve el error. Commit.
2. Añadir la clasificación por palabras clave (normalizar texto, contar, desempate, departamento por defecto). Prueba a mano con 3 mensajes, uno por departamento. Commit.
3. Crear `classifier/test_classifier.py` con los tests y ejecutarlos en el contenedor. Commit.
4. Marcar el spec como `Implementado`. Push.

## Criterios de aceptación

- [x] `echo "gracias por todo"` devuelve `{"ok": true, "department": "Agradecimientos"}`.
- [x] `echo "Quiero información sobre los precios"` devuelve `Comercial`.
- [x] `echo "La aplicación no me deja iniciar sesión"` devuelve `Soporte Técnico`.
- [x] Un mensaje vacío o solo con espacios devuelve `{"ok": false, "error_code": "EMPTY_MESSAGE"}`.
- [x] Un mensaje sin palabras clave (por ejemplo `"hola buenos dias"`) devuelve `Soporte Técnico`.
- [x] Un mensaje con empate (por ejemplo `"gracias, pero tengo un problema"`) devuelve `Soporte Técnico`.
- [x] Las mayúsculas y las tildes no cambian el resultado (`PRECIOS` y `précios` funcionan igual).
- [x] La salida mantiene las tildes (`Soporte Técnico`, no `Soporte Técnico`).
- [x] `docker compose exec web python3 -m unittest discover -s /opt/classifier` termina con `OK`.
- [x] `health.php` sigue devolviendo `"database": "ok"`.
- [x] El código está en inglés básico y los comentarios en español.

## Decisiones

- **Sí:** dividir la Etapa 2 en dos specs. El SPEC 03 no necesita red ni clave, y se prueba entero en local.
- **Sí:** departamento por defecto `Soporte Técnico` si no hay coincidencias. La consulta siempre queda clasificada y nunca se pierde.
- **Sí:** desempate por orden fijo. Ante la duda, un humano de soporte revisa la consulta.
- **Sí:** palabras completas, no trozos de palabra. Así `plan` no coincide con `explanación`.
- **Sí:** `unittest` en lugar de `pytest`. Viene con Python y no hay que instalar nada.
- **Sí:** `./classifier` montado como volumen de solo lectura en `/opt/classifier`. Se edita sin reconstruir la imagen y no queda dentro de la web pública.
- **Sí:** salida JSON con código de salida `0` también en los errores previstos. Un código distinto de `0` significa que el script falló de forma inesperada.
- **No:** leer el mensaje por argumento de línea de comandos. Se vería en la lista de procesos y puede romperse con comillas.
- **No:** usar `CLASSIFIER_MODE` todavía. Se estrena en el SPEC 04.
- **No:** lógica de longitud máxima. Es validación de entrada y pertenece a la API.

## Riesgos

| Riesgo | Mitigación |
|--------|------------|
| Las palabras clave son pobres y clasifican mal frases complejas | Es esperado: este modo es la reserva y la base para probar. Gemini mejorará el resultado en el SPEC 04. |
| El nombre del departamento en Python no coincide con el de la BD | Los tests comprueban los tres nombres exactos. La API los buscará por nombre. |
| La consola de Windows o el contenedor muestran mal las tildes | El script fuerza UTF-8 en entrada y salida. Probar con `Técnico` en el contenedor. |
| El volumen nuevo no aparece en `web` | Hay que recrear el contenedor con `docker compose up -d` tras editar el compose. |

## Progreso de la implementación

Rama: `spec-03-clasificador-palabras-clave`. Última actualización: 2026-11-11.

- [x] Paso 1: `classifier.py` con `EMPTY_MESSAGE` y volumen en `web`.
- [x] Paso 2: clasificación por palabras clave.
- [x] Paso 3: tests con `unittest`.
- [x] Paso 4: cierre y push.

## Lo que **no** está en este spec

- Gemini y la reserva ante fallos (SPEC 04).
- API PHP y frontend.
- Filtros, índices y migraciones.
- README.

Cada uno va en su propio spec.
