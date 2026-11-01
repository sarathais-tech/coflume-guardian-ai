"""Política de jogo do fluxo-0.8 (docs/fluxo_partida.md) — implementação de REFERÊNCIA.

Este módulo descreve, em Python, as decisões que o firmware v0.8 vai tomar.
Ele NÃO é Machine Learning: é lógica tradicional que USA a previsão da Guardiã.

Duas políticas diferentes existem no projeto e não devem ser confundidas:

- **Política adaptativa (cofre)** — ``escolher_nivel``: entre os níveis
  permitidos, escolhe o de previsão mais próxima de 70%. Roda no ESP32-S3.
- **Política exploratória (coleta de dados sintéticos)** — no simulador:
  sorteia o nível uniformemente entre os MESMOS níveis permitidos. Serve só
  para gerar dados de treino sem viés de seleção (ADR 0008 e 0009).

As duas compartilham ``niveis_permitidos``: o modelo é treinado exatamente
sobre os níveis que o cofre pode consultar.

``desbloqueio_referencia`` existe só para simulação e testes. A regra física
do cofre é implementada e validada pelo firmware, nunca pela Guardiã.
"""

from __future__ import annotations

import math
from typing import Mapping, Sequence

from guardia import contrato as C

VERSAO_FLUXO = "fluxo-0.8"
N_PERGUNTAS = 3
ALVO_P_ACERTO = 0.70
FAIXA_NIVEL = 1
ACERTOS_PARA_DESBLOQUEIO = 2
TOLERANCIA_EMPATE = 1e-6


def niveis_permitidos(ordem: int, nivel_inicial: int, faixa: int = FAIXA_NIVEL) -> list[int]:
    """Níveis que podem ser oferecidos na pergunta ``ordem`` (0 = primeira).

    - Pergunta 1: somente o nível escolhido pela criança.
    - Perguntas 2 e 3: nível inicial ± ``faixa``, limitado a 0..2.
    """
    if not 0 <= nivel_inicial < C.N_NIVEIS:
        raise ValueError(f"nivel_inicial inválido: {nivel_inicial}")
    if not 0 <= ordem < N_PERGUNTAS:
        raise ValueError(f"ordem inválida no fluxo-0.8: {ordem}")
    if ordem == 0:
        return [nivel_inicial]
    return [n for n in range(C.N_NIVEIS) if abs(n - nivel_inicial) <= faixa]


def escolher_nivel(previsoes: Mapping[int, float], nivel_inicial: int, alvo: float = ALVO_P_ACERTO) -> int:
    """Política ADAPTATIVA do cofre.

    ``previsoes`` mapeia cada nível permitido para P(acerto) da Guardiã.

    - Escolhe o nível com |P − alvo| mínimo.
    - Empate: prefere o nível inicial; entre dois níveis diferentes do
      inicial, prefere o mais baixo (menos frustrante).
    - Qualquer previsão inválida (INVALIDO, NaN, fora de [0, 1]) ou ausência
      de previsões: usa o nível inicial (fallback do contrato, seção 5).
    """
    if not previsoes:
        return nivel_inicial
    for p in previsoes.values():
        if p == C.INVALIDO or not math.isfinite(p) or not 0.0 <= p <= 1.0:
            return nivel_inicial

    def chave(n: int) -> tuple[int, int, int]:
        # Distâncias que diferem menos que TOLERANCIA_EMPATE contam como empate
        # (evita que arredondamentos de ponto flutuante decidam a escolha).
        distancia = round(abs(previsoes[n] - alvo) / TOLERANCIA_EMPATE)
        return (distancia, 0 if n == nivel_inicial else 1, n)

    return min(previsoes, key=chave)


def desbloqueio_referencia(acertos: Sequence[bool]) -> bool:
    """Regra do cofre (v0.7 e v0.8): pelo menos 2 acertos nas 3 perguntas.

    Referência para simulação. No cofre, quem decide é o validador do firmware.
    """
    if len(acertos) != N_PERGUNTAS:
        raise ValueError(f"A partida do {VERSAO_FLUXO} tem exatamente {N_PERGUNTAS} perguntas.")
    return sum(bool(a) for a in acertos) >= ACERTOS_PARA_DESBLOQUEIO
