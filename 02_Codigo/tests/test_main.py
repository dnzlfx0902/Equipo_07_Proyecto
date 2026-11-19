import json
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


def test_terminal():
    with TemporaryDirectory() as carpeta:
        ruta = Path(carpeta)
        shutil.copy(Path(__file__).parents[1] / "main.py", ruta)

        def ejecutar(*comandos):
            return subprocess.run(
                [sys.executable, "main.py"], cwd=ruta, text=True,
                input="\n".join((*comandos, "salir", "")),
                capture_output=True, check=True, timeout=5,
            ).stdout

        salida = ejecutar(
            "help", "crear --help", 'crear carpeta "Mis notas"',
            'crear archivo "Mis notas/nota.txt"',
            'modificar archivo "Mis notas/nota.txt"', "s", "Contenido",
            'crear archivo "Mis notas/nota.txt"',
            'modificar archivo "Mis notas/nota.txt"', "n",
            'borrar archivo "Mis notas/nota.txt"', "n",
            'modificar carpeta "Mis notas" notas',
            'crear usuario "Ana María"', 'modificar usuario "Ana María" Ana',
        )
        assert "Uso: crear archivo|carpeta|usuario NOMBRE" in salida
        assert salida.count("Error:") == 1
        assert salida.count("Operación cancelada.") == 2
        assert (ruta / "notas/nota.txt").read_text() == "Contenido"
        assert json.loads((ruta / "usuarios.json").read_text()) == ["Ana"]
        salida = ejecutar("listar usuarios", "borrar usuario Ana", "s",
                          "borrar archivo notas/nota.txt", "s", "borrar carpeta notas", "s")
        assert "Ana\n" in salida and "Error:" not in salida
        assert not (ruta / "notas").exists()
        assert "No hay usuarios." in ejecutar("listar usuarios")


if __name__ == "__main__":
    test_terminal()
