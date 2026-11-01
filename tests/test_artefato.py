"""Conferência do artefato do treino: ZIP, pesos .npz e previsões contra validacao.json.

Usa modelos e artefatos FICTÍCIOS gerados no próprio teste.
"""

import io
import json
import zipfile

import numpy as np
import pytest

from guardia import metricas
from guardia.artefato import (
    ARQUIVOS_ESPERADOS,
    carregar_mlp_npz,
    carregar_validacao,
    conferir_com_validacao,
    extrair_zip,
    sha256,
)
from guardia.inferencia_ref import ModeloMLP, prever
from guardia.dados import criar_split, salvar_split
from guardia.simulador import gerar_arquivo, parametros_da_versao
from guardia.treino import preparar
from guardia.artefato import _entrada


def salvar_npz(modelo, caminho):
    np.savez(caminho, media=modelo.media, desvio=modelo.desvio,
             **{f"W{i}": W for i, (W, _) in enumerate(modelo.camadas)},
             **{f"b{i}": b for i, (_, b) in enumerate(modelo.camadas)})


@pytest.fixture(scope="module")
def cenario(tmp_path_factory):
    pasta = tmp_path_factory.mktemp("art")
    csv = pasta / "sinteticos" / "s.csv"
    gerar_arquivo(csv, 300, 2026, parametros_da_versao("sim-1.1"))
    split = pasta / "split.json"
    salvar_split(criar_split(csv, versao="split_teste"), split)
    d = preparar(csv, split)
    modelo = ModeloMLP.aleatorio(5, (8,))
    p = np.array([prever(modelo, _entrada(x)) for x in d.X_va])
    validacao = {"modelos": {"mlp": {"escolhido": {"arquitetura": [8], "n_parametros": 121}, "semente_candidata": 2026,
                                     "validacao": {"metricas": metricas.calcular(d.y_va, p, d.p_real_va)}}}}
    salvar_npz(modelo, pasta / "m.npz")
    return pasta, modelo, validacao, d


def test_npz_ida_e_volta(cenario):
    pasta, modelo, _, _ = cenario
    lido = carregar_mlp_npz(pasta / "m.npz")
    assert lido.hash() == modelo.hash() and lido.ocultas == (8,) and lido.metadados["fonte"] == "SINTETICO"


def test_npz_com_chaves_estranhas_e_recusado(tmp_path):
    np.savez(tmp_path / "x.npz", media=np.zeros(9), desvio=np.ones(9), W0=np.zeros((8, 13)), b0=np.zeros(8),
             W1=np.zeros((1, 8)), b1=np.zeros(1), extra=np.zeros(1))
    with pytest.raises(ValueError, match="Chaves inesperadas"):
        carregar_mlp_npz(tmp_path / "x.npz")


def test_conferencia_aprova_o_modelo_correto(cenario):
    _, modelo, validacao, d = cenario
    c = conferir_com_validacao(modelo, validacao, d.X_va, d.y_va, d.p_real_va)
    assert c["diferenca_max"] < 1e-9 and c["arquitetura"] == [8] and c["n_parametros"] == 121


def test_conferencia_recusa_arquitetura_ou_pesos_diferentes(cenario):
    _, modelo, validacao, d = cenario
    with pytest.raises(ValueError, match="Arquitetura"):
        conferir_com_validacao(ModeloMLP.aleatorio(5, (16,)), validacao, d.X_va, d.y_va, d.p_real_va)
    outro = ModeloMLP.aleatorio(6, (8,))
    with pytest.raises(ValueError, match="divergem"):
        conferir_com_validacao(outro, validacao, d.X_va, d.y_va, d.p_real_va)


def _zip(tmp_path, nomes, extra=None):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for n in nomes:
            z.writestr(n, "conteudo")
        if extra:
            z.writestr(extra, "x")
    caminho = tmp_path / "a.zip"
    caminho.write_bytes(buf.getvalue())
    return caminho


def test_zip_confere_sha_e_conteudo(tmp_path):
    caminho = _zip(tmp_path, ARQUIVOS_ESPERADOS)
    hashes = extrair_zip(caminho, sha256(caminho), tmp_path / "x")
    assert set(hashes) == set(ARQUIVOS_ESPERADOS)
    with pytest.raises(ValueError, match="não confere"):
        extrair_zip(caminho, "0" * 64, tmp_path / "y")


def test_zip_incompleto_ou_inseguro(tmp_path):
    caminho = _zip(tmp_path, ARQUIVOS_ESPERADOS[:2])
    with pytest.raises(ValueError, match="ausentes"):
        extrair_zip(caminho, sha256(caminho), tmp_path / "x")
    caminho = _zip(tmp_path, ARQUIVOS_ESPERADOS, extra="../fora.txt")
    with pytest.raises(ValueError, match="inseguro"):
        extrair_zip(caminho, sha256(caminho), tmp_path / "z")


def test_validacao_com_sha_errado(tmp_path):
    caminho = tmp_path / "v.json"
    caminho.write_text(json.dumps({"a": 1}), encoding="utf-8")
    assert carregar_validacao(caminho, sha256(caminho)) == {"a": 1}
    with pytest.raises(ValueError, match="não confere"):
        carregar_validacao(caminho, "f" * 64)
