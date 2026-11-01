"""Leitura e conferência do artefato do treino oficial (ZIP do GitHub Actions).

Nada aqui abre o conjunto de teste: a conferência das previsões usa só a
VALIDAÇÃO, por meio de guardia.treino.preparar.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import numpy as np

from guardia import contrato as C
from guardia import metricas
from guardia.features import Entrada
from guardia.inferencia_ref import ModeloMLP, prever

ARQUIVOS_ESPERADOS = (
    "resultados/sinteticos/treino_v2/validacao.json",
    "modelos/treino_v2/mlp_candidata.npz",
    "modelos/treino_v2/arvore.joblib",
    "modelos/treino_v2/logistica.joblib",
    "ambiente-pip.txt",
)
METRICAS_CONFERIDAS = ("log_loss", "brier", "roc_auc", "ece", "mae_p_real")


def sha256(caminho: Path) -> str:
    return hashlib.sha256(Path(caminho).read_bytes()).hexdigest()


def extrair_zip(caminho_zip: Path, sha_esperado: str, destino: Path) -> dict[str, str]:
    """Confere o SHA-256 do ZIP, extrai com segurança e devolve o SHA-256 de cada arquivo."""
    atual = sha256(caminho_zip)
    if atual != sha_esperado:
        raise ValueError(f"SHA-256 do ZIP não confere: {atual} ≠ {sha_esperado}")
    destino = Path(destino).resolve()
    with zipfile.ZipFile(caminho_zip) as z:
        for nome in z.namelist():
            alvo = (destino / nome).resolve()
            if destino not in alvo.parents and alvo != destino:
                raise ValueError(f"Caminho inseguro no ZIP: {nome}")
        z.extractall(destino)
        nomes = [n for n in z.namelist() if not n.endswith("/")]
    faltando = [n for n in ARQUIVOS_ESPERADOS if n not in nomes]
    if faltando:
        raise ValueError(f"Arquivos ausentes no ZIP: {faltando}")
    return {n: sha256(destino / n) for n in sorted(nomes)}


def carregar_mlp_npz(caminho: Path, **metadados) -> ModeloMLP:
    """Lê media, desvio e W0/b0, W1/b1 (e W2/b2) no formato do contrato ([saídas, entradas])."""
    with np.load(caminho) as d:
        chaves = set(d.files)
        n_camadas = len([k for k in chaves if k.startswith("W")])
        esperadas = {"media", "desvio"} | {f"W{i}" for i in range(n_camadas)} | {f"b{i}" for i in range(n_camadas)}
        if chaves != esperadas:
            raise ValueError(f"Chaves inesperadas no .npz: {sorted(chaves ^ esperadas)}")
        camadas = [(d[f"W{i}"], d[f"b{i}"]) for i in range(n_camadas)]
        return ModeloMLP(camadas, d["media"], d["desvio"], {"fonte": "SINTETICO", **metadados})


def _entrada(x: np.ndarray) -> Entrada:
    return Entrada(int(x[0]), int(x[1]), int(x[2]), int(np.argmax(x[C.N_NUMERICAS:])), float(x[3]), float(x[4]),
                   float(x[5]), float(x[6]), int(x[7]), int(x[8]))


def conferir_com_validacao(modelo: ModeloMLP, validacao: dict, X_va, y_va, p_real_va, tol: float = 1e-5) -> dict:
    """Confere arquitetura e previsões do modelo contra o registrado em validacao.json.

    Recalcula P(acerto) de TODA a validação com a implementação de referência em Python
    e compara as métricas com as da MLP candidata registradas pelo CI.
    """
    mlp = validacao["modelos"]["mlp"]
    esperado = mlp["escolhido"]
    if list(modelo.ocultas) != list(esperado["arquitetura"]):
        raise ValueError(f"Arquitetura {list(modelo.ocultas)} ≠ registrada {esperado['arquitetura']}")
    if modelo.n_parametros != esperado["n_parametros"]:
        raise ValueError(f"Parâmetros {modelo.n_parametros} ≠ registrados {esperado['n_parametros']}")

    p = np.array([prever(modelo, _entrada(x)) for x in X_va])
    if (p == C.INVALIDO).any():
        raise ValueError("Previsão INVALIDO para entrada da validação.")
    recalculado = metricas.calcular(y_va, p, p_real_va)
    registrado = mlp["validacao"]["metricas"]
    diferencas = {k: abs(recalculado[k] - registrado[k]) for k in METRICAS_CONFERIDAS}
    pior = max(diferencas.values())
    if pior > tol:
        raise ValueError(f"Métricas recalculadas divergem das registradas (máx. {pior:.2e} > {tol}): {diferencas}")
    return {
        "arquitetura": list(modelo.ocultas),
        "n_parametros": modelo.n_parametros,
        "n_validacao": int(len(y_va)),
        "metricas_recalculadas": recalculado,
        "metricas_registradas": {k: registrado[k] for k in METRICAS_CONFERIDAS},
        "diferenca_max": float(pior),
        "tolerancia": tol,
        "semente_candidata": mlp.get("semente_candidata"),
    }


def carregar_validacao(caminho: Path, sha_esperado: str | None = None) -> dict:
    if sha_esperado is not None and sha256(caminho) != sha_esperado:
        raise ValueError("SHA-256 do validacao.json não confere com o publicado pelo CI.")
    return json.loads(Path(caminho).read_text(encoding="utf-8"))
