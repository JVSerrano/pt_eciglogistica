import io
import json
import os
import socket
import subprocess
import sys
import unittest
import urllib.error
from unittest import mock

import classifier

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "classifier.py")


class ClassifyTest(unittest.TestCase):
    def setUp(self):
        # Estos tests son de palabras clave: se fuerza el modo para no depender del entorno
        # y se apagan las trazas para que no ensucien la salida
        env = {"CLASSIFIER_MODE": "keywords", "CLASSIFIER_TRACE": "false"}
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)

    def department(self, message):
        # Ayuda: devuelve el departamento y comprueba que la respuesta es correcta
        result = classifier.classify(message)
        self.assertTrue(result["ok"])
        return result["department"]

    def test_thanks(self):
        self.assertEqual(self.department("gracias por todo"), "Agradecimientos")

    def test_sales(self):
        self.assertEqual(
            self.department("Quiero información sobre los precios"), "Comercial"
        )

    def test_support(self):
        self.assertEqual(
            self.department("La aplicación no me deja iniciar sesión"),
            "Soporte Técnico",
        )

    def test_keywords_mode_reports_keywords_method(self):
        self.assertEqual(classifier.classify("gracias por todo")["method"], "keywords")

    def test_empty_message(self):
        expected = {"ok": False, "error_code": "EMPTY_MESSAGE"}
        self.assertEqual(classifier.classify(""), expected)

    def test_only_spaces(self):
        expected = {"ok": False, "error_code": "EMPTY_MESSAGE"}
        self.assertEqual(classifier.classify("   \n\t "), expected)

    def test_no_keywords_uses_default(self):
        self.assertEqual(self.department("hola buenos dias"), "Soporte Técnico")

    def test_tie_goes_to_first_department(self):
        # Una coincidencia de Agradecimientos y una de Soporte Técnico
        self.assertEqual(
            self.department("gracias, pero tengo un problema"), "Soporte Técnico"
        )

    def test_more_matches_wins(self):
        # Dos de Agradecimientos contra una de Soporte Técnico
        self.assertEqual(
            self.department("gracias, excelente, pero tengo un problema"),
            "Agradecimientos",
        )

    def test_uppercase_and_accents_do_not_matter(self):
        self.assertEqual(self.department("PRECIOS"), "Comercial")
        self.assertEqual(self.department("précios"), "Comercial")

    def test_whole_words_only(self):
        # "error" dentro de "terror" no debe contar
        self.assertEqual(self.department("terror"), "Soporte Técnico")
        # "superoferta" va a Comercial porque está en la lista como palabra propia,
        # no porque "oferta" coincida en mitad de la palabra
        self.assertEqual(self.department("superoferta"), "Comercial")

    def test_plural_offers_message_goes_to_sales(self):
        # Mensaje real que falló en el frontend: "ofertas" (plural) debe contar como "oferta"
        self.assertEqual(
            self.department("Necesito las nuevas ofertas para los socios de A Coruña"),
            "Comercial",
        )

    def test_plurals_of_sales_words(self):
        # Cada plural debe dar el mismo resultado que su singular
        for message in ["ofertas", "descuentos", "tarifas", "presupuestos", "precios"]:
            with self.subTest(message=message):
                self.assertEqual(self.department(message), "Comercial")

    def test_plurals_of_support_words(self):
        # Soporte Técnico es el departamento por defecto, así que se enfrenta a Comercial:
        # dos plurales de Soporte (2 coincidencias) ganan a un precio (1 coincidencia).
        # Si los plurales no se reconocieran, ganaría Comercial.
        for plurals in ["errores y problemas", "usuarios y errores", "problemas y usuarios"]:
            with self.subTest(plurals=plurals):
                self.assertEqual(
                    self.department("precio, " + plurals), "Soporte Técnico"
                )

    def test_plural_of_thanks_word(self):
        self.assertEqual(self.department("excelentes noticias"), "Agradecimientos")

    def test_multiword_phrase_still_matches(self):
        self.assertEqual(self.department("no puedo entrar"), "Soporte Técnico")
        self.assertEqual(self.department("buen trabajo"), "Agradecimientos")

    def test_keyword_must_start_the_word(self):
        # "error" en mitad de "terror" y "precio" en mitad de "aprecio" no cuentan
        self.assertEqual(self.department("aprecio"), "Soporte Técnico")

    def test_department_names_match_database(self):
        names = [name for name, _ in classifier.KEYWORDS]
        self.assertEqual(
            names, ["Soporte Técnico", "Comercial", "Agradecimientos"]
        )


FAKE_KEY = "fake-key-for-tests"


def fake_response(text):
    # Simula la respuesta de Gemini con el formato real de generateContent
    body = {"candidates": [{"content": {"parts": [{"text": text}]}}]}
    response = mock.MagicMock()
    response.__enter__.return_value.read.return_value = json.dumps(body).encode("utf-8")
    return response


class GeminiTest(unittest.TestCase):
    def setUp(self):
        # Modo gemini con clave y modelo falsos: no se necesita red ni clave real
        env = {
            "CLASSIFIER_MODE": "gemini",
            "CLASSIFIER_TRACE": "false",
            "GEMINI_API_KEY": FAKE_KEY,
            "GEMINI_MODEL": "fake-model",
        }
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)

    def classify_with(self, **urlopen_args):
        # Ejecuta classify con urlopen simulado. Devuelve (resultado, stderr, simulacro)
        with mock.patch("urllib.request.urlopen", **urlopen_args) as fake:
            with mock.patch("sys.stderr", new_callable=io.StringIO) as err:
                result = classifier.classify("me cobrasteis dos veces este mes")
        return result, err.getvalue(), fake

    def test_valid_answer_is_used(self):
        result, err, _ = self.classify_with(return_value=fake_response("Comercial"))
        self.assertEqual(
            result, {"ok": True, "department": "Comercial", "method": "gemini"}
        )
        self.assertEqual(err, "")

    def test_answer_ignores_case_spaces_and_accents(self):
        result, _, _ = self.classify_with(
            return_value=fake_response("  soporte tecnico\n")
        )
        self.assertEqual(result["department"], "Soporte Técnico")

    def test_invalid_answer_uses_keywords(self):
        # Sin palabras clave en el mensaje, la reserva da el departamento por defecto
        result, err, _ = self.classify_with(return_value=fake_response("Ventas"))
        expected = {"ok": True, "department": "Soporte Técnico", "method": "keywords"}
        self.assertEqual(result, expected)
        self.assertIn("gemini failed: invalid answer", err)

    def test_invalid_answer_fallback_uses_keywords_result(self):
        with mock.patch("urllib.request.urlopen", return_value=fake_response("Ventas")):
            with mock.patch("sys.stderr", new_callable=io.StringIO):
                result = classifier.classify("quiero saber el precio")
        self.assertEqual(result["department"], "Comercial")

    def test_timeout_uses_keywords(self):
        result, err, _ = self.classify_with(side_effect=socket.timeout())
        self.assertTrue(result["ok"])
        self.assertIn("gemini failed: timeout", err)

    def test_timeout_wrapped_in_urlerror_uses_keywords(self):
        error = urllib.error.URLError(socket.timeout())
        result, err, _ = self.classify_with(side_effect=error)
        self.assertTrue(result["ok"])
        self.assertIn("gemini failed: timeout", err)

    def test_network_error_uses_keywords(self):
        error = urllib.error.URLError("no route")
        result, err, _ = self.classify_with(side_effect=error)
        self.assertTrue(result["ok"])
        self.assertIn("gemini failed: network", err)

    def test_http_error_uses_keywords(self):
        error = urllib.error.HTTPError("http://x", 429, "Too Many", {}, None)
        result, err, _ = self.classify_with(side_effect=error)
        self.assertTrue(result["ok"])
        self.assertIn("gemini failed: http 429", err)

    def test_response_without_text_uses_keywords(self):
        response = mock.MagicMock()
        response.__enter__.return_value.read.return_value = b'{"candidates": []}'
        result, err, _ = self.classify_with(return_value=response)
        self.assertTrue(result["ok"])
        self.assertIn("gemini failed: no text in response", err)

    def test_no_key_uses_keywords_without_calling_gemini(self):
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            result, err, fake = self.classify_with(return_value=fake_response("Comercial"))
        self.assertEqual(result["department"], "Soporte Técnico")
        self.assertIn("gemini failed: no api key", err)
        fake.assert_not_called()

    def test_empty_message_does_not_call_gemini(self):
        with mock.patch("urllib.request.urlopen") as fake:
            result = classifier.classify("   ")
        self.assertEqual(result, {"ok": False, "error_code": "EMPTY_MESSAGE"})
        fake.assert_not_called()

    def test_key_goes_in_header_and_never_in_url_or_stderr(self):
        _, err, fake = self.classify_with(
            side_effect=urllib.error.HTTPError("http://x", 400, "Bad", {}, None)
        )
        request = fake.call_args[0][0]
        self.assertEqual(request.get_header("X-goog-api-key"), FAKE_KEY)
        self.assertNotIn(FAKE_KEY, request.full_url)
        self.assertNotIn(FAKE_KEY, err)
        self.assertNotIn("cobrasteis", err)

    def test_request_uses_temperature_zero_and_separate_message(self):
        _, _, fake = self.classify_with(return_value=fake_response("Comercial"))
        request = fake.call_args[0][0]
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(body["generationConfig"]["temperature"], 0)
        sent = body["contents"][0]["parts"][0]["text"]
        self.assertEqual(sent, "me cobrasteis dos veces este mes")
        self.assertNotIn("cobrasteis", json.dumps(body["systemInstruction"]))


class ModeTest(unittest.TestCase):
    def classify_in_mode(self, mode):
        env = {
            "GEMINI_API_KEY": FAKE_KEY,
            "GEMINI_MODEL": "fake-model",
            "CLASSIFIER_TRACE": "false",
        }
        if mode is not None:
            env["CLASSIFIER_MODE"] = mode
        with mock.patch.dict(os.environ, env):
            if mode is None:
                os.environ.pop("CLASSIFIER_MODE", None)
            with mock.patch("urllib.request.urlopen") as fake:
                result = classifier.classify("precio")
        return result, fake

    def test_keywords_mode_does_not_call_gemini(self):
        result, fake = self.classify_in_mode("keywords")
        self.assertEqual(result["department"], "Comercial")
        fake.assert_not_called()

    def test_missing_mode_is_keywords(self):
        result, fake = self.classify_in_mode(None)
        self.assertEqual(result["department"], "Comercial")
        fake.assert_not_called()

    def test_strange_mode_is_keywords(self):
        result, fake = self.classify_in_mode("banana")
        self.assertEqual(result["department"], "Comercial")
        fake.assert_not_called()


class CommandLineTest(unittest.TestCase):
    def run_script(self, message, trace="false"):
        # Ejecuta el script igual que lo hará PHP: mensaje por stdin
        # Se fuerza keywords para que el test no use red aunque el entorno diga gemini
        env = dict(os.environ, CLASSIFIER_MODE="keywords", CLASSIFIER_TRACE=trace)
        return subprocess.run(
            [sys.executable, SCRIPT],
            input=message.encode("utf-8"),
            capture_output=True,
            env=env,
        )

    def test_output_keeps_accents_and_exit_code_zero(self):
        process = self.run_script("no funciona")
        self.assertEqual(process.returncode, 0)
        output = process.stdout.decode("utf-8").strip()
        expected = '{"ok": true, "department": "Soporte Técnico", "method": "keywords"}'
        self.assertEqual(output, expected)

    def test_error_also_exits_with_zero(self):
        process = self.run_script("")
        self.assertEqual(process.returncode, 0)
        output = process.stdout.decode("utf-8").strip()
        self.assertEqual(output, '{"ok": false, "error_code": "EMPTY_MESSAGE"}')

    def test_trace_goes_to_stderr_and_stdout_does_not_change(self):
        # Con trazas, el JSON de stdout es idéntico y la traza va solo a stderr
        process = self.run_script("no funciona", trace="true")
        output = process.stdout.decode("utf-8").strip()
        expected = '{"ok": true, "department": "Soporte Técnico", "method": "keywords"}'
        self.assertEqual(output, expected)
        error = process.stderr.decode("utf-8")
        self.assertTrue(error.startswith("trace mode=keywords"))

    def test_trace_off_leaves_stderr_empty(self):
        process = self.run_script("no funciona", trace="false")
        self.assertEqual(process.stderr, b"")


class TraceTest(unittest.TestCase):
    # Tests de las trazas del SPEC 08
    MESSAGE = "me cobrasteis dos veces, quiero un descuento"

    def setUp(self):
        env = {
            "CLASSIFIER_MODE": "keywords",
            "CLASSIFIER_TRACE": "true",
            "GEMINI_API_KEY": FAKE_KEY,
            "GEMINI_MODEL": "fake-model",
        }
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_classify(self, message=None, **urlopen_args):
        # Devuelve (resultado, stderr). Gemini va simulado, nunca hay red
        if message is None:
            message = self.MESSAGE
        with mock.patch("urllib.request.urlopen", **urlopen_args):
            with mock.patch("sys.stderr", new_callable=io.StringIO) as err:
                result = classifier.classify(message)
        return result, err.getvalue()

    def trace_lines(self, err):
        return [line for line in err.splitlines() if line.startswith("trace ")]

    def test_keywords_mode_trace(self):
        _, err = self.run_classify()
        self.assertRegex(
            err,
            r"^trace mode=keywords method=keywords department=Comercial "
            r"matches=descuento ms=\d+\n$",
        )

    def test_keywords_mode_lists_every_match(self):
        _, err = self.run_classify("quiero una oferta y un descuento")
        self.assertIn("matches=oferta,descuento ", err)

    def test_keywords_mode_without_matches(self):
        _, err = self.run_classify("hola")
        self.assertRegex(
            err,
            r"^trace mode=keywords method=keywords department=Soporte Técnico "
            r"matches=none ms=\d+\n$",
        )

    def test_gemini_answer_trace_compares_with_keywords(self):
        os.environ["CLASSIFIER_MODE"] = "gemini"
        # Gemini dice Agradecimientos y las palabras clave habrían dicho Comercial
        _, err = self.run_classify(return_value=fake_response("Agradecimientos"))
        self.assertRegex(
            err,
            r"^trace mode=gemini method=gemini department=Agradecimientos "
            r"gemini=Agradecimientos keywords=Comercial ms=\d+\n$",
        )

    def test_gemini_failure_trace_has_reason_and_fallback(self):
        os.environ["CLASSIFIER_MODE"] = "gemini"
        _, err = self.run_classify(side_effect=socket.timeout())
        # El aviso de siempre se mantiene y se añade una sola traza
        self.assertIn("gemini failed: timeout\n", err)
        lines = self.trace_lines(err)
        self.assertEqual(len(lines), 1)
        self.assertRegex(
            lines[0],
            r"^trace mode=gemini method=keywords department=Comercial "
            r"reason=timeout matches=descuento ms=\d+$",
        )

    def test_gemini_failure_without_key_has_reason(self):
        os.environ["CLASSIFIER_MODE"] = "gemini"
        os.environ["GEMINI_API_KEY"] = ""
        _, err = self.run_classify()
        self.assertIn("reason=no api key", err)

    def test_one_trace_line_per_classification(self):
        for mode in ("keywords", "gemini"):
            os.environ["CLASSIFIER_MODE"] = mode
            _, err = self.run_classify(return_value=fake_response("Comercial"))
            self.assertEqual(len(self.trace_lines(err)), 1)

    def test_trace_off_writes_nothing(self):
        for value in ("false", "", "1", "yes"):
            os.environ["CLASSIFIER_TRACE"] = value
            _, err = self.run_classify()
            self.assertEqual(err, "")

    def test_trace_missing_variable_writes_nothing(self):
        os.environ.pop("CLASSIFIER_TRACE")
        _, err = self.run_classify()
        self.assertEqual(err, "")

    def test_trace_switch_ignores_case(self):
        os.environ["CLASSIFIER_TRACE"] = "TRUE"
        _, err = self.run_classify()
        self.assertTrue(err.startswith("trace "))

    def test_trace_off_keeps_old_stderr_when_gemini_fails(self):
        os.environ["CLASSIFIER_MODE"] = "gemini"
        os.environ["CLASSIFIER_TRACE"] = "false"
        _, err = self.run_classify(side_effect=socket.timeout())
        self.assertEqual(err, "gemini failed: timeout\n")

    def test_trace_never_has_key_or_message(self):
        cases = [
            ("keywords", {}),
            ("gemini", {"return_value": fake_response("Comercial")}),
            ("gemini", {"side_effect": socket.timeout()}),
            ("gemini", {"side_effect": urllib.error.HTTPError("http://x", 400, "Bad", {}, None)}),
        ]
        for mode, urlopen_args in cases:
            os.environ["CLASSIFIER_MODE"] = mode
            _, err = self.run_classify(**urlopen_args)
            self.assertIn("trace ", err)
            self.assertNotIn(FAKE_KEY, err)
            self.assertNotIn("cobrasteis", err)
            self.assertNotIn(self.MESSAGE, err)

    def test_trace_does_not_change_the_department(self):
        cases = [
            ("keywords", {}),
            ("gemini", {"return_value": fake_response("Agradecimientos")}),
            ("gemini", {"side_effect": socket.timeout()}),
        ]
        for mode, urlopen_args in cases:
            os.environ["CLASSIFIER_MODE"] = mode
            os.environ["CLASSIFIER_TRACE"] = "true"
            with_trace, _ = self.run_classify(**urlopen_args)
            os.environ["CLASSIFIER_TRACE"] = "false"
            without_trace, _ = self.run_classify(**urlopen_args)
            self.assertEqual(with_trace, without_trace)

    def test_empty_message_writes_no_trace(self):
        _, err = self.run_classify("   ")
        self.assertEqual(err, "")

    def test_keywords_decision_matches_classify_by_keywords(self):
        for message in ["gracias", "hola", "no puedo entrar", "oferta y descuento"]:
            department, _ = classifier.keywords_decision(message)
            self.assertEqual(department, classifier.classify_by_keywords(message))


if __name__ == "__main__":
    unittest.main()
