<?php
// Devuelve el estado del entorno en JSON: versión de PHP, de Python y conexión a la BD.

header('Content-Type: application/json');

// Versión de PHP que ejecuta este archivo
$php_version = PHP_VERSION;

// Versión de Python (se ejecuta el comando dentro del contenedor)
$python_version = trim((string) shell_exec('python3 --version 2>&1'));

// Probamos la conexión a PostgreSQL.
// Dentro de Docker el host es "db" y el puerto es 5432 (no 5433).
$database_status = 'ok';
try {
    $dsn = 'pgsql:host=db;port=5432;dbname=' . getenv('POSTGRES_DB');
    new PDO($dsn, getenv('POSTGRES_USER'), getenv('POSTGRES_PASSWORD'), [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_TIMEOUT => 3,
    ]);
} catch (PDOException $e) {
    // No mostramos el mensaje de PDO: podría incluir datos sensibles
    $database_status = 'error';
    http_response_code(500);
}

echo json_encode([
    'php' => $php_version,
    'python' => $python_version,
    'database' => $database_status,
]);
