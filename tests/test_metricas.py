"""Métricas do protocolo (seção 5)."""

import math

import numpy as np
import pytest

from guardia import metricas


def test_log_loss_e_brier_conhecidos():
    m = metricas.calcular([1, 0], [0.8, 0.2])
    assert m["log_loss"] == pytest.approx(-math.log(0.8))
    assert m["brier"] == pytest.approx(0.04)
    assert m["roc_auc"] == 1.0


def test_probabilidades_extremas_nao_quebram_a_log_loss():
    m = metricas.calcular([1, 0], [0.0, 1.0])
    assert math.isfinite(m["log_loss"]) and m["log_loss"] > 30


def test_ece_manual():
    # faixa 0,7–0,8: confiança 0,75, acerto 0,5 → |0,25| com peso 1
    assert metricas.ece([1, 0, 1, 0], [0.75] * 4) == pytest.approx(0.25)
    # duas faixas, cada uma perfeitamente calibrada
    assert metricas.ece([1, 0, 0, 0], [0.25, 0.25, 0.25, 0.25]) == pytest.approx(0.0)


def test_ece_pequeno_para_previsoes_calibradas():
    rng = np.random.default_rng(0)
    p = rng.random(200_000)
    y = (rng.random(200_000) < p).astype(int)
    assert metricas.ece(y, p) < 0.005


def test_diagrama_soma_n_e_faixas():
    d = metricas.diagrama_confiabilidade([1, 0, 1], [0.05, 0.55, 1.0])
    assert len(d) == 10 and sum(f["n"] for f in d) == 3
    assert d[9]["n"] == 1  # p = 1,0 cai na última faixa


def test_mae_p_real():
    assert metricas.calcular([1, 0], [0.6, 0.4], p_real=[0.7, 0.4])["mae_p_real"] == pytest.approx(0.05)


class TestBootstrap:
    def test_previsoes_iguais(self):
        r = metricas.bootstrap_diferenca_log_loss([1, 0, 1, 0], [0.6] * 4, [0.6] * 4, [1, 1, 2, 2], n_reamostras=200)
        assert r["diferenca"] == 0 and r["ic"] == [0.0, 0.0] and r["cruza_zero"]

    def test_modelo_melhor_tem_diferenca_negativa(self):
        rng = np.random.default_rng(1)
        n = 3000
        p_real = rng.uniform(0.1, 0.9, n)
        y = (rng.random(n) < p_real).astype(int)
        g = np.repeat(np.arange(n // 3), 3)
        r = metricas.bootstrap_diferenca_log_loss(y, p_real, np.full(n, 0.5), g, n_reamostras=500)
        assert r["diferenca"] < 0 and r["ic"][1] < 0 and not r["cruza_zero"]
        assert r["n_participantes"] == 1000

    def test_reproduzivel(self):
        args = ([1, 0, 1, 1, 0, 0], [0.7, 0.3, 0.6, 0.8, 0.4, 0.5], [0.5] * 6, [1, 1, 2, 2, 3, 3])
        assert metricas.bootstrap_diferenca_log_loss(*args, n_reamostras=300) == \
            metricas.bootstrap_diferenca_log_loss(*args, n_reamostras=300)
