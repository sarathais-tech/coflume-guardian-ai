"""Testes da especificação das features (docs/features.md)."""

import dataclasses
import math

import numpy as np
import pytest

from guardia import contrato as C
from guardia.features import Entrada, Resposta, entrada_valida, montar_entrada, vetorizar


def r(cat=0, nivel=1, acertou=True, gasto=10.0, limite=30.0, dica=False):
    return Resposta(cat, nivel, acertou, gasto, limite, dica)


class TestPartidaAFrio:
    @pytest.mark.parametrize("nivel_inicial", range(3))
    @pytest.mark.parametrize("categoria", range(4))
    @pytest.mark.parametrize("nivel_candidato", range(3))
    def test_valores_neutros(self, nivel_inicial, categoria, nivel_candidato):
        e = montar_entrada([], nivel_inicial, categoria, nivel_candidato)
        assert e.n_respondidas == 0
        assert e.taxa_acerto_sessao == C.FRIO_TAXA
        assert e.taxa_acerto_categoria == C.FRIO_TAXA
        assert e.tempo_medio_norm == C.FRIO_TEMPO
        assert e.dicas_por_questao == C.FRIO_DICAS
        assert e.resultado_ultima == 0
        assert e.sequencia == 0
        assert entrada_valida(e)

    def test_sem_historico_difere_de_ter_errado(self):
        """Motivo do ADR 0007: 'sem histórico' não pode ser igual a 'errou'."""
        frio = montar_entrada([], 1, 0, 1)
        errou = montar_entrada([r(acertou=False)], 1, 0, 1)
        assert frio.resultado_ultima == 0
        assert errou.resultado_ultima == -1


class TestCalculo:
    def test_taxas(self):
        hist = [r(cat=0, acertou=True), r(cat=1, acertou=False), r(cat=0, acertou=False), r(cat=2, acertou=True)]
        e = montar_entrada(hist, 1, 0, 1)
        assert e.taxa_acerto_sessao == pytest.approx(0.5)
        assert e.taxa_acerto_categoria == pytest.approx(0.5)
        e3 = montar_entrada(hist, 1, 3, 1)
        assert e3.taxa_acerto_categoria == e3.taxa_acerto_sessao  # categoria ainda não vista

    def test_tempo_normalizado_e_limitado(self):
        hist = [r(gasto=15, limite=30), r(gasto=45, limite=30), r(gasto=-3, limite=30)]
        e = montar_entrada(hist, 0, 0, 0)
        assert e.tempo_medio_norm == pytest.approx((0.5 + 1.0 + 0.0) / 3)

    @pytest.mark.parametrize("limite", [0.0, -5.0, float("nan"), float("inf")])
    def test_limite_invalido_conta_como_esgotado(self, limite):
        e = montar_entrada([r(gasto=10, limite=limite)], 0, 0, 0)
        assert e.tempo_medio_norm == 1.0

    def test_dicas(self):
        e = montar_entrada([r(dica=True), r(dica=False), r(dica=True), r(dica=True)], 0, 0, 0)
        assert e.dicas_por_questao == pytest.approx(0.75)

    @pytest.mark.parametrize(
        "resultados, esperado",
        [
            ([True], 1),
            ([False], -1),
            ([True, True], 2),
            ([False, True, True, True, True], 3),
            ([True, False, False], -2),
            ([False] * 6, -3),
            ([True, False], -1),
        ],
    )
    def test_sequencia(self, resultados, esperado):
        e = montar_entrada([r(acertou=a) for a in resultados], 0, 0, 0)
        assert e.sequencia == esperado

    def test_n_respondidas_limitado(self):
        e = montar_entrada([r()] * 12, 0, 0, 0)
        assert e.n_respondidas == C.N_RESPONDIDAS_MAX

    def test_historico_alem_do_maximo_e_ignorado(self):
        hist = [r(acertou=True)] * C.HIST_MAX + [r(acertou=False)] * 4
        e = montar_entrada(hist, 0, 0, 0)
        assert e.taxa_acerto_sessao == 1.0


class TestVetor:
    def test_ordem_e_onehot(self):
        e = montar_entrada([r(cat=2, acertou=False, dica=True)], 1, 3, 2)
        x = vetorizar(e)
        assert x.dtype == np.float32 and x.shape == (C.N_ENTRADAS,)
        assert x[0] == 2 and x[1] == 1 and x[2] == 1
        assert x[7] == -1 and x[8] == -1
        assert list(x[C.N_NUMERICAS:]) == [0, 0, 0, 1]

    def test_nomes_batem_com_contrato(self):
        campos = {f.name for f in dataclasses.fields(Entrada)}
        assert set(C.FEATURES_NUMERICAS) <= campos


class TestValidacao:
    @pytest.mark.parametrize(
        "campo, valor",
        [
            ("nivel_candidato", 3), ("nivel_inicial", -1), ("categoria", 4), ("n_respondidas", 9),
            ("taxa_acerto_sessao", 1.01), ("taxa_acerto_categoria", math.nan),
            ("tempo_medio_norm", -0.01), ("dicas_por_questao", 1.5),
            ("resultado_ultima", 2), ("sequencia", -4),
        ],
    )
    def test_fora_da_faixa(self, campo, valor):
        e = dataclasses.replace(montar_entrada([], 1, 0, 1), **{campo: valor})
        assert not entrada_valida(e)


def test_resposta_nao_tem_dados_pessoais():
    """Garante que ninguém adicione campos identificadores sem revisão."""
    campos = {f.name for f in dataclasses.fields(Resposta)}
    assert campos == {"categoria", "nivel", "acertou", "tempo_gasto_s", "tempo_limite_s", "usou_dica"}
