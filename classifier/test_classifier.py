import os
import subprocess
import sys
import unittest

import classifier

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "classifier.py")


class ClassifyTest(unittest.TestCase):
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
        self.assertEqual(self.department("preciosisimo"), "Soporte Técnico")

    def test_department_names_match_database(self):
        names = [name for name, _ in classifier.KEYWORDS]
        self.assertEqual(
            names, ["Soporte Técnico", "Comercial", "Agradecimientos"]
        )


class CommandLineTest(unittest.TestCase):
    def run_script(self, message):
        # Ejecuta el script igual que lo hará PHP: mensaje por stdin
        return subprocess.run(
            [sys.executable, SCRIPT],
            input=message.encode("utf-8"),
            capture_output=True,
        )

    def test_output_keeps_accents_and_exit_code_zero(self):
        process = self.run_script("no funciona")
        self.assertEqual(process.returncode, 0)
        output = process.stdout.decode("utf-8").strip()
        self.assertEqual(output, '{"ok": true, "department": "Soporte Técnico"}')

    def test_error_also_exits_with_zero(self):
        process = self.run_script("")
        self.assertEqual(process.returncode, 0)
        output = process.stdout.decode("utf-8").strip()
        self.assertEqual(output, '{"ok": false, "error_code": "EMPTY_MESSAGE"}')


if __name__ == "__main__":
    unittest.main()
