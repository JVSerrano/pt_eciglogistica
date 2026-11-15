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

-- Consultas de los clientes
CREATE TABLE consultations (
    id SERIAL PRIMARY KEY,
    client_name VARCHAR(100) NOT NULL,
    message TEXT NOT NULL,
    department_id INTEGER REFERENCES departments(id),
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    error_type_id INTEGER REFERENCES error_types(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    classified_at TIMESTAMP,
    -- Quién decidió el departamento: la IA (gemini) o las palabras clave (keywords)
    classified_by VARCHAR(10),

    -- Solo se permiten estos tres estados
    CONSTRAINT consultations_status_check
        CHECK (status IN ('pending', 'classified', 'error')),

    -- Solo se permiten estos dos métodos (o nulo)
    CONSTRAINT consultations_classified_by_check
        CHECK (classified_by IN ('gemini', 'keywords')),

    -- Coherencia entre estado, departamento, error y método
    CONSTRAINT consultations_coherence_check CHECK (
        (status = 'pending'    AND department_id IS NULL     AND error_type_id IS NULL     AND classified_by IS NULL)
        OR (status = 'classified' AND department_id IS NOT NULL AND error_type_id IS NULL     AND classified_by IS NOT NULL)
        OR (status = 'error'      AND department_id IS NULL     AND error_type_id IS NOT NULL AND classified_by IS NULL)
    )
);

-- Datos de ejemplo (ficticios)
INSERT INTO consultations (client_name, message, status, department_id, error_type_id, classified_at, classified_by)
VALUES
    (
        'Cliente Ejemplo 1',
        'Quiero información sobre los precios de vuestros servicios.',
        'classified',
        (SELECT id FROM departments WHERE name = 'Comercial'),
        NULL,
        NOW(),
        'keywords'
    ),
    (
        'Cliente Ejemplo 2',
        'La aplicación no me deja iniciar sesión.',
        'error',
        NULL,
        (SELECT id FROM error_types WHERE code = 'AI_TIMEOUT'),
        NOW(),
        NULL
    );
