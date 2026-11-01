"""Simulador de sessões SINTÉTICAS de participantes do Coflume.

Todo dado gerado aqui tem ``fonte = "SINTETICO"``. Ele serve para construir e
testar o pipeline e para comparar modelos em ambiente controlado; não comprova
eficácia educacional nem representa crianças reais (ver docs/simulador.md).

Modelo de resposta (inspirado na Teoria de Resposta ao Item, 3 parâmetros):

    P(correta | dica) = c + (1 - c) * sigmoide(a * (theta_cat - b) + efeito_dica * dica)

- ``theta_cat``: habilidade latente do participante na categoria;
- ``b``: dificuldade da questão (depende do nível, mais variação por questão);
- ``c = 0,25``: acerto ao acaso com 4 alternativas;
- a dica é decidida antes da resposta, com probabilidade maior quando a
  questão está acima da habilidade;
- o tempo de resposta é log-normal, mais lento em questões difíceis e com dica;
  passar do limite conta como erro (tempo esgotado).

As features de cada linha são calculadas por ``guardia.features.montar_entrada``
com o histórico ANTERIOR à questão, exatamente como no runtime embarcado.

``p_real`` é a probabilidade verdadeira de acerto no momento da escolha da
questão (antes de se saber se haverá dica ou tempo esgotado). Só existe em dados
sintéticos e NUNCA pode ser usada como feature.

Versões (ver docs/simulador.md):

- ``sim-1.0``: 3 principais + reforço após erro, nível livre (histórico; ADR 0008).
- ``sim-1.1``: fluxo-0.8 — exatamente 3 perguntas, 1ª no nível escolhido,
  2ª e 3ª na faixa ±1, sem reforço, sem ganho após erro (ADR 0009).

Em ambas, o nível é SORTEADO (política exploratória de coleta). A política
adaptativa do cofre, que escolhe o nível pela previsão da Guardiã, está em
``guardia/politica.py`` e não é usada para gerar dados de treino.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import platform
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from guardia import contrato as C
from guardia import politica
from guardia.features import Resposta, montar_entrada

VERSAO_SIMULADOR = "sim-1.1"  # versão padrão
SEMENTE_PADRAO = 2026
POLITICA_COLETA = "exploratoria-uniforme"

# versão -> (nome do conjunto, participantes padrão)
CONJUNTOS_POR_VERSAO = {"sim-1.0": ("sessoes_v1", 3000), "sim-1.1": ("sessoes_v2", 4000)}
N_PARTICIPANTES_PADRAO = CONJUNTOS_POR_VERSAO[VERSAO_SIMULADOR][1]

TIPO_PRINCIPAL = "principal"
TIPO_REFORCO = "reforco"

COLUNAS = (
    "fonte",
    "versao_simulador",
    "participante_id",
    "ordem",
    "tipo",
    "nivel_inicial",
    "categoria",
    "nivel_candidato",
    "n_respondidas",
    "taxa_acerto_sessao",
    "taxa_acerto_categoria",
    "tempo_medio_norm",
    "dicas_por_questao",
    "resultado_ultima",
    "sequencia",
    "acertou",
    "resp_usou_dica",
    "resp_tempo_gasto_s",
    "resp_tempo_limite_s",
    "resp_esgotou",
    "p_real",
)


@dataclass(frozen=True)
class ParametrosSimulador:
    """Parâmetros do simulador. Justificativas em docs/simulador.md.

    Nenhum valor foi ajustado para favorecer algum modelo (protocolo, seção 8).
    Os valores padrão são os do ``sim-1.1``; use ``parametros_da_versao``.
    """

    versao: str = "sim-1.1"

    # População
    prob_nivel_inicial: tuple[float, float, float] = (0.40, 0.35, 0.25)
    media_habilidade_por_nivel_inicial: tuple[float, float, float] = (-0.7, 0.0, 0.7)
    dp_habilidade_geral: float = 0.8
    dp_habilidade_categoria: float = 0.5

    # Questões e resposta (3PL)
    dificuldade_por_nivel: tuple[float, float, float] = (-1.0, 0.0, 1.0)
    dp_dificuldade_questao: float = 0.3
    discriminacao: float = 1.2
    acerto_ao_acaso: float = 0.25
    efeito_dica: float = 0.8
    ganho_feedback_apos_erro: float = 0.0

    # Uso de dica
    dica_intercepto: float = -1.2
    dica_inclinacao: float = 1.0
    dp_propensao_dica: float = 0.8

    # Tempo de resposta
    tempo_limite_s: float = 30.0
    tempo_base_s: float = 10.0
    tempo_efeito_dificuldade: float = 0.3
    tempo_extra_dica_s: float = 4.0
    dp_log_velocidade: float = 0.25
    dp_log_tempo: float = 0.45

    # Fluxo da partida (ver docs/simulador.md, seção 3)
    n_principais: int = 3
    reforco_apos_erro: bool = False
    prob_reforco_mesmo_nivel: float = 0.5
    primeira_no_nivel_inicial: bool = True       # fluxo-0.8
    faixa_nivel: int | None = politica.FAIXA_NIVEL  # None = qualquer nível (sim-1.0)

    def __post_init__(self) -> None:
        if not self.versao:
            raise ValueError("versao é obrigatória.")
        if abs(sum(self.prob_nivel_inicial) - 1.0) > 1e-9:
            raise ValueError("prob_nivel_inicial deve somar 1.")
        if not 1 <= self.n_principais <= C.N_CATEGORIAS:
            raise ValueError("n_principais deve estar entre 1 e 4 (categorias distintas).")
        if self.n_principais * 2 > C.HIST_MAX:
            raise ValueError("Sessão maior que o histórico máximo do contrato.")
        if not 0.0 <= self.acerto_ao_acaso < 1.0:
            raise ValueError("acerto_ao_acaso deve estar em [0, 1).")
        if self.tempo_limite_s <= 0:
            raise ValueError("tempo_limite_s deve ser positivo.")
        if self.faixa_nivel is not None and self.faixa_nivel < 0:
            raise ValueError("faixa_nivel deve ser None ou >= 0.")


PARAMETROS_POR_VERSAO = {
    "sim-1.0": ParametrosSimulador(
        versao="sim-1.0",
        ganho_feedback_apos_erro=0.3,
        reforco_apos_erro=True,
        primeira_no_nivel_inicial=False,
        faixa_nivel=None,
    ),
    "sim-1.1": ParametrosSimulador(versao="sim-1.1"),
}


def parametros_da_versao(versao: str) -> ParametrosSimulador:
    if versao not in PARAMETROS_POR_VERSAO:
        raise ValueError(f"Versão desconhecida: {versao!r}. Use uma de {sorted(PARAMETROS_POR_VERSAO)}.")
    return PARAMETROS_POR_VERSAO[versao]


def _sigmoide(z: float) -> float:
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    e = math.exp(z)
    return e / (1.0 + e)


def _cdf_normal(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


class _Participante:
    """Estado latente de um participante simulado (nunca exportado)."""

    def __init__(self, pid: int, semente: int, p: ParametrosSimulador) -> None:
        # Gerador próprio por participante: o participante i é idêntico qualquer
        # que seja o número total de participantes gerados.
        self.rng = np.random.default_rng(np.random.SeedSequence(semente, spawn_key=(pid,)))
        self.pid = pid
        self.p = p
        self.nivel_inicial = int(self.rng.choice(C.N_NIVEIS, p=p.prob_nivel_inicial))
        geral = self.rng.normal(p.media_habilidade_por_nivel_inicial[self.nivel_inicial], p.dp_habilidade_geral)
        self.theta = geral + self.rng.normal(0.0, p.dp_habilidade_categoria, C.N_CATEGORIAS)
        self.propensao_dica = float(self.rng.normal(0.0, p.dp_propensao_dica))
        self.velocidade = float(math.exp(self.rng.normal(0.0, p.dp_log_velocidade)))
        self.historico: list[Resposta] = []
        self.linhas: list[dict] = []

    # ---- componentes do modelo de resposta --------------------------------
    def _p_correta(self, theta: float, b: float, dica: int) -> float:
        p = self.p
        return p.acerto_ao_acaso + (1 - p.acerto_ao_acaso) * _sigmoide(
            p.discriminacao * (theta - b) + p.efeito_dica * dica
        )

    def _mediana_tempo(self, theta: float, b: float, dica: int) -> float:
        p = self.p
        base = p.tempo_base_s * math.exp(p.tempo_efeito_dificuldade * (b - theta))
        return (base + p.tempo_extra_dica_s * dica) * self.velocidade

    def _p_esgotar(self, mediana: float) -> float:
        z = (math.log(self.p.tempo_limite_s) - math.log(mediana)) / self.p.dp_log_tempo
        return 1.0 - _cdf_normal(z)

    # ---- uma questão -------------------------------------------------------
    def responder(self, categoria: int, nivel: int, tipo: str) -> bool:
        p, rng = self.p, self.rng
        entrada = montar_entrada(self.historico, self.nivel_inicial, categoria, nivel)

        theta = float(self.theta[categoria])
        b = p.dificuldade_por_nivel[nivel] + float(rng.normal(0.0, p.dp_dificuldade_questao))
        p_dica = _sigmoide(p.dica_intercepto + p.dica_inclinacao * (b - theta) + self.propensao_dica)

        # Probabilidade verdadeira no momento da escolha (dica e tempo ainda incertos).
        p_real = 0.0
        for dica, peso in ((0, 1.0 - p_dica), (1, p_dica)):
            sem_esgotar = 1.0 - self._p_esgotar(self._mediana_tempo(theta, b, dica))
            p_real += peso * sem_esgotar * self._p_correta(theta, b, dica)

        # Realização (ordem fixa de sorteios: dica, tempo, acerto).
        usou_dica = int(rng.random() < p_dica)
        tempo = self._mediana_tempo(theta, b, usou_dica) * math.exp(float(rng.normal(0.0, p.dp_log_tempo)))
        u_acerto = float(rng.random())
        esgotou = tempo >= p.tempo_limite_s
        if esgotou:
            tempo = p.tempo_limite_s
            acertou = False
        else:
            acertou = u_acerto < self._p_correta(theta, b, usou_dica)
        tempo = round(tempo, 2)  # resolução registrada; as features usam este mesmo valor

        self.linhas.append(
            {
                "fonte": "SINTETICO",
                "versao_simulador": p.versao,
                "participante_id": self.pid,
                "ordem": len(self.historico),
                "tipo": tipo,
                "nivel_inicial": entrada.nivel_inicial,
                "categoria": entrada.categoria,
                "nivel_candidato": entrada.nivel_candidato,
                "n_respondidas": entrada.n_respondidas,
                "taxa_acerto_sessao": entrada.taxa_acerto_sessao,
                "taxa_acerto_categoria": entrada.taxa_acerto_categoria,
                "tempo_medio_norm": entrada.tempo_medio_norm,
                "dicas_por_questao": entrada.dicas_por_questao,
                "resultado_ultima": entrada.resultado_ultima,
                "sequencia": entrada.sequencia,
                "acertou": int(acertou),
                "resp_usou_dica": usou_dica,
                "resp_tempo_gasto_s": tempo,
                "resp_tempo_limite_s": p.tempo_limite_s,
                "resp_esgotou": int(esgotou),
                "p_real": p_real,
            }
        )
        self.historico.append(
            Resposta(categoria, nivel, acertou, tempo, p.tempo_limite_s, bool(usou_dica))
        )
        if not acertou:
            # Após um erro o jogo mostra uma explicação: pequeno ganho na categoria.
            self.theta[categoria] += p.ganho_feedback_apos_erro
        return acertou

    # ---- uma partida -------------------------------------------------------
    def jogar(self) -> list[dict]:
        p, rng = self.p, self.rng
        categorias = [int(c) for c in rng.permutation(C.N_CATEGORIAS)[: p.n_principais]]
        ini = self.nivel_inicial
        for k, categoria in enumerate(categorias):
            # Política de COLETA exploratória: o nível é SORTEADO entre os permitidos.
            # Não é a política adaptativa do cofre (guardia.politica.escolher_nivel).
            if k == 0 and p.primeira_no_nivel_inicial:
                nivel = politica.niveis_permitidos(0, ini)[0]  # fluxo-0.8: nível escolhido
            elif k == 0:
                # sim-1.0: nivel_inicial ou um abaixo (sequência de sorteios preservada)
                opcoes = sorted({max(ini - 1, 0), ini})
                nivel = int(rng.choice(opcoes))
            elif p.faixa_nivel is None:
                nivel = int(rng.integers(C.N_NIVEIS))  # sim-1.0: qualquer nível
            else:
                # sim-1.1: mesmos níveis que o cofre pode consultar (faixa ±1)
                nivel = int(rng.choice(politica.niveis_permitidos(1, ini, p.faixa_nivel)))
            if not self.responder(categoria, nivel, TIPO_PRINCIPAL) and p.reforco_apos_erro:
                mesmo = rng.random() < p.prob_reforco_mesmo_nivel
                nivel_ref = nivel if mesmo else max(nivel - 1, 0)
                self.responder(categoria, nivel_ref, TIPO_REFORCO)
        return self.linhas


def simular(
    n_participantes: int = N_PARTICIPANTES_PADRAO,
    semente: int = SEMENTE_PADRAO,
    parametros: ParametrosSimulador | None = None,
) -> list[dict]:
    """Gera as linhas de ``n_participantes`` sessões, em ordem de participante e questão."""
    if n_participantes < 1:
        raise ValueError("n_participantes deve ser positivo.")
    p = parametros or parametros_da_versao(VERSAO_SIMULADOR)
    linhas: list[dict] = []
    for pid in range(n_participantes):
        linhas.extend(_Participante(pid, semente, p).jogar())
    return linhas


# ---------------------------------------------------------------------------
# Serialização
# ---------------------------------------------------------------------------

_FLOAT32_COLS = {"taxa_acerto_sessao", "taxa_acerto_categoria", "tempo_medio_norm", "dicas_por_questao"}


def _formatar(col: str, v) -> str:
    if col in _FLOAT32_COLS:
        return f"{float(np.float32(v)):.9g}"  # reconstrói o mesmo float32 ao ler
    if col in ("resp_tempo_gasto_s", "resp_tempo_limite_s"):
        return f"{v:.2f}"
    if col == "p_real":
        return f"{v:.6f}"
    return str(v)


def para_csv(linhas: list[dict]) -> bytes:
    """CSV em UTF-8 com fim de linha '\\n' (bytes idênticos em qualquer sistema)."""
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(COLUNAS)
    for linha in linhas:
        w.writerow([_formatar(c, linha[c]) for c in COLUNAS])
    return buf.getvalue().encode("utf-8")


def gerar_arquivo(
    caminho: Path,
    n_participantes: int = N_PARTICIPANTES_PADRAO,
    semente: int = SEMENTE_PADRAO,
    parametros: ParametrosSimulador | None = None,
) -> dict:
    """Gera o CSV e o manifesto ``<nome>.manifest.json`` ao lado dele.

    Recusa gravar fora de uma pasta chamada ``sinteticos`` (docs/dados.md).
    """
    caminho = Path(caminho)
    if "sinteticos" not in caminho.parent.parts:
        raise ValueError(
            f"Dados SINTÉTICOS só podem ser gravados numa pasta 'sinteticos' (recebido: {caminho.parent})."
        )
    p = parametros or parametros_da_versao(VERSAO_SIMULADOR)
    conteudo = para_csv(simular(n_participantes, semente, p))
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_bytes(conteudo)

    n_linhas = conteudo.count(b"\n") - 1
    manifesto = {
        "projeto": "Coflume — O Conhecimento Abre Portas",
        "ia": "Guardiã IA",
        "fonte": "SINTETICO",
        "arquivo": caminho.name,
        "versao_simulador": p.versao,
        "politica_coleta": POLITICA_COLETA,
        "fluxo": politica.VERSAO_FLUXO if p.versao == "sim-1.1" else None,
        "semente": semente,
        "n_participantes": n_participantes,
        "n_linhas": n_linhas,
        "sha256": hashlib.sha256(conteudo).hexdigest(),
        "contrato": C.CONTRATO_VERSAO,
        "parametros": asdict(p),
        "ambiente": {
            "python": platform.python_version(),
            "numpy": np.__version__,
        },
        "aviso": "Dados SINTÉTICOS: não representam crianças reais e não comprovam eficácia educacional.",
    }
    texto = json.dumps(manifesto, ensure_ascii=False, indent=2) + "\n"
    caminho.with_name(caminho.stem + ".manifest.json").write_text(texto, encoding="utf-8")
    return json.loads(texto)  # exatamente o que foi gravado (tuplas viram listas)
