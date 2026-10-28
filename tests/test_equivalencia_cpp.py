"""Equivalência Python × C++: o mesmo modelo deve dar as mesmas respostas.

O runtime C++ é compilado no PC com -Wall -Wextra -Werror e executado sobre os
vetores de teste gerados pelo exportador.
"""

import datetime as dt

import pytest

from guardia.exportar.mlp_cpp import exportar
from guardia.inferencia_ref import ModeloMLP

TOL_P = 1e-5       # contrato, seção 4, item 6
TOL_FEATURES = 1e-6


def _ler(saida: str) -> dict:
    return dict(linha.split("=", 1) for linha in saida.strip().splitlines() if "=" in linha)


@pytest.mark.parametrize("ocultas", [(16, 8), (16,), (8,), (32, 16)])
@pytest.mark.parametrize("semente", [1, 2026])
def test_python_e_cpp_coincidem(compilar_e_rodar, tmp_path, ocultas, semente):
    pasta = tmp_path / "modelo"
    info = exportar(ModeloMLP.aleatorio(semente, ocultas), pasta, n_vetores=200, data=dt.date(2026, 10, 28))
    r = _ler(compilar_e_rodar("equivalencia.cpp", pasta))

    assert r["MODELO"] == info["modelo_id"]
    assert int(r["N"]) == 200
    assert int(r["FALHAS_INTEIRAS"]) == 0
    assert int(r["INVALIDOS"]) == 0
    assert float(r["ERRO_FEATURES_MAX"]) <= TOL_FEATURES
    assert float(r["ERRO_P_MAX"]) < TOL_P, f"erro máximo {r['ERRO_P_MAX']}"


def test_garantias_para_entradas_invalidas(compilar_e_rodar, tmp_path):
    pasta = tmp_path / "modelo"
    exportar(ModeloMLP.aleatorio(9), pasta, n_vetores=10)
    r = _ler(compilar_e_rodar("invalidos.cpp", pasta))
    assert int(r["FALHAS"]) == 0, r
