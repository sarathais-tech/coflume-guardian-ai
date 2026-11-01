"""Carregamento, validação e divisão por participante dos dados da Guardiã IA.

Regras implementadas (docs/dados.md e docs/protocolo_avaliacao.md):

- um arquivo contém UMA única fonte (SINTETICO ou REAL), coerente com a pasta;
- só as colunas do contrato viram features; ``resp_*``, ``p_real``, ``ordem``
  e ``tipo`` são proibidas no treino;
- a divisão treino/validação/teste é feita por ``participante_id``, nunca por linha;
- o conjunto de teste é lacrado: só é entregue com ``abrir_teste=True``.
"""

from __future__ import annotations

import hashlib
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from guardia import contrato as C
from guardia.simulador import COLUNAS

PASTA_POR_FONTE = {"SINTETICO": "sinteticos", "REAL": "reais"}

COLUNAS_FEATURES = C.FEATURES_NUMERICAS + ("categoria",)
COLUNA_ROTULO = "acertou"
COLUNA_GRUPO = "participante_id"
COLUNAS_PROIBIDAS_NO_TREINO = (
    "ordem",
    "tipo",
    "resp_usou_dica",
    "resp_tempo_gasto_s",
    "resp_tempo_limite_s",
    "resp_esgotou",
    "p_real",
)

PROPORCOES = {"treino": 0.70, "validacao": 0.15, "teste": 0.15}
SEMENTE_DIVISAO = 2026
CONJUNTOS = tuple(PROPORCOES)


class ConjuntoLacradoError(PermissionError):
    """Tentativa de usar o conjunto de teste sem abri-lo explicitamente."""


# ---------------------------------------------------------------------------
# Carregamento e validação
# ---------------------------------------------------------------------------

def sha256_arquivo(caminho: Path) -> str:
    return hashlib.sha256(Path(caminho).read_bytes()).hexdigest()


def carregar(caminho: Path) -> pd.DataFrame:
    """Lê um CSV de sessões e valida formato, fonte, pasta e faixas."""
    caminho = Path(caminho)
    df = pd.read_csv(caminho, dtype={"fonte": str, "tipo": str, "versao_simulador": str})
    if tuple(df.columns) != COLUNAS:
        raise ValueError(f"Colunas inesperadas em {caminho.name}: {list(df.columns)}")
    fontes = set(df["fonte"].unique())
    if len(fontes) != 1:
        raise ValueError(f"{caminho.name} mistura fontes {sorted(fontes)}; isso é proibido (docs/dados.md).")
    fonte = fontes.pop()
    if fonte not in PASTA_POR_FONTE:
        raise ValueError(f"Fonte inválida em arquivo de dados: {fonte!r}.")
    if PASTA_POR_FONTE[fonte] not in caminho.parent.parts:
        raise ValueError(f"Dados {fonte} devem estar numa pasta '{PASTA_POR_FONTE[fonte]}' (está em {caminho.parent}).")
    for col in C.FEATURES_NUMERICAS[3:7]:
        df[col] = df[col].astype(np.float32)
    validar(df)
    return df


def validar(df: pd.DataFrame) -> None:
    """Verifica faixas do contrato e a estrutura de cada sessão. Lança ValueError."""
    erros: list[str] = []

    def exigir(cond: pd.Series | bool, msg: str) -> None:
        ok = bool(np.all(cond))
        if not ok:
            erros.append(msg)

    exigir(df["nivel_candidato"].between(0, C.N_NIVEIS - 1), "nivel_candidato fora de 0..2")
    exigir(df["nivel_inicial"].between(0, C.N_NIVEIS - 1), "nivel_inicial fora de 0..2")
    exigir(df["categoria"].between(0, C.N_CATEGORIAS - 1), "categoria fora de 0..3")
    exigir(df["n_respondidas"].between(0, C.N_RESPONDIDAS_MAX), "n_respondidas fora de 0..8")
    for col in ("taxa_acerto_sessao", "taxa_acerto_categoria", "tempo_medio_norm", "dicas_por_questao"):
        exigir(df[col].between(0.0, 1.0) & np.isfinite(df[col]), f"{col} fora de [0, 1]")
    exigir(df["resultado_ultima"].isin([-1, 0, 1]), "resultado_ultima fora de {-1,0,1}")
    exigir(df["sequencia"].between(-C.SEQUENCIA_MAX, C.SEQUENCIA_MAX), "sequencia fora de -3..3")
    exigir(df[COLUNA_ROTULO].isin([0, 1]), "acertou deve ser 0 ou 1")
    exigir(df["resp_usou_dica"].isin([0, 1]) & df["resp_esgotou"].isin([0, 1]), "flags resp_* devem ser 0/1")
    exigir((df["resp_tempo_gasto_s"] >= 0) & (df["resp_tempo_gasto_s"] <= df["resp_tempo_limite_s"]),
           "resp_tempo_gasto_s fora de [0, limite]")
    exigir(df["resp_tempo_limite_s"] > 0, "resp_tempo_limite_s deve ser positivo")
    exigir((df["resp_esgotou"] == 0) | (df[COLUNA_ROTULO] == 0), "tempo esgotado deve contar como erro")
    exigir(df["tipo"].isin(["principal", "reforco"]), "tipo inválido")

    sint = df["fonte"] == "SINTETICO"
    if sint.any():
        exigir(df.loc[sint, "p_real"].between(0.0, 1.0), "p_real fora de [0, 1]")
    if (~sint).any():
        exigir(df.loc[~sint, "p_real"].isna(), "p_real só pode existir em dados sintéticos")

    # Estrutura das sessões
    g = df.groupby(COLUNA_GRUPO, sort=False)
    ordem_ok = g["ordem"].apply(lambda s: list(s) == list(range(len(s))))
    exigir(ordem_ok, "ordem deve ser 0, 1, 2, ... dentro de cada participante (linhas contíguas)")
    exigir(g["nivel_inicial"].nunique() == 1, "nivel_inicial deve ser constante na sessão")
    exigir(df.loc[df["ordem"] == 0, "n_respondidas"] == 0, "a primeira questão deve ter n_respondidas = 0")
    exigir(df["n_respondidas"] == np.minimum(df["ordem"], C.N_RESPONDIDAS_MAX), "n_respondidas ≠ min(ordem, 8)")
    blocos = int((df[COLUNA_GRUPO] != df[COLUNA_GRUPO].shift()).sum())
    exigir(blocos == df[COLUNA_GRUPO].nunique(), "as linhas de cada participante devem ser contíguas")

    if erros:
        raise ValueError("Dados inválidos:\n- " + "\n- ".join(erros))


def matriz(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """X (n, 13) float32 na ordem do contrato, y (n,) e grupos (n,).

    Usa SOMENTE as colunas do contrato. X ainda não está padronizado.
    """
    n = len(df)
    X = np.zeros((n, C.N_ENTRADAS), dtype=np.float32)
    for i, col in enumerate(C.FEATURES_NUMERICAS):
        X[:, i] = df[col].to_numpy(dtype=np.float32)
    X[np.arange(n), C.N_NUMERICAS + df["categoria"].to_numpy(dtype=int)] = 1.0
    y = df[COLUNA_ROTULO].to_numpy(dtype=np.float32)
    grupos = df[COLUNA_GRUPO].to_numpy()
    return X, y, grupos


# ---------------------------------------------------------------------------
# Divisão por participante
# ---------------------------------------------------------------------------

def _hash_ids(ids) -> str:
    arr = np.asarray(sorted(int(i) for i in ids), dtype="<i8")
    return hashlib.sha256(arr.tobytes()).hexdigest()


def dividir_participantes(ids, semente: int = SEMENTE_DIVISAO) -> dict[str, list[int]]:
    """Divide participantes em treino/validação/teste (70/15/15).

    ``GroupShuffleSplit`` faz uma divisão por vez; por isso são duas etapas
    (primeiro o teste, depois a validação). Os tamanhos são números inteiros
    de participantes, arredondados a partir das proporções do protocolo.
    """
    from sklearn.model_selection import GroupShuffleSplit

    unicos = np.unique(np.asarray(ids))
    n = len(unicos)
    n_teste = int(round(PROPORCOES["teste"] * n))
    n_val = int(round(PROPORCOES["validacao"] * n))
    if n_teste < 1 or n_val < 1 or n - n_teste - n_val < 1:
        raise ValueError(f"Participantes insuficientes para dividir: {n}.")

    gss = GroupShuffleSplit(n_splits=1, test_size=n_teste, random_state=semente)
    idx_resto, idx_teste = next(gss.split(unicos, groups=unicos))
    resto = unicos[idx_resto]
    gss = GroupShuffleSplit(n_splits=1, test_size=n_val, random_state=semente)
    idx_treino, idx_val = next(gss.split(resto, groups=resto))

    return {
        "treino": sorted(int(i) for i in resto[idx_treino]),
        "validacao": sorted(int(i) for i in resto[idx_val]),
        "teste": sorted(int(i) for i in unicos[idx_teste]),
    }


def verificar_sem_vazamento(divisao: dict[str, list[int]]) -> None:
    """Lança ValueError se algum participante estiver em mais de um conjunto."""
    for i, a in enumerate(CONJUNTOS):
        for b in CONJUNTOS[i + 1 :]:
            comum = set(divisao[a]) & set(divisao[b])
            if comum:
                raise ValueError(f"Vazamento: {len(comum)} participante(s) em '{a}' e '{b}', ex.: {sorted(comum)[:5]}")


def criar_split(
    caminho_dados: Path,
    df: pd.DataFrame | None = None,
    semente: int = SEMENTE_DIVISAO,
    versao: str = "split_v1",
) -> dict:
    """Monta o dicionário do arquivo de divisão para um CSV de dados."""
    caminho_dados = Path(caminho_dados)
    df = carregar(caminho_dados) if df is None else df
    fonte = str(df["fonte"].iloc[0])
    divisao = dividir_participantes(df[COLUNA_GRUPO], semente)
    verificar_sem_vazamento(divisao)
    linhas = {k: int(df[COLUNA_GRUPO].isin(v).sum()) for k, v in divisao.items()}
    return {
        "versao": versao,
        "protocolo": "docs/protocolo_avaliacao.md",
        "fonte": fonte,
        "metodo": "GroupShuffleSplit em duas etapas (teste, depois validação) sobre participante_id",
        "semente": semente,
        "proporcoes": PROPORCOES,
        "dados": {
            "arquivo": caminho_dados.name,
            "sha256": sha256_arquivo(caminho_dados),
            "versao_simulador": str(df["versao_simulador"].iloc[0]) if fonte == "SINTETICO" else None,
        },
        "ids_sha256": _hash_ids(df[COLUNA_GRUPO].unique()),
        "n_participantes": {k: len(v) for k, v in divisao.items()},
        "n_linhas": linhas,
        "participantes": divisao,
    }


def salvar_split(split: dict, caminho: Path) -> None:
    """Grava o JSON com as listas de IDs em uma linha cada (diffs legíveis)."""
    corpo = {k: v for k, v in split.items() if k != "participantes"}
    texto = json.dumps(corpo, ensure_ascii=False, indent=2)
    listas = ",\n".join(
        f'    "{k}": {json.dumps(split["participantes"][k], separators=(",", ":"))}' for k in CONJUNTOS
    )
    texto = texto[: texto.rfind("}")].rstrip() + ',\n  "participantes": {\n' + listas + "\n  }\n}\n"
    Path(caminho).parent.mkdir(parents=True, exist_ok=True)
    Path(caminho).write_text(texto, encoding="utf-8")


def carregar_split(caminho: Path) -> dict:
    split = json.loads(Path(caminho).read_text(encoding="utf-8"))
    verificar_sem_vazamento(split["participantes"])
    return split


def conjunto(df: pd.DataFrame, split: dict, nome: str, abrir_teste: bool = False) -> pd.DataFrame:
    """Linhas de um conjunto. O teste exige ``abrir_teste=True`` (teste lacrado)."""
    if nome not in CONJUNTOS:
        raise ValueError(f"Conjunto desconhecido: {nome!r}.")
    if nome == "teste" and not abrir_teste:
        raise ConjuntoLacradoError(
            "O conjunto de teste é lacrado (protocolo, seção 3): use abrir_teste=True só na avaliação final."
        )
    fonte = str(df["fonte"].iloc[0])
    if fonte != split["fonte"]:
        raise ValueError(f"Split da fonte {split['fonte']} aplicado a dados {fonte}.")
    if _hash_ids(df[COLUNA_GRUPO].unique()) != split["ids_sha256"]:
        raise ValueError("Os participantes dos dados não correspondem aos do split.")
    return df[df[COLUNA_GRUPO].isin(split["participantes"][nome])].reset_index(drop=True)


def conferir_hash_dados(split: dict, caminho_dados: Path) -> bool:
    """True se o CSV é byte a byte o usado para criar o split; senão emite aviso."""
    atual = sha256_arquivo(caminho_dados)
    if atual != split["dados"]["sha256"]:
        warnings.warn(
            "O CSV difere do usado na criação do split (outro ambiente ou outra versão do simulador). "
            "A divisão por participante continua válida, mas os resultados podem não ser idênticos.",
            stacklevel=2,
        )
        return False
    return True
