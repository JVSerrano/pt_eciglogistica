import json
import re
import sys
import unicodedata

# Departamento por defecto si no hay ninguna coincidencia
DEFAULT_DEPARTMENT = "Soporte Técnico"

# Palabras clave por departamento, escritas sin tildes y en minúsculas.
# El orden de la lista es el orden de desempate: gana el primero.
KEYWORDS = [
    (
        "Soporte Técnico",
        [
            "error", "fallo", "problema", "ayuda", "roto", "bloqueado", "bloqueo", "usuarios",
            "no funciona", "no puedo", "no me deja", "sesion", "contrasena", "incorrecto", "advertencia"
        ],
    ),
    (
        "Comercial",
        [
            "precio", "precios", "presupuesto", "tarifa", "oferta",
            "descuento", "comprar", "contratar", "informacion", "cancelacion"
        ],
    ),
    (
        "Agradecimientos",
        [
            "gracias", "agradezco", "agradecido", "felicidades",
            "enhorabuena", "excelente", "genial", "buen trabajo",
        ],
    ),
]


def read_message():
    # Lee todo el mensaje desde la entrada estándar
    return sys.stdin.read()


def normalize(text):
    # Pasa a minúsculas y quita las tildes (á -> a, ñ -> n)
    text = text.lower()
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


def count_matches(text, words):
    # Cuenta cuántas palabras clave aparecen como palabra completa
    total = 0
    for word in words:
        if re.search(r"\b" + re.escape(word) + r"\b", text):
            total += 1
    return total


def classify(message):
    # Mensaje vacío o solo espacios: error previsto
    if message.strip() == "":
        return {"ok": False, "error_code": "EMPTY_MESSAGE"}

    text = normalize(message)

    best_department = DEFAULT_DEPARTMENT
    best_count = 0
    for department, words in KEYWORDS:
        count = count_matches(text, words)
        # Solo cambia si hay más coincidencias, así el empate lo gana el primero
        if count > best_count:
            best_department = department
            best_count = count

    return {"ok": True, "department": best_department}


def main():
    # Fuerza UTF-8 en la entrada y en la salida
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")

    message = read_message()
    result = classify(message)

    # ensure_ascii=False mantiene las tildes sin escapar
    sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
