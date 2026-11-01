"""Métricas do protocolo de avaliação (docs/protocolo_avaliacao.md, seção 5).

- log loss (principal), Brier score, ROC-AUC;
- ECE com 10 faixas de largura igual e os dados do diagrama de confiabilidade;
- erro absoluto médio contra ``p_real`` (somente dados sintéticos);
- intervalo de confiança por bootstrap sobre PARTICIPANTES.
"""

from __future__ import annotations

import numpy as np
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score

N_FAIXAS_ECE = 10
EPS = 1e-15  # limite numérico usado na log loss (o mesmo para todos os modelos)


def _p(p) -> np.ndarray:
    return np.clip(np.asarray(p, dtype=np.float64), EPS, 1.0 - EPS)


def diagrama_confiabilidade(y, p, n_faixas: int = N_FAIXAS_ECE) -> list[dict]:
    """Por faixa de largura igual em [0, 1]: n, confiança média e acerto observado."""
    y = np.asarray(y, dtype=np.float64)
    p = np.asarray(p, dtype=np.float64)
    faixa = np.minimum((p * n_faixas).astype(int), n_faixas - 1)
    linhas = []
    for k in range(n_faixas):
        m = faixa == k
        linhas.append({
            "faixa": [k / n_faixas, (k + 1) / n_faixas],
            "n": int(m.sum()),
            "confianca_media": float(p[m].mean()) if m.any() else None,
            "acerto_observado": float(y[m].mean()) if m.any() else None,
        })
    return linhas


def ece(y, p, n_faixas: int = N_FAIXAS_ECE) -> float:
    """Erro de calibração esperado: média de |acerto − confiança| ponderada pelo tamanho da faixa."""
    n = len(y)
    total = 0.0
    for f in diagrama_confiabilidade(y, p, n_faixas):
        if f["n"]:
            total += f["n"] / n * abs(f["acerto_observado"] - f["confianca_media"])
    return float(total)


def calcular(y, p, p_real=None) -> dict:
    """Todas as métricas do protocolo para um conjunto de previsões."""
    y = np.asarray(y, dtype=np.float64)
    pc = _p(p)
    m = {
        "n": int(len(y)),
        "log_loss": float(log_loss(y, pc, labels=[0, 1])),
        "brier": float(brier_score_loss(y, pc)),
        "roc_auc": float(roc_auc_score(y, pc)) if len(np.unique(y)) == 2 else None,
        "ece": ece(y, pc),
        "p_media": float(pc.mean()),
        "acerto_medio": float(y.mean()),
    }
    if p_real is not None:
        m["mae_p_real"] = float(np.mean(np.abs(pc - np.asarray(p_real, dtype=np.float64))))
    return m


def _log_loss_por_linha(y, p) -> np.ndarray:
    pc = _p(p)
    y = np.asarray(y, dtype=np.float64)
    return -(y * np.log(pc) + (1 - y) * np.log(1 - pc))


def bootstrap_diferenca_log_loss(
    y, p_a, p_b, grupos, n_reamostras: int = 2000, semente: int = 2026, nivel: float = 0.95
) -> dict:
    """IC por bootstrap de log_loss(A) − log_loss(B), reamostrando PARTICIPANTES (protocolo, seção 5).

    Valores negativos favorecem A.
    """
    perda_a = _log_loss_por_linha(y, p_a)
    perda_b = _log_loss_por_linha(y, p_b)
    grupos = np.asarray(grupos)
    ids, inverso = np.unique(grupos, return_inverse=True)
    n_ids = len(ids)
    soma_a = np.bincount(inverso, weights=perda_a, minlength=n_ids)
    soma_b = np.bincount(inverso, weights=perda_b, minlength=n_ids)
    contagem = np.bincount(inverso, minlength=n_ids)

    rng = np.random.default_rng(semente)
    difs = np.empty(n_reamostras)
    for i in range(n_reamostras):
        amostra = rng.integers(0, n_ids, n_ids)
        peso = np.bincount(amostra, minlength=n_ids)
        n_linhas = (peso * contagem).sum()
        difs[i] = ((peso * soma_a).sum() - (peso * soma_b).sum()) / n_linhas
    alfa = (1 - nivel) / 2
    lo, hi = np.quantile(difs, [alfa, 1 - alfa])
    observado = float(perda_a.mean() - perda_b.mean())
    return {
        "diferenca": observado,
        "ic": [float(lo), float(hi)],
        "nivel": nivel,
        "n_reamostras": n_reamostras,
        "semente": semente,
        "n_participantes": int(n_ids),
        "cruza_zero": bool(lo <= 0.0 <= hi),
    }
