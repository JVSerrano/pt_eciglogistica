# SPEC 07 — Mejorar el clasificador: plurales y variantes de palabras

> **Estado:** Borrador
> **Depende de:** SPEC 03 (Implementado), SPEC 04 (Implementado), SPEC 06 (Implementado)
> **Fecha:** 2026-11-15
> **Objetivo:** Que el clasificador por palabras clave reconozca plurales y variantes de las palabras (por ejemplo "ofertas" además de "oferta"), para que mensajes como "Necesito las nuevas ofertas para los socios de A Coruña" vayan a Comercial y no a Soporte Técnico.

## Por qué existe este spec

Al probar el frontend, el mensaje `Necesito las nuevas ofertas para los socios de A Coruña` se clasificó como **Soporte Técnico** y debía ser **Comercial**.

La causa está en `classifier/classifier.py`:

- La lista de Comercial tiene `"oferta"` en singular.
- `count_matches` busca cada palabra como **palabra completa** (`\bpalabra\b`), así que `"ofertas"` no coincide.
- Sin ninguna coincidencia, el mensaje cae en el departamento por defecto, **Soporte Técnico**.

Ocurrirá igual con "descuentos", "tarifas", "presupuestos" y otras variantes. Es un fallo de las palabras clave, que son la reserva cuando Gemini falla y el único método en modo `keywords`. El SPEC 04 dejó fuera "cambiar o ampliar las palabras clave", por eso se hace en un spec propio.

## Alcance

**Dentro:**

- Cambiar la coincidencia de palabras clave para que una palabra clave valga también como **comienzo de palabra** (así `oferta` reconoce `ofertas` y `ofertamos`), manteniendo el límite al principio (`\b`).
- Revisar las listas de palabras clave y ajustarlas a ese nuevo criterio (quitar duplicados de singular y plural, y vigilar las palabras cortas que puedan dar falsos positivos).
- Tests con `unittest` para el mensaje que falló, los plurales y los casos que no deben cambiar.
- Comprobar qué modo (`CLASSIFIER_MODE`) estaba activo cuando falló el mensaje y anotarlo en el spec.

**Fuera (otros specs):**

- Cambiar el departamento por defecto (sigue siendo Soporte Técnico).
- Cambiar el prompt de Gemini o la lógica de reserva del SPEC 04.
- Cambiar la API PHP, el frontend o la base de datos.
- Lematización o librerías de lenguaje natural (`pip`, `nltk`, etc.).
- Añadir nuevos departamentos.

## Estructura y datos

    PT_Eciglogistica/
    ├── classifier/
    │   ├── classifier.py            (modificado: coincidencia por comienzo de palabra y listas ajustadas)
    │   └── test_classifier.py       (modificado: tests de plurales y del mensaje que falló)
    └── specs/07-mejorar-clasificador.md   (nuevo)

No cambian el formato de entrada ni el de salida del script.

### Regla de coincidencia propuesta

Una palabra clave coincide si el texto contiene esa palabra **al comienzo de una palabra**: expresión `\b` + palabra, sin `\b` al final. Los mensajes ya se normalizan (minúsculas y sin tildes) antes de comparar.

| Mensaje | Palabra clave | ¿Coincide? |
|---------|---------------|------------|
| `las nuevas ofertas` | `oferta` | Sí |
| `precios y tarifas` | `precio`, `tarifa` | Sí |
| `una superoferta` | `oferta` | No (no está al comienzo de palabra) |
| `no puedo entrar` | `no puedo` | Sí |

Las frases de varias palabras (`no funciona`) siguen igual.

## Plan de implementación

1. Reproducir el fallo con un test que falla: `Necesito las nuevas ofertas para los socios de A Coruña` debe dar Comercial. Comprobar el modo activo en `.env`.
2. Cambiar `count_matches` a coincidencia por comienzo de palabra.
3. Ajustar las listas de `KEYWORDS`: quitar los plurales que ya cubre el singular y revisar las palabras cortas.
4. Añadir tests de plurales (`ofertas`, `descuentos`, `tarifas`, `presupuestos`) y de no regresión (los tests actuales siguen en verde).
5. Probar el mensaje de ejemplo extremo a extremo desde el frontend.
6. Revisar los criterios de aceptación y marcar el spec como `Implementado`.

## Criterios de aceptación

- [ ] `Necesito las nuevas ofertas para los socios de A Coruña` se clasifica como Comercial en modo `keywords`.
- [ ] Los plurales de las palabras clave (`ofertas`, `descuentos`, `tarifas`, `presupuestos`, `precios`) se reconocen.
- [ ] Todos los tests anteriores del clasificador (SPEC 03 y SPEC 04) siguen pasando.
- [ ] Hay tests nuevos para los plurales y para el mensaje que falló.
- [ ] Un mensaje sin ninguna palabra clave sigue yendo a Soporte Técnico.
- [ ] El formato de salida del script no cambia.
- [ ] El código está en inglés básico y los comentarios en español.

## Decisiones

- **Sí:** coincidencia por comienzo de palabra. Es sencilla, solo usa la librería estándar y cubre plurales y derivados sin listas enormes.
- **Sí:** mantener el `\b` al principio para no coincidir en mitad de una palabra (`superoferta`).
- **Sí:** mantener Soporte Técnico como departamento por defecto, como se decidió en el SPEC 03.
- **No:** librerías de lenguaje natural. No hay `pip` en el proyecto y es excesivo para tres departamentos.
- **No:** tocar Gemini ni la reserva. Este spec solo afecta a las palabras clave.

## Riesgos

| Riesgo | Mitigación |
|--------|------------|
| Una palabra corta coincide con palabras que no tienen relación (falsos positivos) | Revisar las listas en el Paso 3 y añadir tests de no regresión. |
| El cambio altera clasificaciones que ya funcionaban | Los tests de los SPEC 03 y 04 deben seguir en verde. |
| El fallo del mensaje venía de Gemini y no de las palabras clave | Comprobar `CLASSIFIER_MODE` y `stderr` en el Paso 1; si es Gemini, abrir otro spec. |

## Progreso de la implementación

Rama: pendiente de crear (`spec-07-mejorar-clasificador`). Última actualización: 2026-11-15.

- [ ] Paso 1: test que reproduce el fallo.
- [ ] Paso 2: coincidencia por comienzo de palabra.
- [ ] Paso 3: ajuste de las listas.
- [ ] Paso 4: tests de plurales y no regresión.
- [ ] Paso 5: prueba extremo a extremo.
- [ ] Paso 6: cierre.

## Lo que **no** está en este spec

- Filtros y paginación del listado (Bonus).
- README y despliegue (Etapa 5).
- Cambios en Gemini, la API, el frontend o la base de datos.

Cada uno va en su propio spec.
