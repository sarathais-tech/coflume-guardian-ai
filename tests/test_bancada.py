"""Testes do teste de bancada: gerador, sketch (compilado no PC) e leitor do log."""

import shutil
import subprocess

import pytest

from ferramentas import gerar_bancada, ler_bancada
from tests.conftest import HOST_CPP, RAIZ

SKETCH = RAIZ / "embarcado" / "bancada_ia" / "bancada_ia.ino"


@pytest.fixture
def pasta_bancada(tmp_path):
    pasta = tmp_path / "bancada"
    assert gerar_bancada.main(["--semente", "2026", "--saida", str(pasta)]) == 0
    shutil.copy(SKETCH, pasta / "bancada_ia.ino")
    return pasta


def test_gerador_cria_arquivos_do_sketch(pasta_bancada):
    for nome in ("guardia_modelo.h", "guardia_runtime.h", "vetores_teste.h"):
        assert (pasta_bancada / nome).exists()
    assert not (pasta_bancada / "MODELO.json").exists()
    assert '"ALEATORIO"' in (pasta_bancada / "guardia_modelo.h").read_text(encoding="utf-8")


def test_sketch_roda_no_pc_e_e_aprovado(compilador, pasta_bancada, tmp_path):
    exe = tmp_path / "bancada.out"
    cmd = [
        compilador, "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror", "-x", "c++",
        f"-I{HOST_CPP / 'stub_arduino'}", f"-I{pasta_bancada}",
        str(HOST_CPP / "bancada_host.cpp"), "-o", str(exe),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    saida = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120).stdout

    v = ler_bancada.ler(saida)
    assert v["modelo_fonte"] == "ALEATORIO"
    assert float(v["erro_p_max"]) < 1e-5
    assert v["criterio_equivalencia"] == "APROVADO"
    assert v["resultado"] == "APROVADO"
    md = ler_bancada.relatorio(v)
    assert "Pesos ALEATÓRIOS" in md


def test_leitor_rejeita_log_incompleto():
    with pytest.raises(ValueError):
        ler_bancada.ler("BANCADA,inicio,guardia_bancada_v1\nBANCADA,erro_p_max,0\n")
