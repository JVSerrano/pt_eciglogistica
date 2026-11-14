# SPEC 04 — Clasificador con Gemini y reserva por palabras clave

> **Estado:** Implementado
> **Depende de:** SPEC 03 (Implementado)
> **Fecha:** 2026-11-11
> **Objetivo:** Que `classifier.py` pueda preguntar a Gemini a qué departamento va un mensaje y, si Gemini falla, use las palabras clave del SPEC 03 como reserva, sin cambiar el formato de entrada ni de salida.

## Por qué existe este spec

Las palabras clave del SPEC 03 son pobres con frases complejas. Gemini entiende el contexto y clasifica mejor. Pero depende de la red, de una clave y de límites de uso, así que no puede ser el único camino: si falla, la consulta tiene que clasificarse igualmente.

## Alcance

**Dentro:**

- Leer `CLASSIFIER_MODE` del entorno: `keywords` (por defecto) o `gemini`.
- En modo `gemini`: llamar a la API REST de Gemini con el mensaje y validar la respuesta.
- Reserva: si Gemini falla por cualquier motivo, usar la clasificación por palabras clave.
- Tests con `unittest` que simulan Gemini (sin red y sin clave).
- Usar solo la librería estándar de Python (`urllib`, `json`, `os`).

**Fuera (otros specs):**

- Llamar al script desde PHP y guardar el resultado (Etapa 3).
- Validar la longitud máxima del mensaje (lo hace la API).
- Reintentos, caché y límites de uso propios.
- Cambiar o ampliar las palabras clave.
- Instalar librerías con `pip` (no se usa el SDK de Google).

## Estructura y datos

Archivos nuevos o modificados:

    PT_Eciglogistica/
    ├── classifier/
    │   ├── classifier.py            (modificado: modo gemini + reserva)
    │   └── test_classifier.py       (modificado: tests con Gemini simulado)
    ├── .env.example                 (modificado solo si falta alguna variable)
    └── specs/04-clasificador-gemini.md   (nuevo)

No cambia `docker-compose.yml`: el servicio `web` ya lee `.env` con `env_file`.

### Variables de entorno

| Variable | Uso |
|----------|-----|
| `CLASSIFIER_MODE` | `keywords` o `gemini`. Si falta o tiene otro valor, se usa `keywords`. |
| `GEMINI_API_KEY` | Clave de Google AI Studio. Solo en `.env`, nunca en Git. |
| `GEMINI_MODEL` | Nombre del modelo. Se comprueba el modelo gratuito vigente al implementar. |

Importante: `env_file` se lee al **crear** el contenedor. Tras cambiar `.env` hay que ejecutar `docker compose up -d` para recrearlo.

### Contrato del script

No cambia. Misma entrada (stdin) y misma salida (JSON en stdout, código de salida `0`):

    {"ok": true, "department": "Comercial"}
    {"ok": false, "error_code": "EMPTY_MESSAGE"}

Para quien llama, un mensaje clasificado por Gemini y uno clasificado por reserva son iguales. No se añade ningún campo que diga quién clasificó.

### Flujo de `classify(message)`

1. Mensaje vacío o solo espacios: `EMPTY_MESSAGE` (igual que antes, sin llamar a Gemini).
2. Si el modo es `keywords`: clasificación por palabras clave (SPEC 03).
3. Si el modo es `gemini`:
   1. Pedir el departamento a Gemini (tiempo máximo de espera: 10 segundos).
   2. Si responde uno de los tres departamentos exactos: devolverlo.
   3. En cualquier otro caso (sin clave, sin modelo, fallo de red, tiempo agotado, error HTTP, respuesta que no es uno de los tres): usar las palabras clave.
4. El motivo del fallo se escribe en `stderr` en una línea corta (por ejemplo `gemini failed: timeout`). Nunca se escribe la clave ni el mensaje.

### Llamada a Gemini

- Petición HTTPS `POST` a la API REST `generateContent` del modelo indicado en `GEMINI_MODEL`.
- La clave va en una cabecera, no en la URL, para que no acabe en registros.
- Temperatura `0` para que la misma frase dé la misma respuesta.
- El prompt (en inglés básico) obliga a responder con **solo** uno de los tres nombres exactos y nada más.
- El mensaje del cliente se envía como contenido separado de las instrucciones. Aunque alguien escriba "ignora lo anterior", solo se acepta una respuesta que sea uno de los tres nombres; lo peor que puede pasar es que elija otro departamento.
- Se comparan los nombres recortando espacios, sin distinguir mayúsculas y sin tener en cuenta las tildes. El resultado devuelto es siempre el nombre canónico de la lista del código.

## Plan de implementación

1. Comprobar en la documentación de Google AI Studio el modelo gratuito vigente y el formato exacto de la petición. Rellenar `GEMINI_API_KEY` y `GEMINI_MODEL` en `.env` y recrear con `docker compose up -d`. Prueba: una petición suelta con la clave responde sin error. No se cambia código. Sin commit.
2. Añadir la función que llama a Gemini y valida la respuesta (`ask_gemini`), sin conectarla todavía a `classify`. Prueba a mano con 3 mensajes, uno por departamento. Commit.
3. Conectar el modo: leer `CLASSIFIER_MODE`, llamar a `ask_gemini` y usar las palabras clave como reserva con el aviso en `stderr`. Prueba a mano: modo `gemini` con clave correcta, con clave falsa y sin clave. Commit.
4. Añadir tests con `unittest.mock` que simulan Gemini: respuesta válida, respuesta inválida, tiempo agotado, error HTTP, sin clave, modo `keywords` (no llama a Gemini). Ejecutarlos en el contenedor. Commit.
5. Marcar el spec como `Implementado`. Push.

## Criterios de aceptación

- [ ] Con `CLASSIFIER_MODE=keywords` el comportamiento es el mismo del SPEC 03 y no se hace ninguna llamada de red.
- [ ] Con `CLASSIFIER_MODE=gemini` y clave válida, `echo "gracias por todo"` devuelve `Agradecimientos`.
- [ ] Con `CLASSIFIER_MODE=gemini`, un mensaje que las palabras clave no entienden pero Gemini sí (por ejemplo `"me cobrasteis dos veces este mes"`) devuelve el departamento coherente.
- [ ] Con clave falsa o sin clave, el script devuelve igualmente un departamento (reserva) y termina con código `0`.
- [ ] Si Gemini devuelve texto que no es uno de los tres departamentos, se usa la reserva.
- [ ] Un mensaje vacío devuelve `EMPTY_MESSAGE` sin llamar a Gemini.
- [ ] La clave no aparece en la salida, en `stderr` ni en ningún archivo de Git (`git grep` de la clave no encuentra nada).
- [ ] Un valor raro en `CLASSIFIER_MODE` se trata como `keywords`.
- [ ] Los tests no necesitan red ni clave y `docker compose exec web python3 -m unittest discover -s /opt/classifier` termina con `OK`.
- [ ] `health.php` sigue devolviendo `"database": "ok"`.
- [ ] El código está en inglés básico y los comentarios en español.

## Decisiones

- **Sí:** reserva ante **cualquier** fallo de Gemini, incluido el modo `gemini` sin clave. La consulta siempre queda clasificada y la demo funciona aunque se agote la cuota gratuita.
- **Sí:** librería estándar (`urllib`) en lugar del SDK de Google. No hay `pip`, la imagen no cambia y el código de la llamada se lee entero.
- **Sí:** clave en cabecera y nunca en la URL.
- **Sí:** el motivo del fallo va a `stderr`, no al JSON. Así el contrato con PHP no cambia y aun así se puede depurar con `docker compose exec`.
- **Sí:** aceptar solo los tres nombres exactos. Es la defensa frente a respuestas inventadas y frente a texto malicioso dentro del mensaje.
- **Sí:** tests con Gemini simulado. Son rápidos, repetibles y no gastan cuota.
- **No:** campo que indique quién clasificó (ya decidido en el plan, ver `PLAN_PRIVADO.md`).
- **No:** reintentos automáticos. Con la reserva no hacen falta y alargarían la respuesta.
- **No:** usar los códigos `API_KEY_MISSING`, `AI_TIMEOUT` y `AI_INVALID_RESPONSE` en la salida. Con la reserva, esos casos ya no devuelven error. Los códigos siguen en la tabla `error_types` por si más adelante hay un modo estricto.

## Riesgos

| Riesgo | Mitigación |
|--------|------------|
| Gemini gratuito cambia modelos y límites con frecuencia | El modelo está en `.env`. El Paso 1 lo comprueba en la documentación antes de escribir código. |
| Se agota la cuota gratuita (error 429) | Es un fallo más: entra la reserva. |
| La respuesta tarda y bloquea la petición web | Tiempo máximo de 10 segundos y después reserva. |
| El mensaje del cliente se envía a un servicio externo | Solo se usan textos de ejemplo neutros, sin datos personales. Se avisará en el README (Etapa 5). |
| Alguien escribe instrucciones dentro del mensaje (prompt injection) | La salida se valida contra los tres nombres exactos. |
| La clave se cuela en Git o en un registro | Solo `.env` (ignorado), cabecera en vez de URL y nunca se imprime. Criterio de aceptación con `git grep`. |
| Cambiar `.env` y no ver el efecto | `env_file` se lee al crear el contenedor: recrear con `docker compose up -d`. |
| En Git Bash, `/opt/...` se convierte en una ruta de Windows | Anteponer `MSYS_NO_PATHCONV=1` a los comandos o usar PowerShell. |

## Progreso de la implementación

Rama: `spec-04-clasificador-gemini` (creada, activa). Última actualización: 2026-11-13.

- [x] Paso 1: modelo vigente, clave en `.env` y petición suelta. Modelo: `gemini-3.5-flash-lite` (HTTP 200).
- [x] Paso 2: función `ask_gemini`. Hecho, **sin commit**.
- [x] Paso 3: modo `gemini` con reserva. Hecho, **sin commit**.
- [x] Paso 4: tests con Gemini simulado (29 tests en `OK`, también con red bloqueada). Hecho, **sin commit**.
- [ ] Paso 5: cierre y push.

### Estado al dejarlo (2026-11-13)

- Todo el código está en el árbol de trabajo, **nada está commiteado**. Archivos modificados: `classifier/classifier.py`, `classifier/test_classifier.py` y este spec.
- Cambio de spec acordado durante el Paso 2: la comparación de la respuesta de Gemini ignora también las tildes (`Soporte Tecnico` se acepta como `Soporte Técnico`).
- `.env` sigue con `CLASSIFIER_MODE=keywords`. El modo `gemini` se ha probado pasando la variable con `-e` en `docker compose exec`. No hace falta cambiarlo para cerrar el spec.
- `.env.example` ya tenía las tres variables, no se toca.

### Qué falta

1. Decidir cómo agrupar los commits (el plan pedía uno por paso 2, 3 y 4, pero se hizo todo sin commitear). Opciones: tres commits separados por archivo y tema, o uno solo.
2. Repasar los criterios de aceptación uno a uno y marcarlos.
3. Cambiar el estado del spec a `Implementado`.
4. Commit final y push de la rama `spec-04-clasificador-gemini`, y fusionar con `main`.

### Notas para retomar

- Comandos en Git Bash: anteponer `MSYS_NO_PATHCONV=1`. No hay Python en el equipo anfitrión, todo se ejecuta en el contenedor `web`.
- Tests: `docker compose exec web python3 -m unittest discover -s /opt/classifier`.
- La web está en el puerto `8081` (`http://localhost:8081/health.php`).

## Lo que **no** está en este spec

- API PHP y llamada al script desde PHP.
- Frontend.
- Filtros, índices y migraciones.
- README.

Cada uno va en su propio spec.
