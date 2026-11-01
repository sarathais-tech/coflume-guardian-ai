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

``decidir_pergunta`` reúne a decisão completa de uma pergunta, inclusive o
fallback quando uma célula (nível × categoria) do banco está vazia, e devolve
tudo o que deve ir para o log (docs/fluxo_partida.md, seções 3 e 5).

``desbloqueio_referencia`` existe só para simulação e testes. A regra física
do cofre é implementada e validada pelo firmware, nunca pela Guardiã.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field
from typing import Callable, Mapping, Sequence

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


# ---------------------------------------------------------------------------
# Decisão completa de uma pergunta, com fallback de célula vazia
# ---------------------------------------------------------------------------

MOTIVO_PERGUNTA_1 = "nivel_inicial_pergunta_1"
MOTIVO_GUARDIA = "guardia"
MOTIVO_SEM_MODELO = "fallback_sem_modelo"
MOTIVO_PREVISAO_INVALIDA = "fallback_previsao_invalida"
MOTIVOS = (MOTIVO_PERGUNTA_1, MOTIVO_GUARDIA, MOTIVO_SEM_MODELO, MOTIVO_PREVISAO_INVALIDA)

TemPergunta = Callable[[int, int], bool]   # (nivel, categoria) -> há pergunta disponível?
Prever = Callable[[int, int], float]       # (nivel, categoria) -> P(acerto) da Guardiã


class BancoIncompletoError(RuntimeError):
    """Nenhuma categoria restante tem pergunta em algum nível permitido."""


@dataclass(frozen=True)
class Decisao:
    """Resultado de ``decidir_pergunta``: tudo o que vai para o log da pergunta."""

    ordem: int
    nivel_inicial: int
    categoria_sorteada: int
    categoria: int                         # categoria efetivamente apresentada
    niveis_permitidos: tuple[int, ...]
    niveis_disponiveis: tuple[int, ...]    # permitidos com pergunta no banco nesta categoria
    previsoes: dict[int, float] = field(default_factory=dict)  # só dos níveis disponíveis
    nivel: int = 0                         # nível efetivamente apresentado
    p_previsto: float = C.INVALIDO         # previsão DO NÍVEL APRESENTADO
    motivo: str = MOTIVO_GUARDIA

    @property
    def categoria_substituida(self) -> bool:
        return self.categoria != self.categoria_sorteada

    @property
    def celula_vazia(self) -> bool:
        return self.niveis_disponiveis != self.niveis_permitidos


def _valida(p: float) -> bool:
    return p != C.INVALIDO and math.isfinite(p) and 0.0 <= p <= 1.0


def _mais_proximo_do_inicial(niveis: Sequence[int], nivel_inicial: int) -> int:
    """Nível disponível mais próximo do inicial; empate -> o mais baixo."""
    return min(niveis, key=lambda n: (abs(n - nivel_inicial), n))


def decidir_pergunta(
    ordem: int,
    nivel_inicial: int,
    categorias_restantes: Sequence[int],
    tem_pergunta: TemPergunta,
    prever: Prever | None,
) -> Decisao:
    """Decide categoria e nível de uma pergunta do fluxo-0.8.

    1. Percorre ``categorias_restantes`` (ordem sorteada, sem as já usadas) e
       fica com a primeira que tenha pergunta em algum nível PERMITIDO.
    2. A Guardiã só avalia níveis DISPONÍVEIS (permitidos e com pergunta);
       assim a previsão registrada é sempre a do nível apresentado.
    3. Pergunta 1: nível inicial. Sem modelo ou com previsão inválida: nível
       inicial se disponível, senão o disponível mais próximo dele.

    O nível escolhido está SEMPRE em ``niveis_permitidos``.
    """
    if not categorias_restantes:
        raise ValueError("Não há categorias restantes.")
    permitidos = tuple(niveis_permitidos(ordem, nivel_inicial))
    for categoria in categorias_restantes:
        disponiveis = tuple(n for n in permitidos if tem_pergunta(n, categoria))
        if disponiveis:
            break
    else:
        raise BancoIncompletoError(
            f"Sem perguntas nos níveis {list(permitidos)} para as categorias {list(categorias_restantes)}."
        )

    previsoes = {n: float(prever(n, categoria)) for n in disponiveis} if prever is not None else {}
    base = dict(
        ordem=ordem,
        nivel_inicial=nivel_inicial,
        categoria_sorteada=int(categorias_restantes[0]),
        categoria=int(categoria),
        niveis_permitidos=permitidos,
        niveis_disponiveis=disponiveis,
        previsoes=previsoes,
    )

    if ordem == 0:
        nivel, motivo = nivel_inicial, MOTIVO_PERGUNTA_1
    elif prever is None:
        nivel, motivo = _mais_proximo_do_inicial(disponiveis, nivel_inicial), MOTIVO_SEM_MODELO
    elif not all(_valida(p) for p in previsoes.values()):
        nivel, motivo = _mais_proximo_do_inicial(disponiveis, nivel_inicial), MOTIVO_PREVISAO_INVALIDA
    else:
        nivel, motivo = escolher_nivel(previsoes, nivel_inicial), MOTIVO_GUARDIA

    assert nivel in disponiveis and nivel in permitidos
    p = previsoes.get(nivel, C.INVALIDO)
    return Decisao(**base, nivel=nivel, p_previsto=p if _valida(p) else C.INVALIDO, motivo=motivo)


def problemas_de_viabilidade(tem_pergunta: TemPergunta) -> list[str]:
    """Verifica se o banco sustenta qualquer partida do fluxo-0.8.

    Testa os 3 níveis iniciais × as 24 ordens possíveis das 4 categorias. Como
    os níveis permitidos dependem só do nível inicial e da posição, e não das
    escolhas anteriores, isso cobre todas as partidas possíveis.
    """
    problemas = []
    for ini in range(C.N_NIVEIS):
        falhas = []
        for ordem_cat in itertools.permutations(range(C.N_CATEGORIAS)):
            restantes = list(ordem_cat)
            try:
                for k in range(N_PERGUNTAS):
                    d = decidir_pergunta(k, ini, restantes, tem_pergunta, None)
                    restantes.remove(d.categoria)
            except BancoIncompletoError as e:
                falhas.append(f"categorias sorteadas {list(ordem_cat)}, pergunta {k + 1}: {e}")
        if falhas:
            problemas.append(
                f"nível inicial {ini}: {len(falhas)} de 24 ordens de categorias falham (ex.: {falhas[0]})"
            )
    return problemas
