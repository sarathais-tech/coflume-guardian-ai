"""Testes da MLP em Keras. Pulados se o TensorFlow não estiver instalado."""

import numpy as np
import pytest

tf = pytest.importorskip("tensorflow")

from guardia import contrato as C  # noqa: E402
from guardia.features import Resposta, montar_entrada, vetorizar  # noqa: E402
from guardia.inferencia_ref import prever  # noqa: E402
from guardia.mlp import construir_mlp, estatisticas_treino, padronizar, para_modelo_mlp  # noqa: E402


def _amostras(n=300, semente=0):
    rng = np.random.default_rng(semente)
    entradas = []
    for _ in range(n):
        hist = [
            Resposta(int(rng.integers(4)), int(rng.integers(3)), bool(rng.random() < 0.6),
                     float(rng.uniform(0, 35)), 30.0, bool(rng.random() < 0.3))
            for _ in range(int(rng.integers(0, 7)))
        ]
        entradas.append(montar_entrada(hist, int(rng.integers(3)), int(rng.integers(4)), int(rng.integers(3))))
    return entradas


def test_arquitetura_padrao():
    m = construir_mlp((16, 8))
    assert m.count_params() == 369
    assert m.input_shape == (None, C.N_ENTRADAS)


def test_conversao_keras_para_contrato_preserva_previsoes():
    entradas = _amostras()
    X = np.stack([vetorizar(e) for e in entradas])
    media, desvio = estatisticas_treino(X)
    m = construir_mlp((16, 8), semente=3)
    y = (np.random.default_rng(1).random(len(X)) < 0.6).astype(np.float32)
    m.fit(padronizar(X, media, desvio), y, epochs=3, verbose=0)

    p_keras = m.predict(padronizar(X, media, desvio), verbose=0).reshape(-1)
    modelo = para_modelo_mlp(m, media, desvio, fonte="ALEATORIO")
    p_ref = np.array([prever(modelo, e) for e in entradas])
    assert np.max(np.abs(p_keras - p_ref)) < 1e-5


def test_fonte_obrigatoria():
    m = construir_mlp((8,))
    with pytest.raises(ValueError):
        para_modelo_mlp(m, np.zeros(9), np.ones(9), fonte="desconhecida")
