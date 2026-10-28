"""Constantes do contrato de integração (docs/contrato_integracao.md).

Qualquer alteração aqui deve ser espelhada em embarcado/runtime/guardia_runtime.h;
o teste tests/test_contrato.py verifica a consistência entre os dois.
"""

CONTRATO_MAJOR = 1
CONTRATO_MINOR = 0
CONTRATO_PATCH = 0
CONTRATO_VERSAO = f"{CONTRATO_MAJOR}.{CONTRATO_MINOR}.{CONTRATO_PATCH}"

N_CATEGORIAS = 4  # 0 Matemática, 1 Português, 2 Lógica, 3 Conhecimentos gerais
N_NIVEIS = 3      # 0 Explorador, 1 Desafiante, 2 Mestre
HIST_MAX = 16
N_RESPONDIDAS_MAX = 8
SEQUENCIA_MAX = 3

# Ordem das features numéricas (posições 0..8 do vetor; padronizadas).
FEATURES_NUMERICAS = (
    "nivel_candidato",
    "nivel_inicial",
    "n_respondidas",
    "taxa_acerto_sessao",
    "taxa_acerto_categoria",
    "tempo_medio_norm",
    "dicas_por_questao",
    "resultado_ultima",
    "sequencia",
)
N_NUMERICAS = len(FEATURES_NUMERICAS)          # 9
N_ENTRADAS = N_NUMERICAS + N_CATEGORIAS        # 13

# Valores neutros quando não há histórico (partida a frio).
FRIO_TAXA = 0.5
FRIO_TEMPO = 0.5
FRIO_DICAS = 0.0

INVALIDO = -1.0

FONTES_VALIDAS = ("SINTETICO", "REAL", "MISTO", "ALEATORIO")
FONTE_PREFIXO = {"SINTETICO": "sint", "REAL": "real", "MISTO": "misto", "ALEATORIO": "aleat"}
