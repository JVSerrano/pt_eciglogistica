-- Se ejecuta solo la primera vez, cuando el volumen de PostgreSQL está vacío.

-- Departamentos a los que se puede enviar una consulta
CREATE TABLE departments (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE
);

-- Tipos de error que puede tener una consulta
CREATE TABLE error_types (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) NOT NULL UNIQUE,
    description VARCHAR(255) NOT NULL
);

INSERT INTO departments (name) VALUES
    ('Soporte Técnico'),
    ('Comercial'),
    ('Agradecimientos');

INSERT INTO error_types (code, description) VALUES
    ('EMPTY_MESSAGE', 'El mensaje está vacío'),
    ('API_KEY_MISSING', 'Falta la clave de la API de IA'),
    ('AI_TIMEOUT', 'La IA tardó demasiado en responder'),
    ('AI_INVALID_RESPONSE', 'La IA devolvió un departamento no válido'),
    ('UNKNOWN', 'Error no previsto');
