<?php
// API de consultas: crear (POST) y listar (GET).
// Responde siempre en JSON y con el código HTTP correcto.

// Nunca mostramos errores de PHP en la respuesta: podrían revelar rutas internas
ini_set('display_errors', '0');

header('Content-Type: application/json; charset=utf-8');

// Envía una respuesta JSON y termina el script.
// JSON_UNESCAPED_UNICODE evita que las tildes salgan escapadas (código unicode en vez de la letra).
// JSON_UNESCAPED_SLASHES evita que "/" salga como "\/" (el texto se devuelve tal cual).
function send_json(int $status, array $data): void
{
    http_response_code($status);
    echo json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

// Envía una respuesta de error de la API (nada se ha guardado).
function send_error(int $status, string $error_code, string $message): void
{
    send_json($status, [
        'ok' => false,
        'error_code' => $error_code,
        'message' => $message,
    ]);
}

// Conecta con PostgreSQL.
// Dentro de Docker el host es "db" y el puerto es 5432 (no 5433).
function get_connection(): PDO
{
    $dsn = 'pgsql:host=db;port=5432;dbname=' . getenv('POSTGRES_DB');
    return new PDO($dsn, getenv('POSTGRES_USER'), getenv('POSTGRES_PASSWORD'), [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        PDO::ATTR_TIMEOUT => 3,
    ]);
}

// Convierte una fila de la base de datos en el formato público de la API.
// Las fechas ya llegan como texto YYYY-MM-DD HH:MM:SS (sin microsegundos), ver la consulta SQL.
function format_consultation(array $row): array
{
    return [
        'id' => (int) $row['id'],
        'client_name' => $row['client_name'],
        'message' => $row['message'],
        'department' => $row['department'],
        'status' => $row['status'],
        'error_code' => $row['error_code'],
        'created_at' => $row['created_at'],
        'classified_at' => $row['classified_at'],
    ];
}

// Parte común de las consultas SELECT (columnas y JOINs).
// LEFT JOIN porque una consulta pending o error no tiene departamento,
// y una pending o classified no tiene tipo de error.
function consultation_select_sql(): string
{
    return 'SELECT c.id, c.client_name, c.message, d.name AS department, c.status,
                   e.code AS error_code,
                   to_char(c.created_at, \'YYYY-MM-DD HH24:MI:SS\') AS created_at,
                   to_char(c.classified_at, \'YYYY-MM-DD HH24:MI:SS\') AS classified_at
            FROM consultations c
            LEFT JOIN departments d ON d.id = c.department_id
            LEFT JOIN error_types e ON e.id = c.error_type_id';
}

// Devuelve todas las consultas, la más reciente primero.
function list_consultations(PDO $pdo): array
{
    $sql = consultation_select_sql() . ' ORDER BY c.created_at DESC, c.id DESC';
    $rows = $pdo->query($sql)->fetchAll();
    return array_map('format_consultation', $rows);
}

// Devuelve una consulta por su id (leída de la base de datos).
function get_consultation(PDO $pdo, int $id): array
{
    $stmt = $pdo->prepare(consultation_select_sql() . ' WHERE c.id = :id');
    $stmt->execute([':id' => $id]);
    return format_consultation($stmt->fetch());
}

// Valida un campo de texto: debe existir, ser texto, no quedar vacío y no pasarse de largo.
// Devuelve el texto recortado. Si falla, responde 422 y termina.
// El mensaje dice qué campo falla, pero nunca incluye el texto recibido.
function validate_text(array $data, string $field, int $max_length): string
{
    if (!array_key_exists($field, $data) || $data[$field] === null) {
        send_error(422, 'INVALID_INPUT', "$field is required");
    }
    if (!is_string($data[$field])) {
        send_error(422, 'INVALID_INPUT', "$field must be text");
    }

    $value = trim($data[$field]);

    if ($value === '') {
        send_error(422, 'INVALID_INPUT', "$field is required");
    }
    // PostgreSQL no admite el carácter nulo dentro de un texto
    if (str_contains($value, "\0")) {
        send_error(422, 'INVALID_INPUT', "$field has invalid characters");
    }
    // mb_strlen cuenta caracteres, no bytes (las tildes no cuentan doble)
    if (mb_strlen($value, 'UTF-8') > $max_length) {
        send_error(422, 'INVALID_INPUT', "$field is too long (max $max_length characters)");
    }

    return $value;
}

// Lee el cuerpo de la petición. Si no es JSON válido, responde 400 y termina.
function read_json_body(): array
{
    $data = json_decode((string) file_get_contents('php://input'), true);

    if (json_last_error() !== JSON_ERROR_NONE) {
        send_error(400, 'INVALID_JSON', 'Body is not valid JSON');
    }

    // Un JSON válido que no es un objeto (por ejemplo 5 o "hola") se trata
    // como un objeto vacío: la validación dirá que faltan los campos.
    return is_array($data) ? $data : [];
}

// Guarda una consulta nueva con estado pending y devuelve su id.
// Queda guardada antes de clasificar, así no se pierde si algo falla después.
function insert_pending_consultation(PDO $pdo, string $client_name, string $message): int
{
    $stmt = $pdo->prepare(
        "INSERT INTO consultations (client_name, message, status)
         VALUES (:client_name, :message, 'pending')
         RETURNING id"
    );
    $stmt->execute([':client_name' => $client_name, ':message' => $message]);
    return (int) $stmt->fetchColumn();
}

// Orden que ejecuta el clasificador, como lista de argumentos (sin shell, sin inyección de comandos)
const CLASSIFIER_COMMAND = ['python3', '/opt/classifier/classifier.py'];

// Tiempo máximo en segundos. Es mayor que los 10 s de Gemini: el clasificador tiene
// su propio tiempo y su reserva, este es solo un seguro.
const CLASSIFIER_TIMEOUT = 15;

// Ejecuta el clasificador pasando el mensaje por stdin (nunca por argumento).
// El proceso hereda el entorno del contenedor (CLASSIFIER_MODE, GEMINI_API_KEY, GEMINI_MODEL).
// Devuelve: timed_out (bool), exit_code (int), stdout (string), stderr (string).
function run_classifier(string $message): array
{
    $result = ['timed_out' => false, 'exit_code' => -1, 'stdout' => '', 'stderr' => ''];

    $descriptors = [
        0 => ['pipe', 'r'], // stdin del clasificador
        1 => ['pipe', 'w'], // stdout
        2 => ['pipe', 'w'], // stderr
    ];
    $process = proc_open(CLASSIFIER_COMMAND, $descriptors, $pipes);
    if (!is_resource($process)) {
        return $result;
    }

    // Escribimos el mensaje y cerramos stdin para que el clasificador sepa que terminó
    @fwrite($pipes[0], $message);
    fclose($pipes[0]);

    // Leemos stdout y stderr sin bloquear, vigilando el tiempo máximo
    stream_set_blocking($pipes[1], false);
    stream_set_blocking($pipes[2], false);
    $open = [$pipes[1], $pipes[2]];
    $deadline = microtime(true) + CLASSIFIER_TIMEOUT;

    while ($open) {
        $remaining = $deadline - microtime(true);
        if ($remaining <= 0) {
            $result['timed_out'] = true;
            break;
        }

        $read = $open;
        $write = null;
        $except = null;
        $seconds = (int) floor($remaining);
        $microseconds = (int) (($remaining - $seconds) * 1000000);
        if (stream_select($read, $write, $except, $seconds, $microseconds) === false) {
            break;
        }

        foreach ($read as $stream) {
            $chunk = fread($stream, 8192);
            if ($chunk === false || ($chunk === '' && feof($stream))) {
                // Este flujo terminó: lo quitamos de la lista
                $open = array_filter($open, fn($s) => $s !== $stream);
                continue;
            }
            if ($stream === $pipes[1]) {
                $result['stdout'] .= $chunk;
            } else {
                $result['stderr'] .= $chunk;
            }
        }
    }

    // Si se agotó el tiempo, matamos el proceso para que no quede colgado
    if ($result['timed_out']) {
        proc_terminate($process, 9);
    }
    fclose($pipes[1]);
    fclose($pipes[2]);
    $result['exit_code'] = proc_close($process);

    return $result;
}

// Busca el id de un departamento por su nombre. Devuelve null si no existe.
function find_department_id(PDO $pdo, string $name): ?int
{
    $stmt = $pdo->prepare('SELECT id FROM departments WHERE name = :name');
    $stmt->execute([':name' => $name]);
    $id = $stmt->fetchColumn();
    return $id === false ? null : (int) $id;
}

// Busca el id de un tipo de error por su código. Devuelve null si no existe.
function find_error_type_id(PDO $pdo, string $code): ?int
{
    $stmt = $pdo->prepare('SELECT id FROM error_types WHERE code = :code');
    $stmt->execute([':code' => $code]);
    $id = $stmt->fetchColumn();
    return $id === false ? null : (int) $id;
}

// Traduce el resultado del clasificador a los campos de la tabla.
// Devuelve: status, department_id y error_type_id (uno de los dos ids es siempre null).
function interpret_classifier_result(PDO $pdo, array $run): array
{
    // Tabla de casos de error: cualquier fallo acaba en un código de error_types
    $error_code = 'UNKNOWN';

    if ($run['timed_out']) {
        $error_code = 'AI_TIMEOUT';
    } elseif ($run['exit_code'] === 0) {
        $output = json_decode($run['stdout'], true);

        if (is_array($output) && ($output['ok'] ?? null) === true && is_string($output['department'] ?? null)) {
            // Solo vale un departamento que exista en la base de datos
            $department_id = find_department_id($pdo, $output['department']);
            if ($department_id !== null) {
                return ['status' => 'classified', 'department_id' => $department_id, 'error_type_id' => null];
            }
            $error_code = 'AI_INVALID_RESPONSE';
        } elseif (is_array($output) && ($output['ok'] ?? null) === false && is_string($output['error_code'] ?? null)) {
            // Solo vale un código que exista en error_types; si no, se queda UNKNOWN
            if (find_error_type_id($pdo, $output['error_code']) !== null) {
                $error_code = $output['error_code'];
            }
        }
    }

    $error_type_id = find_error_type_id($pdo, $error_code);
    if ($error_type_id === null) {
        // Sin ni siquiera UNKNOWN no podemos guardar un error coherente
        throw new RuntimeException('error type missing in database: ' . $error_code);
    }
    return ['status' => 'error', 'department_id' => null, 'error_type_id' => $error_type_id];
}

// Guarda el resultado de la clasificación en la consulta.
// La tabla exige coherencia: classified lleva departamento y no error, error lleva error y no departamento.
function save_classification(PDO $pdo, int $id, array $result): void
{
    $stmt = $pdo->prepare(
        'UPDATE consultations
         SET status = :status, department_id = :department_id,
             error_type_id = :error_type_id, classified_at = NOW()
         WHERE id = :id'
    );
    $stmt->execute([
        ':status' => $result['status'],
        ':department_id' => $result['department_id'],
        ':error_type_id' => $result['error_type_id'],
        ':id' => $id,
    ]);
}

// Cualquier excepción sin controlar acaba aquí.
// El detalle va al registro de PHP; el cliente solo recibe un mensaje genérico.
set_exception_handler(function (Throwable $e): void {
    error_log('consultations.php: ' . $e->getMessage());
    send_error(500, 'INTERNAL_ERROR', 'Internal error');
});

// Según el método HTTP decidimos qué hacer
$method = $_SERVER['REQUEST_METHOD'];

if ($method === 'GET') {
    send_json(200, [
        'ok' => true,
        'consultations' => list_consultations(get_connection()),
    ]);
}

if ($method === 'POST') {
    // 1. Leer el cuerpo y validar. Si falla, se responde y no se toca la base de datos
    $data = read_json_body();
    $client_name = validate_text($data, 'client_name', 100);
    $message = validate_text($data, 'message', 2000);

    // 2. Guardar como pending
    $pdo = get_connection();
    $id = insert_pending_consultation($pdo, $client_name, $message);

    // 3. Clasificar. El stderr del clasificador (por ejemplo "gemini failed: timeout")
    // va al registro de PHP, nunca a la respuesta
    $run = run_classifier($message);
    if (trim($run['stderr']) !== '') {
        error_log('classifier: ' . trim($run['stderr']));
    }

    // 4. Guardar el resultado. La petición tiene éxito (201) aunque la consulta quede en error
    $result = interpret_classifier_result($pdo, $run);
    save_classification($pdo, $id, $result);

    // 5. Responder con la consulta completa, leída de la base de datos
    send_json(201, ['ok' => true, 'consultation' => get_consultation($pdo, $id)]);
}

// Cualquier otro método no está permitido
header('Allow: GET, POST');
send_error(405, 'METHOD_NOT_ALLOWED', 'Method not allowed');
