"""Cálculo das features da Guardiã IA.

Implementação de referência de docs/features.md. A versão C++
(guardia::montar_entrada em embarcado/runtime/guardia_runtime.h) deve produzir
exatamente os mesmos valores; os testes de equivalência verificam isso.

Toda a aritmética usa float32, na mesma ordem do código C++, para que as duas
implementações coincidam bit a bit.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

import numpy as np

from guardia import contrato as C

F32 = np.float32


@dataclass(frozen=True)
class Resposta:
    """Uma questão respondida na sessão. Não contém nenhum dado pessoal."""

    categoria: int        # 0..3
    nivel: int            # 0..2
    acertou: bool         # tempo esgotado conta como erro
    tempo_gasto_s: float  # >= 0
    tempo_limite_s: float # > 0
    usou_dica: bool


@dataclass(frozen=True)
class Entrada:
    """Features já calculadas, ainda não padronizadas."""

    nivel_candidato: int
    nivel_inicial: int
    n_respondidas: int
    categoria: int
    taxa_acerto_sessao: float
    taxa_acerto_categoria: float
    tempo_medio_norm: float
    dicas_por_questao: float
    resultado_ultima: int
    sequencia: int


def _razao_tempo(r: Resposta) -> np.float32:
    gasto, limite = F32(r.tempo_gasto_s), F32(r.tempo_limite_s)
    if not (math.isfinite(gasto) and math.isfinite(limite)) or limite <= F32(0):
        return F32(1.0)  # tratado como tempo esgotado
    razao = F32(gasto / limite)
    if razao < F32(0):
        return F32(0.0)
    if razao > F32(1):
        return F32(1.0)
    return razao


def _sequencia(hist: Sequence[Resposta]) -> int:
    if not hist:
        return 0
    ultimo = hist[-1].acertou
    tamanho = 0
    for r in reversed(hist):
        if r.acertou != ultimo or tamanho == C.SEQUENCIA_MAX:
            break
        tamanho += 1
    return tamanho if ultimo else -tamanho


def montar_entrada(
    historico: Sequence[Resposta],
    nivel_inicial: int,
    categoria: int,
    nivel_candidato: int,
) -> Entrada:
    """Calcula as features para avaliar uma questão candidata.

    Com histórico vazio (primeira questão), devolve os valores neutros
    definidos em docs/features.md, seção 4.
    """
    hist = list(historico)[: C.HIST_MAX]
    n = len(hist)

    acertos = F32(0)
    acertos_cat = F32(0)
    n_cat = F32(0)
    soma_tempo = F32(0)
    dicas = F32(0)
    for r in hist:
        if r.acertou:
            acertos = F32(acertos + F32(1))
        if r.categoria == categoria:
            n_cat = F32(n_cat + F32(1))
            if r.acertou:
                acertos_cat = F32(acertos_cat + F32(1))
        soma_tempo = F32(soma_tempo + _razao_tempo(r))
        if r.usou_dica:
            dicas = F32(dicas + F32(1))

    if n > 0:
        nf = F32(n)
        taxa_sessao = F32(acertos / nf)
        tempo_medio = F32(soma_tempo / nf)
        dicas_q = F32(dicas / nf)
        resultado_ultima = 1 if hist[-1].acertou else -1
    else:
        taxa_sessao = F32(C.FRIO_TAXA)
        tempo_medio = F32(C.FRIO_TEMPO)
        dicas_q = F32(C.FRIO_DICAS)
        resultado_ultima = 0

    taxa_cat = F32(acertos_cat / n_cat) if n_cat > F32(0) else taxa_sessao

    return Entrada(
        nivel_candidato=int(nivel_candidato),
        nivel_inicial=int(nivel_inicial),
        n_respondidas=min(n, C.N_RESPONDIDAS_MAX),
        categoria=int(categoria),
        taxa_acerto_sessao=float(taxa_sessao),
        taxa_acerto_categoria=float(taxa_cat),
        tempo_medio_norm=float(tempo_medio),
        dicas_por_questao=float(dicas_q),
        resultado_ultima=resultado_ultima,
        sequencia=_sequencia(hist),
    )


def _no_intervalo(v: float, lo: float, hi: float) -> bool:
    return math.isfinite(v) and lo <= v <= hi


def entrada_valida(e: Entrada) -> bool:
    """Mesmas regras de guardia::entrada_valida no C++."""
    return (
        0 <= e.nivel_candidato < C.N_NIVEIS
        and 0 <= e.nivel_inicial < C.N_NIVEIS
        and 0 <= e.categoria < C.N_CATEGORIAS
        and 0 <= e.n_respondidas <= C.N_RESPONDIDAS_MAX
        and _no_intervalo(e.taxa_acerto_sessao, 0.0, 1.0)
        and _no_intervalo(e.taxa_acerto_categoria, 0.0, 1.0)
        and _no_intervalo(e.tempo_medio_norm, 0.0, 1.0)
        and _no_intervalo(e.dicas_por_questao, 0.0, 1.0)
        and -1 <= e.resultado_ultima <= 1
        and -C.SEQUENCIA_MAX <= e.sequencia <= C.SEQUENCIA_MAX
    )


def vetorizar(e: Entrada) -> np.ndarray:
    """Vetor de 13 posições (float32), na ordem de docs/features.md, seção 3.

    As posições 0..8 ainda NÃO estão padronizadas; a padronização faz parte
    do modelo (média e desvio do treino).
    """
    x = np.zeros(C.N_ENTRADAS, dtype=np.float32)
    x[0] = e.nivel_candidato
    x[1] = e.nivel_inicial
    x[2] = e.n_respondidas
    x[3] = e.taxa_acerto_sessao
    x[4] = e.taxa_acerto_categoria
    x[5] = e.tempo_medio_norm
    x[6] = e.dicas_por_questao
    x[7] = e.resultado_ultima
    x[8] = e.sequencia
    x[C.N_NUMERICAS + e.categoria] = 1.0
    return x
