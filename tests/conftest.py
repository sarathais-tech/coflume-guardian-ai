import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
RUNTIME = RAIZ / "embarcado" / "runtime" / "guardia_runtime.h"
HOST_CPP = RAIZ / "tests" / "host_cpp"


def _compilador():
    for nome in ("g++", "clang++"):
        caminho = shutil.which(nome)
        if caminho:
            return caminho
    return None


@pytest.fixture(scope="session")
def compilador():
    cc = _compilador()
    if cc is None:
        pytest.skip("Nenhum compilador C++ (g++/clang++) encontrado; testes de equivalência pulados.")
    return cc


@pytest.fixture
def compilar_e_rodar(compilador, tmp_path):
    """Compila um .cpp de tests/host_cpp com os cabeçalhos de `pasta_modelo` e o executa."""

    def _rodar(fonte: str, pasta_modelo: Path) -> str:
        shutil.copy(RUNTIME, pasta_modelo / "guardia_runtime.h")
        exe = tmp_path / (Path(fonte).stem + ".out")
        cmd = [
            compilador, "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror",
            f"-I{pasta_modelo}", str(HOST_CPP / fonte), "-o", str(exe),
        ]
        r = subprocess.run(cmd, capture_output=True, text=True)
        assert r.returncode == 0, f"Falha ao compilar:\n{r.stderr}"
        r = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, f"Execução falhou:\n{r.stdout}\n{r.stderr}"
        return r.stdout

    return _rodar
