"""Testes do exportador C++ (sem compilar)."""

import datetime as dt
import json
import re

import numpy as np
import pytest

from guardia import contrato as C
from guardia.exportar.mlp_cpp import exportar, gerar_cabecalho_modelo, identificador
from guardia.features import montar_entrada
from guardia.inferencia_ref import ModeloMLP, prever

DATA = dt.date(2026, 10, 28)


def test_modelo_padrao_tem_369_parametros():
    assert ModeloMLP.aleatorio(1).n_parametros == 369


def test_identificador():
    m = ModeloMLP.aleatorio(1)
    assert re.fullmatch(r"mlp16x8-aleat-20261028-[0-9a-f]{8}", identificador(m, DATA))
    m.metadados["fonte"] = "SINTETICO"
    assert identificador(m, DATA).startswith("mlp16x8-sint-")


def test_fonte_invalida_e_rejeitada():
    m = ModeloMLP.aleatorio(1)
    m.metadados["fonte"] = "QUALQUER"
    with pytest.raises(ValueError):
        identificador(m, DATA)


def test_hash_muda_com_qualquer_peso():
    a, b = ModeloMLP.aleatorio(1), ModeloMLP.aleatorio(1)
    assert a.hash() == b.hash()
    b.camadas[1][0][3, 2] += np.float32(1e-6)
    assert a.hash() != b.hash()


def test_floats_exportados_reconstroem_float32_exato():
    m = ModeloMLP.aleatorio(3)
    cab = gerar_cabecalho_modelo(m, "x")
    bloco = cab.split("GUARDIA_W_O1")[1].split(";")[0].split("=", 1)[1]
    valores = np.array([float(v) for v in re.findall(r"(-?[\d.]+(?:e[-+]?\d+)?)f", bloco)], dtype=np.float32)
    assert np.array_equal(valores, m.camadas[0][0].reshape(-1))


def test_desvio_zero_vira_um():
    m = ModeloMLP.aleatorio(1)
    desvio = m.desvio.copy()
    desvio[2] = 0.0
    m2 = ModeloMLP(m.camadas, m.media, desvio)
    assert m2.desvio[2] == 1.0


def test_formatos_invalidos():
    m = ModeloMLP.aleatorio(1)
    with pytest.raises(ValueError):
        ModeloMLP(m.camadas[:1], m.media, m.desvio)  # sem camada oculta
    W, b = m.camadas[0]
    with pytest.raises(ValueError):
        ModeloMLP([(W[:, :12], b)] + m.camadas[1:], m.media, m.desvio)
    nan = m.media.copy()
    nan[0] = np.nan
    with pytest.raises(ValueError):
        ModeloMLP(m.camadas, nan, m.desvio)


def test_saida_sempre_entre_zero_e_um():
    m = ModeloMLP.aleatorio(5)
    for ini in range(3):
        for cat in range(4):
            for niv in range(3):
                p = prever(m, montar_entrada([], ini, cat, niv))
                assert 0.0 <= p <= 1.0


def test_exportar_gera_artefatos(tmp_path):
    out = exportar(ModeloMLP.aleatorio(2), tmp_path, n_vetores=30, data=DATA)
    for nome in ("guardia_modelo.h", "vetores_teste.h", "MODELO.json"):
        assert (tmp_path / nome).exists()
    meta = json.loads((tmp_path / "MODELO.json").read_text(encoding="utf-8"))
    assert meta["contrato"] == C.CONTRATO_VERSAO
    assert meta["fonte_dados"] == "ALEATORIO"
    assert meta["arquitetura"]["n_parametros"] == 369
    assert meta["modelo_id"] == out["modelo_id"]
    # vetores incluem partida a frio
    assert sum(r["n_hist"] == 0 for r in out["registros"]) >= 5
    assert "NÃO EDITAR" in (tmp_path / "guardia_modelo.h").read_text(encoding="utf-8")
