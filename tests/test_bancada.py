"""Testes da bancada: gerador, sketch (compilado e executado no PC) e leitor do log."""

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


def rodar_sketch(compilador, pasta, tmp_path, *defines, fonte="bancada_host.cpp") -> str:
    exe = tmp_path / (fonte + ".out")
    cmd = [compilador, "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror", "-x", "c++",
           *defines, f"-I{HOST_CPP / 'stub_arduino'}", f"-I{pasta}", str(HOST_CPP / fonte), "-o", str(exe)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return subprocess.run([str(exe)], capture_output=True, text=True, timeout=120).stdout


def test_gerador_cria_arquivos_do_sketch(pasta_bancada):
    for nome in ("guardia_modelo.h", "guardia_runtime.h", "vetores_teste.h"):
        assert (pasta_bancada / nome).exists()
    assert not (pasta_bancada / "MODELO.json").exists()
    assert '"ALEATORIO"' in (pasta_bancada / "guardia_modelo.h").read_text(encoding="utf-8")


def test_sketch_na_placa_avalia_latencia(compilador, pasta_bancada, tmp_path):
    v = ler_bancada.ler(rodar_sketch(compilador, pasta_bancada, tmp_path))
    assert v["ambiente"] == "placa" and v["modelo_fonte"] == "ALEATORIO"
    assert float(v["erro_p_max"]) < 1e-5
    assert v["casos_entrada_corretos"] == v["casos_entrada_testados"] == "46"
    assert v["heap_variacao_prever_bytes"] == "0" and v["heap_variacao_montar_entrada_bytes"] == "0"
    for criterio in ("criterio_equivalencia", "criterio_entradas", "criterio_sem_alocacao", "criterio_latencia"):
        assert v[criterio] == "APROVADO", criterio
    assert v["resultado"] == "APROVADO"
    assert "Pesos ALEATÓRIOS" in ler_bancada.relatorio(v)


def test_sketch_no_wokwi_nao_avalia_latencia(compilador, pasta_bancada, tmp_path):
    v = ler_bancada.ler(rodar_sketch(compilador, pasta_bancada, tmp_path, '-DBANCADA_AMBIENTE="wokwi"'))
    assert v["ambiente"] == "wokwi"
    assert v["criterio_latencia"] == "NAO_AVALIADO"
    assert v["latencia_valida"].startswith("nao")
    assert v["resultado"] == "APROVADO_FUNCIONAL"
    md = ler_bancada.relatorio(v)
    assert "Latência simulada, apenas indicativa" in md and "Critério (< 1000 µs" not in md


def test_alocacao_dinamica_seria_detectada(compilador, tmp_path):
    """O stub mede alocações reais: confirma que o critério de heap não é trivialmente verdadeiro."""
    fonte = tmp_path / "aloca.cpp"
    fonte.write_text(
        '#include "Arduino.h"\n#include <vector>\n'
        "int main() { uint32_t a = ESP.getFreeHeap(); std::vector<char>* v = new std::vector<char>(4096);"
        " uint32_t b = ESP.getFreeHeap(); std::printf(\"%ld\\n\", (long)a - (long)b); delete v; return 0; }\n",
        encoding="utf-8",
    )
    exe = tmp_path / "aloca.out"
    from tests.conftest import _compilador

    r = subprocess.run([_compilador(), "-std=c++17", "-O0", f"-I{HOST_CPP / 'stub_arduino'}", str(fonte), "-o", str(exe)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert int(subprocess.run([str(exe)], capture_output=True, text=True).stdout) >= 4096


def test_leitor_rejeita_log_incompleto_ou_antigo():
    with pytest.raises(ValueError, match="incompleto"):
        ler_bancada.ler("BANCADA,inicio,guardia_bancada_v2\nBANCADA,erro_p_max,0\n")
    with pytest.raises(ValueError, match="outra versão"):
        ler_bancada.ler("BANCADA,inicio,guardia_bancada_v1\nBANCADA,fim,ok\n")
