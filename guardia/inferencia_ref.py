"""Modelo MLP independente de framework e inferência de referência em float32.

`ModeloMLP` é o formato intermediário entre o treino (Keras) e a exportação
para C++. A inferência aqui segue a mesma sequência de operações do
guardia_runtime.h e é a referência dos testes de equivalência.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

import numpy as np

from guardia import contrato as C
from guardia.features import Entrada, entrada_valida, vetorizar

F32 = np.float32


@dataclass
class ModeloMLP:
    """Pesos de uma MLP com 1 ou 2 camadas ocultas (ReLU) e saída sigmoide.

    `camadas[k] = (W, b)` com W no formato [saídas, entradas] (o mesmo do C++).
    """

    camadas: list[tuple[np.ndarray, np.ndarray]]
    media: np.ndarray   # (9,) média das features numéricas no treino
    desvio: np.ndarray  # (9,) desvio das features numéricas no treino
    metadados: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.camadas = [(np.asarray(W, F32), np.asarray(b, F32).reshape(-1)) for W, b in self.camadas]
        self.media = np.asarray(self.media, F32).reshape(-1)
        desvio = np.asarray(self.desvio, F32).reshape(-1)
        self.desvio = np.where(desvio < F32(1e-6), F32(1.0), desvio).astype(F32)
        self._validar()

    def _validar(self) -> None:
        if not 2 <= len(self.camadas) <= 3:
            raise ValueError("O contrato 1.x aceita 1 ou 2 camadas ocultas.")
        n_in = C.N_ENTRADAS
        for i, (W, b) in enumerate(self.camadas):
            if W.ndim != 2 or W.shape[1] != n_in or b.shape != (W.shape[0],):
                raise ValueError(f"Camada {i}: formato inconsistente {W.shape}, {b.shape}.")
            n_in = W.shape[0]
        if self.camadas[-1][0].shape[0] != 1:
            raise ValueError("A camada de saída deve ter 1 neurônio.")
        if self.media.shape != (C.N_NUMERICAS,) or self.desvio.shape != (C.N_NUMERICAS,):
            raise ValueError("Média e desvio devem ter 9 posições.")
        for arr in [self.media, self.desvio] + [a for W, b in self.camadas for a in (W, b)]:
            if not np.all(np.isfinite(arr)):
                raise ValueError("O modelo contém valores não finitos.")

    @property
    def ocultas(self) -> tuple[int, ...]:
        return tuple(W.shape[0] for W, _ in self.camadas[:-1])

    @property
    def n_parametros(self) -> int:
        return int(sum(W.size + b.size for W, b in self.camadas))

    def hash(self) -> str:
        """SHA-256 dos parâmetros em float32 (identifica o modelo exportado)."""
        h = hashlib.sha256()
        for arr in [self.media, self.desvio] + [a for W, b in self.camadas for a in (W, b)]:
            h.update(np.ascontiguousarray(arr, dtype="<f4").tobytes())
        return h.hexdigest()

    @classmethod
    def aleatorio(cls, semente: int, ocultas: tuple[int, ...] = (16, 8)) -> "ModeloMLP":
        """Pesos ALEATÓRIOS (Glorot uniforme). Uso exclusivo em bancada e testes.

        O custo computacional é idêntico ao de um modelo treinado com a mesma
        arquitetura, o que permite testar a viabilidade embarcada antes do treino.
        """
        rng = np.random.default_rng(semente)
        tamanhos = (C.N_ENTRADAS, *ocultas, 1)
        camadas = []
        for n_in, n_out in zip(tamanhos[:-1], tamanhos[1:]):
            lim = np.sqrt(6.0 / (n_in + n_out))
            camadas.append((rng.uniform(-lim, lim, (n_out, n_in)), rng.uniform(-0.1, 0.1, n_out)))
        # Média e desvio plausíveis para as 9 features numéricas.
        media = np.array([1.0, 1.0, 3.0, 0.6, 0.6, 0.5, 0.3, 0.2, 0.3])
        desvio = np.array([0.8, 0.8, 2.5, 0.3, 0.35, 0.25, 0.35, 0.9, 1.6])
        return cls(camadas, media, desvio, {"fonte": "ALEATORIO", "semente": semente})


def _sigmoide(z: np.float32) -> np.float32:
    if z >= 0:
        return F32(F32(1) / F32(F32(1) + np.exp(F32(-z), dtype=F32)))
    e = np.exp(z, dtype=F32)
    return F32(e / F32(F32(1) + e))


def prever(modelo: ModeloMLP, entrada: Entrada) -> float:
    """P(acerto) em [0, 1], ou C.INVALIDO para entradas fora da faixa."""
    if not entrada_valida(entrada):
        return C.INVALIDO
    x = vetorizar(entrada)
    x[: C.N_NUMERICAS] = (x[: C.N_NUMERICAS] - modelo.media) / modelo.desvio
    a = x
    for W, b in modelo.camadas[:-1]:
        a = np.maximum(W @ a + b, F32(0)).astype(F32)
    W, b = modelo.camadas[-1]
    z = F32((W @ a + b)[0])
    p = _sigmoide(z)
    if not np.isfinite(p):
        return C.INVALIDO
    return float(min(max(p, F32(0)), F32(1)))
