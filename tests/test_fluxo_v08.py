"""fluxo-0.8: política de referência do cofre, sim-1.1 e preservação do histórico (sim-1.0)."""

import hashlib
import math
import re

import numpy as np
import pytest

from guardia import contrato as C
from guardia import politica
from guardia.simulador import para_csv, parametros_da_versao, simular
from tests.conftest import RAIZ

SEMENTE = 2026


@pytest.fixture(scope="module")
def df_v11():
    import pandas as pd

    return pd.DataFrame(simular(2000, SEMENTE, parametros_da_versao("sim-1.1")))


# ---------------------------------------------------------------------------
# Política de referência (cofre) — lógica tradicional, não ML
# ---------------------------------------------------------------------------

class TestNiveisPermitidos:
    @pytest.mark.parametrize("ini", range(3))
    def test_primeira_pergunta_no_nivel_escolhido(self, ini):
        assert politica.niveis_permitidos(0, ini) == [ini]

    @pytest.mark.parametrize("ordem", [1, 2])
    def test_faixa_mais_ou_menos_um(self, ordem):
        assert politica.niveis_permitidos(ordem, 0) == [0, 1]
        assert politica.niveis_permitidos(ordem, 1) == [0, 1, 2]
        assert politica.niveis_permitidos(ordem, 2) == [1, 2]

    def test_entradas_invalidas(self):
        with pytest.raises(ValueError):
            politica.niveis_permitidos(3, 1)  # o fluxo-0.8 tem só 3 perguntas
        with pytest.raises(ValueError):
            politica.niveis_permitidos(1, 3)


class TestEscolherNivel:
    def test_mais_proximo_de_70(self):
        assert politica.escolher_nivel({0: 0.90, 1: 0.72, 2: 0.40}, 1) == 1
        assert politica.escolher_nivel({0: 0.95, 1: 0.85, 2: 0.66}, 1) == 2
        assert politica.escolher_nivel({1: 0.30, 2: 0.10}, 2) == 1

    def test_empate_prefere_nivel_inicial(self):
        assert politica.escolher_nivel({0: 0.80, 1: 0.60}, 1) == 1
        assert politica.escolher_nivel({0: 0.80, 1: 0.60}, 0) == 0

    def test_empate_sem_nivel_inicial_prefere_o_mais_baixo(self):
        assert politica.escolher_nivel({0: 0.80, 1: 0.10, 2: 0.60}, 1) == 0

    @pytest.mark.parametrize("ruim", [C.INVALIDO, math.nan, 1.5, -0.2])
    def test_previsao_invalida_volta_ao_nivel_inicial(self, ruim):
        assert politica.escolher_nivel({0: 0.70, 1: ruim, 2: 0.69}, 2) == 2

    def test_sem_previsoes_volta_ao_nivel_inicial(self):
        assert politica.escolher_nivel({}, 1) == 1


class TestDesbloqueioReferencia:
    @pytest.mark.parametrize(
        "acertos, abre",
        [([1, 1, 1], True), ([1, 1, 0], True), ([0, 1, 1], True), ([1, 0, 1], True),
         ([1, 0, 0], False), ([0, 0, 1], False), ([0, 0, 0], False)],
    )
    def test_dois_em_tres(self, acertos, abre):
        assert politica.desbloqueio_referencia([bool(a) for a in acertos]) is abre

    def test_exige_tres_perguntas(self):
        with pytest.raises(ValueError):
            politica.desbloqueio_referencia([True, True])


# ---------------------------------------------------------------------------
# sim-1.1 segue o fluxo-0.8
# ---------------------------------------------------------------------------

def test_parametros_sim11():
    p = parametros_da_versao("sim-1.1")
    assert p.n_principais == 3
    assert p.reforco_apos_erro is False
    assert p.ganho_feedback_apos_erro == 0.0
    assert p.primeira_no_nivel_inicial is True
    assert p.faixa_nivel == politica.FAIXA_NIVEL
    assert p.tempo_limite_s == 30.0
    assert p.efeito_dica > 0  # dicas mantidas


def test_tres_perguntas_principais_em_categorias_distintas(df_v11):
    g = df_v11.groupby("participante_id")
    assert (g.size() == politica.N_PERGUNTAS).all()
    assert (g["categoria"].nunique() == 3).all()
    assert set(df_v11["tipo"]) == {"principal"}


def test_niveis_gerados_estao_nos_permitidos_pela_politica(df_v11):
    """A coleta usa exatamente o mesmo suporte que o cofre pode consultar."""
    gerados = set()
    for r in df_v11.itertuples(index=False):
        assert r.nivel_candidato in politica.niveis_permitidos(r.ordem, r.nivel_inicial)
        gerados.add((r.ordem, r.nivel_inicial, r.nivel_candidato))
    permitidos = {(o, i, n) for o in range(3) for i in range(3) for n in politica.niveis_permitidos(o, i)}
    assert gerados == permitidos


def test_coleta_e_exploratoria_e_nao_adaptativa(df_v11):
    """Na coleta o nível é sorteado: cada nível permitido aparece em proporção semelhante."""
    seg = df_v11[(df_v11["ordem"] > 0) & (df_v11["nivel_inicial"] == 1)]
    freq = seg["nivel_candidato"].value_counts(normalize=True)
    assert set(freq.index) == {0, 1, 2}
    assert (abs(freq - 1 / 3) < 0.05).all()


def test_dicas_presentes_e_registradas(df_v11):
    assert set(df_v11["resp_usou_dica"]) == {0, 1}
    assert (df_v11.loc[df_v11["ordem"] > 0, "dicas_por_questao"] > 0).any()


def test_taxa_categoria_igual_a_sessao_quando_categorias_nao_se_repetem(df_v11):
    """montar_entrada usa a taxa da sessão para categoria sem respostas anteriores.

    Com 3 categorias distintas (fluxo-0.8), as duas features são sempre iguais.
    """
    assert (df_v11["taxa_acerto_categoria"] == df_v11["taxa_acerto_sessao"]).all()


def test_taxa_categoria_difere_quando_categoria_se_repete():
    """Contraprova: no sim-1.0 o reforço repete a categoria e a igualdade deixa de valer."""
    import pandas as pd

    df = pd.DataFrame(simular(500, SEMENTE, parametros_da_versao("sim-1.0")))
    repetida = df.groupby("participante_id")["categoria"].transform(lambda s: s.duplicated())
    assert (df.loc[~repetida, "taxa_acerto_categoria"] == df.loc[~repetida, "taxa_acerto_sessao"]).all()
    assert (df.loc[repetida, "taxa_acerto_categoria"] != df.loc[repetida, "taxa_acerto_sessao"]).any()


def test_features_continuam_no_contrato_1_0_0(df_v11):
    assert C.CONTRATO_VERSAO == "1.0.0"
    assert df_v11["n_respondidas"].between(0, 2).all()
    assert df_v11["sequencia"].between(-2, 2).all()


# ---------------------------------------------------------------------------
# Histórico preservado: os resumos versionados continuam reproduzíveis
# ---------------------------------------------------------------------------

def _resumo(nome):
    texto = (RAIZ / "resultados" / "sinteticos" / f"{nome}_resumo.md").read_text(encoding="utf-8")
    sha = re.search(r"SHA-256 do CSV:\*\* `([0-9a-f]{64})`", texto).group(1)
    numpy_v = re.search(r"numpy ([\w.]+)", texto).group(1)
    n = int(re.search(r"\| Participantes \| (\d+) \|", texto).group(1))
    return sha, numpy_v, n


@pytest.mark.parametrize("versao, nome", [("sim-1.0", "sessoes_v1"), ("sim-1.1", "sessoes_v2")])
def test_conjunto_versionado_e_reproduzivel(versao, nome):
    """Regenera o conjunto e compara com o SHA-256 registrado no resumo versionado.

    O NumPy não garante a mesma sequência aleatória entre versões; por isso a
    comparação só é exigida quando a versão do numpy é a mesma do registro.
    """
    sha, numpy_v, n = _resumo(nome)
    if np.__version__ != numpy_v:
        pytest.skip(f"resumo gerado com numpy {numpy_v}; ambiente atual tem {np.__version__}")
    atual = hashlib.sha256(para_csv(simular(n, SEMENTE, parametros_da_versao(versao)))).hexdigest()
    assert atual == sha
