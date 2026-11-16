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

Requisito: Docker Desktop.

```bash
cp .env.example .env
docker compose up --build
```

Abre http://localhost:8081

La base de datos se crea sola la primera vez con `db/init.sql` (tablas y 2 consultas de ejemplo).
Para empezar de cero: `docker compose down -v` y vuelve a arrancar.

## Configuración (`.env`)

| Variable | Qué hace |
|---|---|
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Datos de la base de datos. Cambia la contraseña. |
| `CLASSIFIER_MODE` | `keywords` (por defecto, sin internet ni clave) o `gemini` (IA real). |
| `GEMINI_API_KEY` | Clave de Google AI Studio. Solo hace falta en modo `gemini`. |
| `GEMINI_MODEL` | Nombre del modelo de Gemini a usar. |
| `CLASSIFIER_TRACE` | `true` escribe en el log cómo se decidió cada clasificación (nunca la clave ni el mensaje). |

### Probar con IA real

1. Consigue una clave en Google AI Studio.
2. En `.env` pon `CLASSIFIER_MODE=gemini`, tu `GEMINI_API_KEY` y un `GEMINI_MODEL` válido.
3. Reinicia: `docker compose up -d --force-recreate web`.

Si Gemini falla (sin red, timeout, respuesta rara), el clasificador usa las palabras clave como reserva. La columna **Clasificado por** del listado indica quién decidió cada una (`gemini` o `keywords`).

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

Tests del clasificador (no necesitan Docker ni clave):

```bash
cd classifier
python -m unittest test_classifier -v
```

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
