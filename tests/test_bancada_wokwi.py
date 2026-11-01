"""Bancada do Wokwi com a MLP candidata TREINADA (embarcado/bancada_wokwi).

Confere que a pasta versionada corresponde exatamente aos pesos do artefato,
que o sketch exportado é aprovado no PC e que nada usa o conjunto de teste.
"""

import json
import shutil
import subprocess

import pytest

from ferramentas import exportar_bancada, ler_bancada
from guardia.artefato import carregar_mlp_npz, sha256
from guardia.dados import carregar_split
from guardia.simulador import gerar_arquivo, parametros_da_versao
from tests.conftest import HOST_CPP, RAIZ

PASTA = RAIZ / "embarcado" / "bancada_wokwi"
TREINO = RAIZ / "resultados" / "sinteticos" / "treino_v2"
ARQUIVOS = ("sketch.ino", "guardia_modelo.h", "guardia_runtime.h", "vetores_teste.h", "diagram.json", "MODELO.json")


@pytest.fixture(scope="module")
def dados_v2(tmp_path_factory):
    """Gera sessoes_v2 e confirma que é o CSV registrado no split (senão pula: outra versão do NumPy)."""
    csv = tmp_path_factory.mktemp("d") / "sinteticos" / "sessoes_v2.csv"
    gerar_arquivo(csv, 4000, 2026, parametros_da_versao("sim-1.1"))
    split = RAIZ / "splits" / "split_v2.json"
    if sha256(csv) != carregar_split(split)["dados"]["sha256"]:
        pytest.skip("CSV gerado difere do registrado (versão do NumPy); conferência de sincronia pulada")
    return csv, split


def test_pasta_completa_e_rotulada():
    for nome in ARQUIVOS:
        assert (PASTA / nome).exists(), nome
    meta = json.loads((PASTA / "MODELO.json").read_text(encoding="utf-8"))
    assert meta["fonte_dados"] == "SINTETICO" and "NÃO é versão de produção" in meta["uso"]
    assert meta["teste_lacrado"] is True and meta["arquitetura"]["ocultas"] == [8]
    assert meta["arquitetura"]["n_parametros"] == 121
    modelo = carregar_mlp_npz(TREINO / "mlp_candidata.npz")
    assert meta["hash_sha256"] == modelo.hash()
    cab = (PASTA / "guardia_modelo.h").read_text(encoding="utf-8")
    assert f'#define GUARDIA_MODELO_HASH "{modelo.hash()}"' in cab and "#define GUARDIA_H2 0" in cab
    assert '#define GUARDIA_MODELO_USO "bancada (nao e versao de producao)"' in cab


def test_vetores_cobrem_as_tres_perguntas():
    v = json.loads((PASTA / "MODELO.json").read_text(encoding="utf-8"))["vetores"]
    assert v["aleatorios"] == 200 and v["validacao"] == 200
    assert all(n >= 60 for n in v["validacao_por_posicao"].values())


def test_indices_alternam_posicao():
    idx = exportar_bancada.indices_validacao(1800, 200)
    assert len(idx) == 200 and len(set(idx)) == 200
    assert {i % 3 for i in idx} == {0, 1, 2}


def test_sketch_e_runtime_sincronizados():
    sketch = (PASTA / "sketch.ino").read_text(encoding="utf-8")
    assert '#define BANCADA_AMBIENTE "wokwi"' in sketch
    assert sketch.endswith((RAIZ / "embarcado" / "bancada_ia" / "bancada_ia.ino").read_text(encoding="utf-8"))
    assert (PASTA / "guardia_runtime.h").read_bytes() == (RAIZ / "embarcado" / "runtime" / "guardia_runtime.h").read_bytes()


def test_diagrama_so_com_a_placa():
    d = json.loads((PASTA / "diagram.json").read_text(encoding="utf-8"))
    assert [p["id"] for p in d["parts"]] == ["esp"] and "esp32-s3" in d["parts"][0]["type"]


def test_exportacao_reproduz_a_pasta_versionada(dados_v2, tmp_path):
    csv, split = dados_v2
    origem = json.loads((TREINO / "ORIGEM.json").read_text(encoding="utf-8"))
    exportar_bancada.exportar(tmp_path, TREINO / "mlp_candidata.npz", TREINO / "validacao.json",
                              origem["validacao_json_sha256_publicado_pelo_ci"], csv, split)
    for nome in ARQUIVOS:
        assert (tmp_path / nome).read_bytes() == (PASTA / nome).read_bytes(), nome


def test_exportacao_recusa_validacao_adulterada(dados_v2, tmp_path):
    csv, split = dados_v2
    with pytest.raises(ValueError, match="não confere"):
        exportar_bancada.exportar(tmp_path, TREINO / "mlp_candidata.npz", TREINO / "validacao.json",
                                  "0" * 64, csv, split)


def test_sketch_exportado_aprovado_no_pc(compilador, tmp_path):
    for nome in ("guardia_modelo.h", "guardia_runtime.h", "vetores_teste.h"):
        shutil.copy(PASTA / nome, tmp_path / nome)
    shutil.copy(PASTA / "sketch.ino", tmp_path / "bancada_ia.ino")
    exe = tmp_path / "b.out"
    r = subprocess.run([compilador, "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror", "-x", "c++",
                        f"-I{HOST_CPP / 'stub_arduino'}", f"-I{tmp_path}", str(HOST_CPP / "bancada_host.cpp"),
                        "-o", str(exe)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    v = ler_bancada.ler(subprocess.run([str(exe)], capture_output=True, text=True, timeout=120).stdout)
    assert v["ambiente"] == "wokwi" and v["modelo_fonte"] == "SINTETICO"
    assert float(v["erro_p_max_aleatorios"]) < 1e-5 and float(v["erro_p_max_validacao"]) < 1e-5
    assert v["erro_features_max"] == "0" and v["falhas_inteiras"] == "0" and v["invalidos"] == "0"
    assert v["casos_entrada_corretos"] == v["casos_entrada_testados"]
    assert v["heap_variacao_prever_bytes"] == "0" and v["heap_variacao_montar_entrada_bytes"] == "0"
    assert v["resultado"] == "APROVADO_FUNCIONAL" and v["criterio_latencia"] == "NAO_AVALIADO"
