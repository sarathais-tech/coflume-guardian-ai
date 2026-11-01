"""Treino e avaliação em VALIDAÇÃO dos modelos da Guardiã IA (Etapa 2).

Segue docs/protocolo_avaliacao.md e docs/protocolo_adendo_01.md, com as
interpretações registradas em docs/treino.md, seção 2:

- dados ``sessoes_v2`` (sim-1.1) e divisão ``split_v2``, por participante;
- só os conjuntos de TREINO e VALIDAÇÃO são carregados: o TESTE continua lacrado;
- hiperparâmetros escolhidos por log loss média em ``GroupKFold`` (5 folds) no treino;
- padronização ajustada dentro de cada fold (e no treino inteiro para o ajuste final);
- a validação é usada só para o early stopping da MLP e para relatar métricas.

Resultados com dados SINTÉTICOS não comprovam eficácia educacional.
"""

from __future__ import annotations

import platform
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.base import BaseEstimator, ClassifierMixin, TransformerMixin, clone
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.tree import DecisionTreeClassifier

from guardia import contrato as C
from guardia import metricas
from guardia.dados import (
    carregar,
    carregar_split,
    conjunto,
    matriz,
    sha256_arquivo,
    verificar_sem_vazamento,
)

VERSAO_TREINO = "treino-v2.0"
SEMENTE = 2026
SEMENTES_MLP = (2026, 2027, 2028, 2029, 2030)
SEMENTE_MLP_CANDIDATA = 2026  # fixada ANTES dos resultados; não é escolhida pelo desempenho
N_FOLDS = 5

GRADE_ARVORE = [{"max_depth": d, "min_samples_leaf": m} for d in (3, 4, 5, 6) for m in (20, 50, 100)]
GRADE_LOGISTICA = [{"C": c} for c in (0.01, 0.1, 1.0, 10.0)]
ARQUITETURAS_MLP = [(8,), (16,), (16, 8), (32, 16)]
TOLERANCIA_ARQUITETURA = 0.01  # "a menor arquitetura a até 1% da melhor log loss"

MLP_CONFIG = {"lr": 1e-3, "batch": 64, "l2": 1e-4, "paciencia": 20, "max_epocas": 300}


# ---------------------------------------------------------------------------
# Dados
# ---------------------------------------------------------------------------

@dataclass
class Conjuntos:
    X_tr: np.ndarray
    y_tr: np.ndarray
    g_tr: np.ndarray
    p_real_tr: np.ndarray
    X_va: np.ndarray
    y_va: np.ndarray
    g_va: np.ndarray
    p_real_va: np.ndarray
    info: dict


def preparar(caminho_dados: Path, caminho_split: Path) -> Conjuntos:
    """Carrega SOMENTE treino e validação. O conjunto de teste nunca é solicitado."""
    caminho_dados, caminho_split = Path(caminho_dados), Path(caminho_split)
    df = carregar(caminho_dados)
    split = carregar_split(caminho_split)
    verificar_sem_vazamento(split["participantes"])
    tr = conjunto(df, split, "treino")
    va = conjunto(df, split, "validacao")
    if set(tr["participante_id"]) & set(va["participante_id"]):
        raise AssertionError("Vazamento entre treino e validação.")
    X_tr, y_tr, g_tr = matriz(tr)
    X_va, y_va, g_va = matriz(va)
    sha = sha256_arquivo(caminho_dados)
    info = {
        "arquivo": caminho_dados.name,
        "fonte": str(df["fonte"].iloc[0]),
        "versao_simulador": str(df["versao_simulador"].iloc[0]),
        "sha256": sha,
        "sha256_registrado_no_split": split["dados"]["sha256"],
        "identico_ao_registrado": sha == split["dados"]["sha256"],
        "split": caminho_split.name,
        "split_ids_sha256": split["ids_sha256"],
        "conjuntos_carregados": ["treino", "validacao"],
        "teste_lacrado": True,
        "n_participantes": {"treino": int(len(np.unique(g_tr))), "validacao": int(len(np.unique(g_va)))},
        "n_linhas": {"treino": int(len(y_tr)), "validacao": int(len(y_va))},
    }
    return Conjuntos(
        X_tr, y_tr, g_tr, tr["p_real"].to_numpy(float),
        X_va, y_va, g_va, va["p_real"].to_numpy(float), info,
    )


def dobras(g_tr: np.ndarray) -> list[tuple[np.ndarray, np.ndarray]]:
    """GroupKFold determinístico: nenhum participante aparece no ajuste e no teste da mesma dobra."""
    X_falso = np.zeros((len(g_tr), 1))
    return list(GroupKFold(n_splits=N_FOLDS).split(X_falso, groups=g_tr))


# ---------------------------------------------------------------------------
# Modelos scikit-learn
# ---------------------------------------------------------------------------

class Padronizador(BaseEstimator, TransformerMixin):
    """Padronização do contrato: posições 0..8 com média e desvio do conjunto de AJUSTE."""

    def fit(self, X, y=None):
        num = np.asarray(X, dtype=np.float64)[:, : C.N_NUMERICAS]
        self.media_ = num.mean(axis=0).astype(np.float32)
        desvio = num.std(axis=0).astype(np.float32)
        self.desvio_ = np.where(desvio < 1e-6, 1.0, desvio).astype(np.float32)
        return self

    def transform(self, X):
        X = np.asarray(X, dtype=np.float32).copy()
        X[:, : C.N_NUMERICAS] = (X[:, : C.N_NUMERICAS] - self.media_) / self.desvio_
        return X


class BaselineIngenuo(BaseEstimator, ClassifierMixin):
    """Taxa de acerto do treino por (nivel_inicial, nivel_candidato); sem comportamento."""

    def fit(self, X, y):
        X, y = np.asarray(X), np.asarray(y, dtype=np.float64)
        self.global_ = float(y.mean())
        self.taxa_ = {}
        chaves = list(zip(X[:, 1].astype(int), X[:, 0].astype(int)))
        for chave in set(chaves):
            m = np.array([c == chave for c in chaves])
            self.taxa_[chave] = float(y[m].mean())
        self.classes_ = np.array([0, 1])
        return self

    def predict_proba(self, X):
        X = np.asarray(X)
        p = np.array([self.taxa_.get((int(i), int(n)), self.global_) for i, n in zip(X[:, 1], X[:, 0])])
        return np.column_stack([1 - p, p])


def _arvore(params: dict) -> DecisionTreeClassifier:
    return DecisionTreeClassifier(random_state=SEMENTE, **params)


def _logistica(params: dict) -> Pipeline:
    return Pipeline([("padronizador", Padronizador()), ("logistica", LogisticRegression(max_iter=5000, **params))])


def _cv_sklearn(modelo, X, y, folds) -> list[float]:
    perdas = []
    for itr, ite in folds:
        m = clone(modelo).fit(X[itr], y[itr])
        perdas.append(metricas.calcular(y[ite], m.predict_proba(X[ite])[:, 1])["log_loss"])
    return perdas


def _resumo_cv(perdas: list[float]) -> dict:
    return {"cv_log_loss_media": float(np.mean(perdas)), "cv_log_loss_dp": float(np.std(perdas)),
            "cv_log_loss_folds": [float(x) for x in perdas]}


def _avaliar(y, p, p_real) -> dict:
    return {"metricas": metricas.calcular(y, p, p_real), "diagrama": metricas.diagrama_confiabilidade(y, p)}


def treinar_baseline(d: Conjuntos, folds) -> tuple[dict, np.ndarray]:
    t0 = time.time()
    perdas = _cv_sklearn(BaselineIngenuo(), d.X_tr, d.y_tr, folds)
    m = BaselineIngenuo().fit(d.X_tr, d.y_tr)
    p = m.predict_proba(d.X_va)[:, 1]
    res = {"descricao": "taxa de acerto por (nivel_inicial, nivel_candidato) no treino",
           "taxas": {f"{i},{n}": v for (i, n), v in sorted(m.taxa_.items())}, **_resumo_cv(perdas),
           "validacao": _avaliar(d.y_va, p, d.p_real_va), "segundos": round(time.time() - t0, 2)}
    return res, p


def _buscar(fabrica, grade, chave_desempate, d: Conjuntos, folds) -> tuple[list[dict], dict]:
    linhas = []
    for params in grade:
        linhas.append({"params": params, **_resumo_cv(_cv_sklearn(fabrica(params), d.X_tr, d.y_tr, folds))})
    escolhido = min(linhas, key=lambda r: (round(r["cv_log_loss_media"], 12), chave_desempate(r["params"])))
    return linhas, escolhido["params"]


def treinar_arvore(d: Conjuntos, folds) -> tuple[dict, np.ndarray, DecisionTreeClassifier]:
    t0 = time.time()
    # desempate: árvore mais simples (menos profunda, folhas maiores)
    grade, params = _buscar(_arvore, GRADE_ARVORE, lambda q: (q["max_depth"], -q["min_samples_leaf"]), d, folds)
    m = _arvore(params).fit(d.X_tr, d.y_tr)
    p = m.predict_proba(d.X_va)[:, 1]
    res = {"grade": grade, "escolhido": params, "n_folhas": int(m.get_n_leaves()), "profundidade": int(m.get_depth()),
           "validacao": _avaliar(d.y_va, p, d.p_real_va), "segundos": round(time.time() - t0, 2)}
    return res, p, m


def treinar_logistica(d: Conjuntos, folds) -> tuple[dict, np.ndarray, Pipeline]:
    t0 = time.time()
    # desempate: regularização mais forte (C menor)
    grade, params = _buscar(_logistica, GRADE_LOGISTICA, lambda q: q["C"], d, folds)
    m = _logistica(params).fit(d.X_tr, d.y_tr)
    p = m.predict_proba(d.X_va)[:, 1]
    lr = m.named_steps["logistica"]
    res = {"grade": grade, "escolhido": params,
           "coeficientes": [float(c) for c in lr.coef_[0]], "intercepto": float(lr.intercept_[0]),
           "validacao": _avaliar(d.y_va, p, d.p_real_va), "segundos": round(time.time() - t0, 2)}
    return res, p, m


# ---------------------------------------------------------------------------
# MLP (Keras/TensorFlow)
# ---------------------------------------------------------------------------

def tensorflow_disponivel() -> bool:
    try:
        import tensorflow  # noqa: F401
    except ImportError:
        return False
    return True


def n_parametros(arquitetura) -> int:
    tamanhos = (C.N_ENTRADAS, *arquitetura, 1)
    return int(sum(a * b + b for a, b in zip(tamanhos[:-1], tamanhos[1:])))


def escolher_arquitetura(linhas: list[dict], tolerancia: float = TOLERANCIA_ARQUITETURA) -> dict:
    """A MENOR arquitetura (em parâmetros) com log loss ≤ (1 + tolerância) × melhor (protocolo, seção 4)."""
    melhor = min(r["cv_log_loss_media"] for r in linhas)
    candidatas = [r for r in linhas if r["cv_log_loss_media"] <= melhor * (1 + tolerancia)]
    return min(candidatas, key=lambda r: (r["n_parametros"], r["cv_log_loss_media"]))


def _ajustar_mlp(arquitetura, semente, X_aj, y_aj, X_va, y_va, config):
    import tensorflow as tf

    from guardia.mlp import construir_mlp, treinar

    tf.keras.utils.set_random_seed(semente)
    tf.config.experimental.enable_op_determinism()
    pad = Padronizador().fit(X_aj)
    modelo = construir_mlp(arquitetura, l2=config["l2"], semente=semente)
    modelo.optimizer.learning_rate.assign(config["lr"])
    hist = treinar(modelo, pad.transform(X_aj), y_aj, pad.transform(X_va), y_va, semente=semente,
                   epocas=config["max_epocas"], paciencia=config["paciencia"], batch=config["batch"])
    val_loss = hist.history["val_loss"]
    epocas = {"executadas": len(val_loss), "melhor": int(np.argmin(val_loss)) + 1}
    return modelo, pad, epocas


def _prever_mlp(modelo, pad, X) -> np.ndarray:
    return modelo.predict(pad.transform(X), verbose=0, batch_size=4096).reshape(-1).astype(np.float64)


def treinar_mlp(d: Conjuntos, folds, config: dict | None = None, arquiteturas=None, sementes=None):
    """Seleção por GroupKFold (early stopping na validação) e 5 execuções finais no treino inteiro."""
    from guardia.inferencia_ref import prever as prever_ref
    from guardia.mlp import para_modelo_mlp

    config = {**MLP_CONFIG, **(config or {})}
    arquiteturas = arquiteturas or ARQUITETURAS_MLP
    sementes = sementes or SEMENTES_MLP
    t0 = time.time()

    grade = []
    for arq in arquiteturas:
        perdas, epocas = [], []
        for k, (itr, ite) in enumerate(folds):
            modelo, pad, ep = _ajustar_mlp(arq, SEMENTE + k, d.X_tr[itr], d.y_tr[itr], d.X_va, d.y_va, config)
            perdas.append(metricas.calcular(d.y_tr[ite], _prever_mlp(modelo, pad, d.X_tr[ite]))["log_loss"])
            epocas.append(ep["melhor"])
        grade.append({"arquitetura": list(arq), "n_parametros": n_parametros(arq), **_resumo_cv(perdas),
                      "epocas_melhor_por_fold": epocas})
    escolhida = escolher_arquitetura(grade)
    arq = tuple(escolhida["arquitetura"])

    execucoes, previsoes, candidata = [], {}, None
    for s in sementes:
        modelo, pad, ep = _ajustar_mlp(arq, s, d.X_tr, d.y_tr, d.X_va, d.y_va, config)
        p = _prever_mlp(modelo, pad, d.X_va)
        previsoes[s] = p
        execucoes.append({"semente": s, "epocas": ep, "validacao": metricas.calcular(d.y_va, p, d.p_real_va)})
        if s == SEMENTE_MLP_CANDIDATA:
            candidata = (modelo, pad)

    # Conferência: o modelo convertido para o formato do contrato prevê o mesmo que o Keras.
    modelo, pad = candidata if candidata else (modelo, pad)
    convertido = para_modelo_mlp(modelo, pad.media_, pad.desvio_, fonte="SINTETICO", arquitetura=list(arq))
    from guardia.features import Entrada

    amostra = range(0, len(d.y_va), max(1, len(d.y_va) // 200))
    p_keras = _prever_mlp(modelo, pad, d.X_va)
    dif = 0.0
    for i in amostra:
        x = d.X_va[i]
        e = Entrada(int(x[0]), int(x[1]), int(x[2]), int(np.argmax(x[C.N_NUMERICAS:])), float(x[3]), float(x[4]),
                    float(x[5]), float(x[6]), int(x[7]), int(x[8]))
        dif = max(dif, abs(prever_ref(convertido, e) - p_keras[i]))

    nomes = ["log_loss", "brier", "roc_auc", "ece", "mae_p_real"]
    valores = {n: [e["validacao"][n] for e in execucoes] for n in nomes}
    p_cand = previsoes.get(SEMENTE_MLP_CANDIDATA, next(iter(previsoes.values())))
    res = {
        "config": config,
        "grade": grade,
        "escolhido": {"arquitetura": list(arq), "n_parametros": n_parametros(arq)},
        "regra_escolha": f"menor arquitetura com log loss <= (1 + {TOLERANCIA_ARQUITETURA}) x melhor",
        "execucoes": execucoes,
        "validacao_media": {n: float(np.mean(v)) for n, v in valores.items()},
        "validacao_dp": {n: float(np.std(v)) for n, v in valores.items()},
        "semente_candidata": SEMENTE_MLP_CANDIDATA,
        "validacao": _avaliar(d.y_va, p_cand, d.p_real_va),
        "equivalencia_keras_formato_contrato_max": float(dif),
        "segundos": round(time.time() - t0, 2),
    }
    return res, p_cand, convertido


# ---------------------------------------------------------------------------
# Execução completa
# ---------------------------------------------------------------------------

def ambiente() -> dict:
    amb = {"python": platform.python_version(), "plataforma": platform.platform(), "numpy": np.__version__,
           "pandas": pd.__version__, "scikit_learn": sklearn.__version__}
    if tensorflow_disponivel():
        import tensorflow as tf

        amb["tensorflow"] = tf.__version__
    return amb


def executar(caminho_dados: Path, caminho_split: Path, modelos=("baseline", "arvore", "logistica", "mlp"),
             config_mlp: dict | None = None, arquiteturas_mlp=None, sementes_mlp=None) -> tuple[dict, dict]:
    """Treina os modelos pedidos e devolve (resultados, objetos treinados)."""
    d = preparar(caminho_dados, caminho_split)
    folds = dobras(d.g_tr)
    for itr, ite in folds:
        assert not set(d.g_tr[itr]) & set(d.g_tr[ite])

    res = {
        "versao": VERSAO_TREINO,
        "fonte": "SINTETICO",
        "aviso": "Resultados [SINTÉTICO] em VALIDAÇÃO. Não comprovam eficácia educacional; o teste continua lacrado.",
        "protocolo": ["docs/protocolo_avaliacao.md", "docs/protocolo_adendo_01.md", "docs/treino.md"],
        "dados": d.info,
        "ambiente": ambiente(),
        "sementes": {"geral": SEMENTE, "mlp": list(sementes_mlp or SEMENTES_MLP), "mlp_candidata": SEMENTE_MLP_CANDIDATA,
                     "bootstrap": SEMENTE},
        "n_folds": N_FOLDS,
        "oraculo_p_real": {"descricao": "p_real do simulador usado como previsão: limite inferior de referência",
                           "validacao": metricas.calcular(d.y_va, d.p_real_va, d.p_real_va)},
        "modelos": {},
    }
    previsoes, objetos = {}, {}
    if "baseline" in modelos:
        res["modelos"]["baseline"], previsoes["baseline"] = treinar_baseline(d, folds)
    if "arvore" in modelos:
        res["modelos"]["arvore"], previsoes["arvore"], objetos["arvore"] = treinar_arvore(d, folds)
    if "logistica" in modelos:
        res["modelos"]["logistica"], previsoes["logistica"], objetos["logistica"] = treinar_logistica(d, folds)
    if "mlp" in modelos:
        res["modelos"]["mlp"], previsoes["mlp"], objetos["mlp"] = treinar_mlp(
            d, folds, config_mlp, arquiteturas_mlp, sementes_mlp)

    comparacoes = {}
    for a, b in (("mlp", "arvore"), ("logistica", "arvore"), ("mlp", "logistica"), ("arvore", "baseline")):
        if a in previsoes and b in previsoes:
            comparacoes[f"{a}_menos_{b}"] = metricas.bootstrap_diferenca_log_loss(
                d.y_va, previsoes[a], previsoes[b], d.g_va, semente=SEMENTE)
    res["comparacoes_validacao_preliminares"] = comparacoes
    return res, objetos
