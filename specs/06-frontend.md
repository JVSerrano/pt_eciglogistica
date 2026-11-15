# SPEC 06 — Frontend: formulario de consultas y listado

> **Estado:** Implementado
> **Depende de:** SPEC 05 (Implementado)
> **Fecha:** 2026-11-14
> **Objetivo:** Una página web con dos pestañas, "Nueva consulta" y "Listado", que usa la API del SPEC 05 para enviar una consulta, mostrar a qué departamento ha ido y listar todas las consultas guardadas.

## Por qué existe este spec

La API, el clasificador y la base de datos ya funcionan, pero solo se pueden usar con `curl`. Este spec añade la parte que ve el usuario y cierra el flujo completo del proyecto: el usuario escribe un mensaje en el navegador y ve el departamento al que se envía.

## Alcance

**Dentro:**

- Una página con dos pestañas: **Nueva consulta** y **Listado**.
- Se usará el logo que esta en la carpeta img/logo.png
- los colores serán blanco y #DE2C37
- Formulario con nombre, mensaje y botón de envío. Al enviar muestra "Consulta enviada al departamento X" o "Ha habido un error".
- Para mostrar los mensajes usaremos la libreria toastify https://apvarun.github.io/toastify-js/#
- Estado de "enviando" que evita envíos dobles (la API puede tardar hasta 15 s). Si fuera necesario poner un spinner de https://magecdn.com/tools/svg-loaders
- Listado en tabla con nombre, mensaje, departamento, estado y fecha, la más reciente primero.
- Estados de carga, lista vacía y error de conexión en el listado. Usar spinner si fuera necesario 
- Validación básica en el navegador (campos vacíos y longitudes) antes de enviar.
- Mostrar el texto del usuario sin ejecutarlo nunca como HTML (protección contra XSS).
- Diseño simple, usable en móvil.

**Fuera (otros specs):**

- Filtros y paginación del listado (Bonus).
- README y despliegue (Etapa 5).
- Cambiar la API, el clasificador o la base de datos.
- Frameworks, `npm`, empaquetadores y tests automáticos de JavaScript (no hay Node en el proyecto; se prueba a mano en el navegador, ver criterios).
- Actualización automática del listado cada cierto tiempo.
- Editar o borrar consultas, autenticación, varios idiomas.

## Estructura y datos

Archivos nuevos:

    PT_Eciglogistica/
    ├── public/
    │   ├── index.html          (nuevo: estructura de la página y las dos pestañas)
    │   ├── img/logo.png        (nuevo: logo)
    │   ├── vendor/toastify/    (nuevo: toastify.js y toastify.css, Toastify 1.12.0 en local)
    │   ├── styles/style.css    (nuevo: estilos)
    │   └── scripts/app.js      (nuevo: pestañas, formulario y listado)
    └── specs/06-frontend.md  (nuevo)

No cambian `docker-compose.yml`, el `Dockerfile`, `init.sql` ni `public/api/`. El volumen `./public` ya se ve en `web`, y Apache sirve `index.html` en `http://localhost:8081/`. La web y la API comparten origen, así que no hace falta CORS y las peticiones usan la ruta relativa `/api/consultations.php`.

### Pestañas

- Dos botones arriba: **Nueva consulta** y **Listado**. Al cargar la página se ve "Nueva consulta".
- Cambiar de pestaña no recarga la página. Al abrir "Listado" se pide la lista a la API (así siempre está al día).
- Los botones llevan los atributos de accesibilidad de pestañas (`role="tab"`, `aria-selected`) y se pueden usar con el teclado.

### Pestaña "Nueva consulta"

- Campo **Nombre** (`maxlength="100"`) y área de texto **Mensaje** (`maxlength="2000"`), cada uno con su `<label>`.
- Botón **Enviar**.
- Antes de enviar, el navegador recorta los espacios y comprueba que ninguno está vacío. Si falla, muestra un aviso en español junto al campo y **no** llama a la API. La API sigue siendo la que decide: esta validación es solo comodidad.
- Mientras espera la respuesta: botón desactivado con el texto "Enviando...", y no se permite otro envío.
- Tiempo máximo de espera en el navegador: 20 segundos (la API espera como mucho 15 al clasificador).
- Si todo va bien, el formulario se vacía. Si falla, **se conserva** lo escrito para que el usuario no lo pierda.

### Mensajes de resultado

La API devuelve `201` tanto si la consulta queda `classified` como si queda `error`, así que el navegador decide el mensaje mirando `status`:

| Respuesta de la API | Mensaje al usuario |
|---------------------|--------------------|
| `201` con `status: "classified"` | "Consulta enviada al departamento **{department}**." |
| `201` con `status: "error"` | "Ha habido un error. La consulta se ha guardado, pero no se ha podido clasificar." |
| `201` con cualquier otro `status` | Igual que el caso anterior. |
| `400` o `422` | "Revisa el nombre y el mensaje e inténtalo de nuevo." |
| `405`, `500` u otra respuesta (también si no es JSON) | "No se ha podido enviar la consulta. Inténtalo de nuevo." |
| Sin conexión | "No se ha podido conectar con el servidor." |
| Tiempo agotado (20 s) | "La respuesta tarda demasiado. Mira el listado antes de volver a enviar, por si la consulta ya se guardó." |

El mensaje se muestra en una zona con `aria-live="polite"` para que lo lean los lectores de pantalla. Nunca se muestran al usuario el texto de error de la API, códigos internos ni detalles técnicos.

### Pestaña "Listado"

Tabla con estas columnas, en este orden: **Nombre**, **Mensaje**, **Departamento**, **Clasificado por**, **Estado**, **Fecha / hora**. (La columna "Clasificado por" la añadió el SPEC 09; el orden actual agrupa lo que se lee junto.)

Diseño visual (mejora posterior de UX/UI, sin iconos):

- **Color por departamento:** cada fila lleva un fondo suave, una barra de color a la izquierda y el departamento en una pastilla del mismo color. Soporte Técnico en azul, Comercial en ámbar y Agradecimientos en verde. Las filas sin departamento quedan blancas y sin barra. El color nunca es el único indicador: el departamento siempre está escrito.
- **El rojo solo para errores:** el rojo de marca no se usa como color de departamento, para que un error destaque.
- **Filas separadas:** hueco de 8 px entre una consulta y la siguiente, con esquinas redondeadas, para que cada una se vea como una pieza propia.
- **Estado como pastilla:** `Clasificada` en gris con borde, `Pendiente` en gris con borde discontinuo y cursiva, `Error` en rojo suave.
- **"Clasificado por" discreto:** texto gris y más pequeño, porque es un dato secundario.
- **Fecha corta:** `11 nov, 17:28` (con el año si no es el actual). La fecha completa `DD/MM/AAAA HH:MM:SS` queda en el atributo `title` (se ve al pasar el ratón).
- **Cabecera clara:** fondo gris muy claro con línea roja inferior, en lugar de roja a todo ancho.
- **Móvil:** la barra de color pasa a ser el borde izquierdo de la tarjeta.

- Orden: el que devuelve la API (la más reciente primero). No se reordena en el navegador.
- Los mensajes largos se recortan a 3 líneas. Si el texto no cabe, aparece un botón **Mostrar más** que lo expande y pasa a **Mostrar menos** para contraerlo. Si cabe entero, no hay botón. Funciona con textos largos sin espacios.
- `department` vacío se muestra como `—`.
- `status` se muestra en español: `pending` → "Pendiente", `classified` → "Clasificada", `error` → "Error".
- `Fecha / hora` es `created_at` reordenado en español, sin conversión de zona horaria: formato corto a la vista y `DD/MM/AAAA HH:MM:SS` en el `title` (ver "Diseño visual").
- Estados de la pestaña: "Cargando..." mientras espera, "Todavía no hay consultas." si la lista está vacía, y "No se ha podido cargar el listado." con un botón **Reintentar** si la petición falla.
- Un botón **Actualizar** vuelve a pedir la lista.
- En pantallas estrechas (hasta 640 px) cada consulta se muestra como una tarjeta con sus cinco datos en filas "etiqueta + valor", de modo que se ve todo sin desplazamiento horizontal. En pantallas anchas se mantiene la tabla.

### Seguridad al mostrar datos

El texto de `client_name` y `message` lo escribe el usuario y la API lo devuelve sin tocar (puede contener `<script>` o `<img onerror=...>`). Por eso:

- Todo dato de la API se escribe con `textContent` o `createTextNode`. **Nunca** se usa `innerHTML`, `outerHTML` ni `insertAdjacentHTML` con datos de la API.
- Los saltos de línea del mensaje se conservan con CSS (`white-space: pre-wrap`), no con HTML.
- Los textos largos se parten con CSS (`overflow-wrap: anywhere`) para no desbordar la tabla.

## Plan de implementación

1. Crear `index.html`, `style.css` y `app.js` con la estructura, las dos pestañas y su cambio con el ratón y el teclado, sin datos todavía. Prueba: `http://localhost:8081/` muestra la página y las pestañas cambian. Commit.
2. Implementar el listado: `GET`, tabla, estados de carga, vacío y error con **Reintentar**, y botón **Actualizar**. Prueba: salen las consultas del seed en español. Commit.
3. Implementar el formulario: validación en el navegador, estado "Enviando..." y llamada `POST` con tiempo máximo. Prueba: una consulta válida se guarda y aparece en el listado. Commit.
4. Implementar los mensajes de resultado de la tabla de arriba y refrescar el listado al abrir su pestaña. Prueba: `gracias por todo` muestra "enviada al departamento Agradecimientos". Commit.
5. Probar los caminos de fallo y la seguridad: texto con `<script>` e `<img onerror>`, `422`, `500` simulado, API caída, tiempo agotado, móvil y teclado. Commit si hay cambios.
6. Revisar los criterios de aceptación, marcar el spec como `Implementado` y push.

## Criterios de aceptación

- [ ] `http://localhost:8081/` carga la página sin errores en la consola del navegador.
- [ ] Hay dos pestañas, "Nueva consulta" y "Listado", y se puede cambiar entre ellas con el ratón y con el teclado.
- [ ] Enviar `gracias por todo` con un nombre válido muestra "Consulta enviada al departamento Agradecimientos." y vacía el formulario.
- [ ] La consulta enviada aparece arriba del listado con el departamento, el estado "Clasificada" y la fecha.
- [ ] Con nombre o mensaje vacío (o solo espacios), el navegador muestra un aviso y **no** llama a la API (se comprueba en la pestaña de red del navegador).
- [ ] Mientras se envía, el botón está desactivado y dice "Enviando...". Pulsar dos veces seguidas crea una sola consulta.
- [ ] Si la consulta queda en `error`, se muestra "Ha habido un error..." y la consulta aparece en el listado con estado "Error".
- [ ] Si la API devuelve `422` o `500`, o está caída, se muestra el mensaje correspondiente de la tabla y **se conserva** lo escrito en el formulario.
- [ ] Un mensaje con `<script>alert(1)</script>` y otro con `<img src=x onerror=alert(1)>` se ven como texto en el listado y no ejecutan nada.
- [ ] Las tildes y la `ñ` se ven bien en el formulario, en los mensajes y en el listado.
- [ ] El listado muestra las columnas Nombre, Mensaje, Departamento, Clasificado por, Estado y Fecha / hora (corta, con la completa `DD/MM/AAAA HH:MM:SS` al pasar el ratón), con `—` cuando no hay departamento.
- [ ] Cada fila tiene el color de su departamento (fondo, barra y pastilla); las filas sin departamento son neutras y el rojo solo aparece en el estado "Error".
- [ ] Con la lista vacía se muestra "Todavía no hay consultas.". Si la petición falla se muestra "No se ha podido cargar el listado." con un botón **Reintentar** que funciona.
- [ ] Un mensaje de 2000 caracteres sin espacios no rompe el diseño (ni en el listado ni en móvil).
- [ ] Un mensaje largo se ve recortado a 3 líneas con **Mostrar más**, que lo expande y pasa a **Mostrar menos**. Un mensaje corto no muestra el botón.
- [ ] A 375 px de ancho no hay ningún desplazamiento horizontal (ni de la página ni del listado) y se ven todos los datos de cada consulta.
- [ ] No hay ningún uso de `innerHTML`, `outerHTML` ni `insertAdjacentHTML` con datos de la API (se comprueba con una búsqueda en `app.js`).
- [ ] No se carga ningún recurso externo (ni librerías, ni fuentes, ni scripts de terceros).
- [ ] `GET` y `POST` de la API y `health.php` siguen funcionando igual.
- [ ] El código está en inglés básico y los comentarios en español. Los textos que ve el usuario están en español.

## Decisiones

- **Sí:** tres archivos (`index.html`, `style.css`, `app.js`) sin frameworks. Es lo que pide el plan y basta para dos pantallas.
- **Sí:** pestañas con botones y mostrar u ocultar secciones, sin recargar la página ni usar rutas.
- **Sí:** el navegador decide el mensaje con el campo `status`, no con el código HTTP, porque la API responde `201` también cuando la consulta queda en `error`.
- **Sí:** `textContent` para todo dato de la API. Es la protección contra XSS que el SPEC 05 dejó anotada para esta etapa.
- **Sí:** conservar lo escrito si el envío falla. Perder un mensaje largo por un fallo de red es lo peor que le puede pasar al usuario.
- **Sí:** tiempo máximo de 20 s en el navegador, mayor que los 15 s de la API, y un mensaje propio que avisa de que la consulta puede haberse guardado.
- **Sí:** refrescar el listado al abrir su pestaña y con un botón. Es simple y siempre está al día sin consultar la API cada pocos segundos.
- **Sí:** la fecha se muestra en formato español (`DD/MM/AAAA HH:MM:SS`) reordenando el texto que devuelve la API (`YYYY-MM-DD HH:MM:SS`). Sin conversiones de zona horaria, igual que en el SPEC 05.
- **Sí:** validar en el navegador solo por comodidad. La API sigue siendo la fuente de verdad y repite todas las comprobaciones.
- **No:** mostrar los mensajes de error de la API. Están en inglés y son técnicos; el usuario ve textos propios en español.
- **No:** fuentes ni librerías externas. La página funciona sin internet y no depende de terceros.
- **No:** filtros ni paginación. Son el Bonus.
- **No:** mostrar el `error_code` al usuario. Es información interna de la clasificación.

## Riesgos

| Riesgo | Mitigación |
|--------|------------|
| El texto del usuario ejecuta código en el navegador (XSS) | Solo `textContent`, nunca `innerHTML` con datos de la API. Se prueba con `<script>` e `<img onerror>` en el Paso 5. |
| El usuario pulsa **Enviar** varias veces y crea consultas duplicadas | Botón desactivado y bloqueo en JavaScript mientras hay un envío en curso. |
| El envío tarda hasta 15 s si Gemini falla | Texto "Enviando..." y botón desactivado para que se vea que no se ha colgado. |
| El navegador da por perdida una petición que la API sí guardó | Mensaje de tiempo agotado que manda mirar el listado antes de reenviar. |
| La API devuelve algo que no es JSON (por ejemplo una página de error de Apache) | La lectura del JSON va dentro de `try/catch` y se trata como "No se ha podido enviar la consulta". |
| Una palabra muy larga rompe la tabla o la tarjeta | `overflow-wrap: anywhere`, tarjetas en móvil y la tabla dentro de un contenedor con desplazamiento horizontal en pantallas intermedias. |
| El navegador guarda en caché una versión antigua de `app.js` | Recarga forzada (`Ctrl+F5`) durante las pruebas. |
| `index.html` no se sirve en la raíz | Se comprueba en el Paso 1; el `php:apache` incluye `index.html` como página por defecto. |

## Progreso de la implementación

Rama: `spec-06-frontend`. Última actualización: 2026-11-15.

- [x] Paso 1: página base y pestañas.
- [x] Paso 2: listado.
- [x] Paso 3: formulario y envío.
- [x] Paso 4: mensajes de resultado.
- [x] Paso 5: caminos de fallo y seguridad.
- [x] Paso 6: cierre y push.

## Lo que **no** está en este spec

- Filtros por nombre, departamento o estado, y paginación.
- README.
- Cambios en la API o en la base de datos.

Cada uno va en su propio spec.
