"""Decisão completa de uma pergunta no fluxo-0.8, inclusive com células vazias no banco."""

import itertools
import math

import numpy as np
import pytest

from guardia import contrato as C
from guardia.politica import (
    MOTIVO_GUARDIA,
    MOTIVO_PERGUNTA_1,
    MOTIVO_PREVISAO_INVALIDA,
    MOTIVO_SEM_MODELO,
    BancoIncompletoError,
    decidir_pergunta,
    niveis_permitidos,
    problemas_de_viabilidade,
)

CHEIO = lambda n, c: True  # noqa: E731


def banco(*vazias):
    """Banco com todas as células preenchidas, exceto as (nivel, categoria) indicadas."""
    return lambda n, c: (n, c) not in set(vazias)


def prever_tabela(tabela):
    return lambda n, c: tabela[n]


class TestBancoCompleto:
    def test_pergunta_1_no_nivel_inicial_e_previsao_registrada(self):
        d = decidir_pergunta(0, 2, [3, 0, 1, 2], CHEIO, prever_tabela({2: 0.41}))
        assert (d.nivel, d.categoria, d.motivo) == (2, 3, MOTIVO_PERGUNTA_1)
        assert d.p_previsto == 0.41  # partida a frio registrada, mas não decide
        assert not d.celula_vazia and not d.categoria_substituida

    def test_guardia_escolhe_mais_proximo_de_70(self):
        d = decidir_pergunta(1, 1, [0, 2], CHEIO, prever_tabela({0: 0.9, 1: 0.8, 2: 0.68}))
        assert (d.nivel, d.motivo, d.p_previsto) == (2, MOTIVO_GUARDIA, 0.68)
        assert d.previsoes == {0: 0.9, 1: 0.8, 2: 0.68}


class TestCelulaVazia:
    def test_guardia_so_avalia_niveis_disponiveis(self):
        # Desafiante × categoria 2 vazia: a Guardiã escolhe entre 0 e 2
        d = decidir_pergunta(1, 1, [2, 0], banco((1, 2)), prever_tabela({0: 0.9, 1: 0.7, 2: 0.66}))
        assert d.niveis_permitidos == (0, 1, 2)
        assert d.niveis_disponiveis == (0, 2)
        assert 1 not in d.previsoes
        assert (d.nivel, d.p_previsto, d.motivo) == (2, 0.66, MOTIVO_GUARDIA)
        assert d.celula_vazia and not d.categoria_substituida

    def test_pergunta_1_troca_de_categoria_e_mantem_o_nivel_inicial(self):
        d = decidir_pergunta(0, 2, [1, 3, 0], banco((2, 1)), prever_tabela({2: 0.5}))
        assert (d.nivel, d.categoria, d.categoria_sorteada) == (2, 3, 1)
        assert d.categoria_substituida

    def test_categoria_sem_nenhum_nivel_permitido_e_substituida(self):
        vazias = [(0, 0), (1, 0)]  # Explorador: faixa {0, 1}; categoria 0 sem nenhum dos dois
        d = decidir_pergunta(2, 0, [0, 3], banco(*vazias), prever_tabela({0: 0.8, 1: 0.6}))
        assert d.categoria == 3 and d.categoria_substituida
        assert d.nivel in niveis_permitidos(2, 0)

    def test_sem_modelo_usa_inicial_ou_o_disponivel_mais_proximo(self):
        assert decidir_pergunta(1, 1, [0], CHEIO, None).nivel == 1
        d = decidir_pergunta(1, 1, [0], banco((1, 0)), None)
        assert (d.nivel, d.motivo, d.p_previsto) == (0, MOTIVO_SEM_MODELO, C.INVALIDO)  # empate 0/2 -> mais baixo

    @pytest.mark.parametrize("ruim", [C.INVALIDO, math.nan, 1.3])
    def test_previsao_invalida(self, ruim):
        d = decidir_pergunta(1, 2, [0], banco((2, 0)), prever_tabela({1: ruim, 2: 0.7}))
        assert d.niveis_disponiveis == (1,)
        assert (d.nivel, d.motivo, d.p_previsto) == (1, MOTIVO_PREVISAO_INVALIDA, C.INVALIDO)

    def test_banco_incompleto(self):
        with pytest.raises(BancoIncompletoError):
            decidir_pergunta(0, 2, [0, 1], lambda n, c: n != 2, None)


def test_propriedades_em_bancos_aleatorios():
    """Em qualquer banco viável: nível sempre na faixa, categorias distintas, previsão do nível apresentado."""
    rng = np.random.default_rng(7)
    partidas = 0
    for _ in range(300):
        cheias = rng.random((3, 4)) > 0.3
        tem = lambda n, c: bool(cheias[n, c])  # noqa: E731
        if problemas_de_viabilidade(tem):
            continue
        tabela = rng.random(3)
        prev = lambda n, c: float(tabela[n])  # noqa: E731
        for ini, ordem_cat in itertools.product(range(3), itertools.permutations(range(4))):
            restantes, usadas = list(ordem_cat), []
            for k in range(3):
                d = decidir_pergunta(k, ini, restantes, tem, prev)
                assert d.nivel in niveis_permitidos(k, ini)
                assert cheias[d.nivel, d.categoria]
                assert d.p_previsto == d.previsoes[d.nivel] == tabela[d.nivel]
                assert set(d.previsoes) == set(d.niveis_disponiveis)
                if k == 0:
                    assert d.nivel == ini
                usadas.append(d.categoria)
                restantes.remove(d.categoria)
            assert len(set(usadas)) == 3
            partidas += 1
    assert partidas > 1000


class TestViabilidade:
    def test_banco_completo_e_viavel(self):
        assert problemas_de_viabilidade(CHEIO) == []

    def test_um_nivel_ausente_inviabiliza_quem_o_escolhe(self):
        problemas = problemas_de_viabilidade(lambda n, c: n != 2)
        assert len(problemas) == 1 and problemas[0].startswith("nível inicial 2")

    def test_substituicao_de_categoria_cobre_lacunas_parciais(self):
        # Mestre só em duas categorias: ainda viável, porque a categoria é substituída
        assert problemas_de_viabilidade(lambda n, c: n != 2 or c < 2) == []

    def test_lacuna_que_nao_da_para_contornar(self):
        # Mestre só em uma categoria: a pergunta 1 de quem escolhe Mestre funciona,
        # mas pode não haver nível {1, 2} nas perguntas seguintes se Desafiante também faltar
        problemas = problemas_de_viabilidade(lambda n, c: (n == 0) or (n == 2 and c == 0))
        assert any(p.startswith("nível inicial 2") for p in problemas)
