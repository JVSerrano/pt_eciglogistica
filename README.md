# Mini-sistema de categorización de consultas con IA

Aplicación que recibe la consulta de un cliente, la clasifica al instante y la guarda en la base de datos.

- **Frontend:** HTML, CSS y JavaScript sin frameworks (formulario + listado).
- **Backend:** PHP 8.3 (API JSON) que ejecuta un script en Python.
- **Clasificador:** Python 3, usa Gemini (IA) o palabras clave.
- **Base de datos:** PostgreSQL 16.
- Todo se levanta con Docker Compose.

## Categorías

Cada consulta se clasifica en uno de estos departamentos:

- Soporte Técnico
- Comercial
- Agradecimientos

## Cómo arrancarlo

### Requisitos

- **Docker Desktop instalado y abierto** (el icono de la ballena debe estar en marcha antes de continuar).
- Git, para descargar el proyecto.
- No hace falta instalar PHP, Python ni PostgreSQL: todo va dentro de los contenedores.
- No hace falta ninguna clave de API para la primera prueba (ver [Modo del clasificador](#modo-del-clasificador-classifier_mode)).
- Los puertos **8081** (web) y **5433** (base de datos) deben estar libres.

### Pasos

1. Descarga el proyecto y entra en la carpeta:

   ```bash
   git clone https://github.com/JVSerrano/pt_eciglogistica
   cd PT_Eciglogistica
   ```

2. Crea tu archivo `.env` a partir de la plantilla. Los valores de ejemplo ya sirven para arrancar.

   - macOS, Linux, Git Bash o PowerShell:

     ```bash
     cp .env.example .env
     ```

   - Símbolo del sistema de Windows (`cmd`):

     ```bat
     copy .env.example .env
     ```

3. Construye y arranca los contenedores (la primera vez tarda unos minutos porque descarga las imágenes):

   ```bash
   docker compose up --build
   ```

   Espera a que la terminal deje de escribir líneas nuevas. Para dejarlo en segundo plano, usa `docker compose up --build -d`.

### Comprobar que ha ido bien

- Abre http://localhost:8081 : debe verse la web con las pestañas **Nueva consulta** y **Listado**.
- En **Listado** deben aparecer 2 consultas de ejemplo.
- Abre http://localhost:8081/health.php : debe responder un JSON con las versiones de PHP y Python y `"database": "ok"`.
- Prueba a enviar una consulta desde **Nueva consulta**, por ejemplo "Quiero un presupuesto": debe quedar clasificada como **Comercial**.

### Parar y empezar de cero

- Parar: `docker compose down` (conserva los datos).
- Empezar de cero, borrando la base de datos: `docker compose down -v` y luego `docker compose up --build`.

La base de datos se crea sola la primera vez con `db/init.sql` (tablas y 2 consultas de ejemplo). Si cambias ese archivo, el cambio solo se aplica con `docker compose down -v`.

## Configuración (`.env`)

| Variable | Qué hace |
|---|---|
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Datos de la base de datos. Cambia la contraseña si no es solo para pruebas. |
| `CLASSIFIER_MODE` | Cómo se clasifica: `keywords` (por defecto) o `gemini`. Ver más abajo. |
| `GEMINI_API_KEY` | Tu clave personal de Google AI Studio. Solo hace falta en modo `gemini`. |
| `GEMINI_MODEL` | Nombre del modelo de Gemini a usar. Solo hace falta en modo `gemini`. |
| `CLASSIFIER_TRACE` | `true` escribe en el log cómo se decidió cada clasificación (nunca la clave ni el mensaje). |

Después de cambiar el `.env`, recrea el contenedor para que lo lea:

```bash
docker compose up -d --force-recreate web
```

### Modo del clasificador (`CLASSIFIER_MODE`)

El proyecto puede clasificar de dos maneras. Se elige con la variable `CLASSIFIER_MODE`:

| Valor | Cómo clasifica | Necesita |
|---|---|---|
| `keywords` (**por defecto**) | Busca palabras clave en el mensaje (por ejemplo "precio" o "oferta" para Comercial, "error" para Soporte Técnico, "gracias" para Agradecimientos). Si no encuentra ninguna, lo manda a Soporte Técnico. | Nada: sin internet y sin clave. |
| `gemini` | Pregunta a la IA de Google (Gemini) a qué departamento va el mensaje. Si Gemini falla, usa las palabras clave como reserva. | Una clave de API de Gemini propia, y conexión a internet. |

El `.env.example` viene en `keywords` para que el proyecto se pueda probar de inmediato sin configurar nada. Para ver la IA funcionando hay que cambiar a `gemini` siguiendo los pasos de abajo.

La columna **Clasificado por** del listado indica quién decidió cada consulta (`IA` o `Palabras clave`). Así se ve de un vistazo si se ha usado la IA o la reserva.

### Probar con IA real (Gemini)

La clave de API es personal: **cada persona debe crear la suya**. No hay ninguna clave incluida en el proyecto y nunca debe subirse a Git (el archivo `.env` ya está ignorado).

1. **Consigue una clave de Gemini:**
   1. Entra en https://aistudio.google.com/apikey con una cuenta de Google.
   2. Pulsa **Create API key** (Crear clave de API) y elige o crea un proyecto.
   3. Copia la clave que aparece.
   - Gemini tiene una capa gratuita con límites de uso. Los límites y las condiciones los define Google y pueden cambiar; consúltalos en su documentación.
2. **Elige un modelo:** consulta la lista actual en https://ai.google.dev/gemini-api/docs/models y copia el nombre exacto de un modelo que admita `generateContent` (los modelos "flash" son rápidos y baratos). Los nombres cambian con el tiempo. Durante el desarrollo se usó `gemini-3.5-flash-lite`; si ya no existe, elige otro de la lista.
3. **Edita tu `.env`** (no el `.env.example`):

   ```env
   CLASSIFIER_MODE=gemini
   GEMINI_API_KEY=pega_aqui_tu_clave
   GEMINI_MODEL=nombre-del-modelo
   ```

4. **Recrea el contenedor** para que lea los cambios:

   ```bash
   docker compose up -d --force-recreate web
   ```

5. **Comprueba que funciona:** envía una consulta y mira la columna **Clasificado por** del listado: debe poner `IA`. Si pone `Palabras clave`, Gemini ha fallado y se ha usado la reserva. Para ver el motivo, activa las trazas (siguiente apartado).

### Ver cómo decide el clasificador (trazas)

Pon `CLASSIFIER_TRACE=true` en el `.env`, recrea el contenedor y mira el registro:

```bash
docker compose logs -f web
```

Cada consulta escribe una línea con el modo, el método usado, el departamento y, si Gemini falla, el motivo (`timeout`, `http 400`, `no api key`...). Nunca se escribe la clave ni el mensaje del cliente.

## Flujo de una consulta

1. El formulario envía `POST /api/consultations.php` con `client_name` y `message`.
2. PHP valida los datos y guarda la consulta como `pending` (así no se pierde si algo falla).
3. PHP lanza `classifier/classifier.py` y le pasa el mensaje por stdin (con límite de 15 s).
4. Python devuelve un JSON con el departamento y el método usado.
5. PHP actualiza la fila (`classified` o `error`) y responde con la consulta guardada.
6. El listado (`GET /api/consultations.php`) muestra todas, la más reciente primero.

## Estructura

```
classifier/   Clasificador en Python y sus tests
db/init.sql   Tablas y datos de ejemplo
docker/       Dockerfile de PHP + Apache + Python
public/       Frontend y API (api/consultations.php)
specs/        Especificaciones de cada fase del proyecto
```

## Tests

Los tests del clasificador (`classifier/test_classifier.py`, 53 tests) se ejecutan dentro del contenedor, así que no hace falta tener Python instalado. No necesitan internet ni clave: la respuesta de Gemini se simula.

Con el proyecto arrancado:

```bash
docker compose exec web python3 -m unittest discover -s /opt/classifier
```

Debe terminar con `OK`.

> En Git Bash de Windows, la ruta `/opt/classifier` se convierte en una ruta de Windows y falla. Antepón `MSYS_NO_PATHCONV=1` al comando, o usa PowerShell.

## Problemas frecuentes

| Problema | Causa y solución |
|---|---|
| `Cannot connect to the Docker daemon` o error similar al ejecutar `docker compose` | Docker Desktop no está abierto. Ábrelo, espera a que arranque y repite. |
| `port is already allocated` o `address already in use` | El puerto 8081 o 5433 está ocupado. Cierra el programa que lo usa, o cambia el primer número en `docker-compose.yml` (por ejemplo `"127.0.0.1:8082:80"`) y abre esa dirección. |
| Error por falta del archivo `.env` | No se ha hecho el paso 2. Ejecuta `cp .env.example .env` (o `copy` en `cmd`). |
| El listado no carga o `health.php` dice `"database": "error"` | La base de datos aún está arrancando. Espera unos segundos y recarga. Si sigue igual, mira `docker compose logs db`. |
| He cambiado `db/init.sql` y no se nota | Solo se ejecuta con el volumen vacío. Usa `docker compose down -v` y vuelve a arrancar (borra los datos). |
| Con `CLASSIFIER_MODE=gemini` todo sale como `Palabras clave` | Gemini está fallando y se usa la reserva. Activa `CLASSIFIER_TRACE=true` y mira `docker compose logs -f web`: `no api key` o `no model` indican que falta rellenar el `.env`; `http 400/403` suele ser clave o modelo incorrectos; `http 429` es que se ha superado el límite de uso. |
| He cambiado el `.env` y no hace efecto | Hay que recrear el contenedor: `docker compose up -d --force-recreate web`. |

## Decisiones y buenas prácticas

- **Seguridad:** consultas SQL preparadas, el mensaje va por stdin (nunca como argumento de shell), la clave de Gemini va en cabecera y no en la URL, y el prompt ignora instrucciones dentro del mensaje del cliente.
- **Errores controlados:** la tabla `error_types` guarda por qué falló una clasificación (timeout, respuesta inválida, etc.). El cliente nunca ve detalles internos.
- **Integridad:** restricciones `CHECK` en la base de datos garantizan que estado, departamento y error sean coherentes.
- **Resiliencia:** si la IA falla, hay clasificación por palabras clave.
- **Frontend:** accesible (pestañas con teclado, mensajes `aria-live`), con estados de carga, vacío y error. Sin dependencias externas en ejecución.

## Limitaciones

- La clasificación es síncrona: si Gemini tarda, la persona espera hasta el límite (10 s en Gemini, 15 s en PHP).
- No hay autenticación ni límite de peticiones; es una prueba técnica.
- No hay tests automáticos de la API PHP.
