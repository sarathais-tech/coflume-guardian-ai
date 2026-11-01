"""Testes do simulador SINTÉTICO: formato, faixas, consistência e reprodutibilidade.

Os testes comuns rodam para sim-1.0 (histórico) e sim-1.1 (fluxo-0.8).
"""

import dataclasses
import json

import numpy as np
import pandas as pd
import pytest

from guardia import contrato as C
from guardia.dados import carregar
from guardia.features import Resposta, entrada_valida, montar_entrada
from guardia.simulador import (
    COLUNAS,
    PARAMETROS_POR_VERSAO,
    ParametrosSimulador,
    gerar_arquivo,
    para_csv,
    parametros_da_versao,
    simular,
)

N_TESTE = 1500
SEMENTE = 2026


@pytest.fixture(scope="module", params=sorted(PARAMETROS_POR_VERSAO))
def gerado(request, tmp_path_factory):
    pasta = tmp_path_factory.mktemp("dados") / "sinteticos"
    caminho = pasta / "sessoes.csv"
    manifesto = gerar_arquivo(caminho, N_TESTE, SEMENTE, parametros_da_versao(request.param))
    return caminho, manifesto, carregar(caminho)


def _versao(gerado) -> str:
    return gerado[1]["versao_simulador"]


# ---------------------------------------------------------------------------
# Formato e separação sintético × real
# ---------------------------------------------------------------------------

class TestFormato:
    def test_colunas_exatas(self, gerado):
        _, _, df = gerado
        assert tuple(df.columns) == COLUNAS

    def test_fonte_e_versao(self, gerado):
        _, _, df = gerado
        assert set(df["fonte"]) == {"SINTETICO"}
        assert set(df["versao_simulador"]) == {_versao(gerado)}
        assert gerado[1]["politica_coleta"] == "exploratoria-uniforme"

    def test_manifesto(self, gerado):
        caminho, manifesto, df = gerado
        disco = json.loads(caminho.with_name("sessoes.manifest.json").read_text(encoding="utf-8"))
        assert disco == manifesto
        assert manifesto["fonte"] == "SINTETICO"
        assert manifesto["semente"] == SEMENTE
        assert manifesto["n_linhas"] == len(df)
        assert manifesto["n_participantes"] == df["participante_id"].nunique() == N_TESTE
        assert "não comprovam eficácia educacional" in manifesto["aviso"]

    def test_sem_dados_pessoais(self):
        """Nenhuma coluna identifica pessoas; mudanças aqui exigem revisão."""
        proibidas = {"nome", "idade", "escola", "foto", "email", "cpf", "data_nascimento", "turma"}
        assert not proibidas & set(COLUNAS)

    def test_ids_sao_indices_sequenciais(self, gerado):
        _, _, df = gerado
        assert sorted(df["participante_id"].unique()) == list(range(N_TESTE))

    def test_recusa_gravar_sintetico_fora_da_pasta(self, tmp_path):
        with pytest.raises(ValueError, match="sinteticos"):
            gerar_arquivo(tmp_path / "reais" / "x.csv", 5, 1)

    def test_carregar_recusa_pasta_errada(self, gerado, tmp_path):
        caminho, _, _ = gerado
        destino = tmp_path / "reais" / "x.csv"
        destino.parent.mkdir()
        destino.write_bytes(caminho.read_bytes())
        with pytest.raises(ValueError, match="sinteticos"):
            carregar(destino)

    def test_carregar_recusa_mistura_de_fontes(self, gerado, tmp_path):
        caminho, _, df = gerado
        misto = df.copy()
        misto.loc[misto.index[:5], "fonte"] = "REAL"
        destino = tmp_path / "sinteticos" / "misto.csv"
        destino.parent.mkdir()
        misto.to_csv(destino, index=False)
        with pytest.raises(ValueError, match="mistura fontes"):
            carregar(destino)


# ---------------------------------------------------------------------------
# Faixas e estrutura das sessões
# ---------------------------------------------------------------------------

class TestFaixas:
    def test_todas_as_entradas_validas_no_contrato(self, gerado):
        _, _, df = gerado
        from guardia.features import Entrada

        campos = [f.name for f in dataclasses.fields(Entrada)]
        for linha in df[campos].itertuples(index=False):
            e = Entrada(*[int(v) if isinstance(v, (np.integer, int)) else float(v) for v in linha])
            assert entrada_valida(e)

    def test_oraculo_e_tempos(self, gerado):
        _, _, df = gerado
        assert df["p_real"].between(0, 1).all()
        assert (df["resp_tempo_gasto_s"] <= df["resp_tempo_limite_s"]).all()
        esg = df[df["resp_esgotou"] == 1]
        assert len(esg) > 0
        assert (esg["acertou"] == 0).all()
        assert (esg["resp_tempo_gasto_s"] == esg["resp_tempo_limite_s"]).all()

    def test_cobertura_de_niveis_categorias_e_respostas(self, gerado):
        _, _, df = gerado
        assert set(df["nivel_candidato"]) == {0, 1, 2}
        assert set(df["categoria"]) == {0, 1, 2, 3}
        assert set(df["nivel_inicial"]) == {0, 1, 2}
        assert set(df["acertou"]) == {0, 1}
        assert set(df["resp_usou_dica"]) == {0, 1}
        combos = df.groupby(["nivel_inicial", "nivel_candidato"]).size()
        if _versao(gerado) == "sim-1.0":
            assert set(df["tipo"]) == {"principal", "reforco"}
            assert len(combos) == 9
        else:
            # fluxo-0.8: só as combinações da faixa ±1 (Explorador nunca recebe Mestre)
            assert set(df["tipo"]) == {"principal"}
            assert set(combos.index) == {(i, n) for i in range(3) for n in range(3) if abs(i - n) <= 1}
        assert combos.min() >= 30


class TestEstruturaDaSessao:
    def test_dados_incluem_partida_a_frio(self, gerado):
        """Exigido em docs/features.md, seção 4."""
        _, _, df = gerado
        primeira = df[df["ordem"] == 0]
        assert primeira["participante_id"].nunique() == N_TESTE
        assert (primeira["n_respondidas"] == 0).all()
        assert (primeira["resultado_ultima"] == 0).all()
        assert (primeira["sequencia"] == 0).all()
        assert (primeira["taxa_acerto_sessao"] == C.FRIO_TAXA).all()
        assert (primeira["tempo_medio_norm"] == C.FRIO_TEMPO).all()
        assert (primeira["dicas_por_questao"] == C.FRIO_DICAS).all()

    def test_primeira_questao_nunca_acima_do_nivel_inicial(self, gerado):
        _, _, df = gerado
        p = df[df["ordem"] == 0]
        assert (p["nivel_candidato"] <= p["nivel_inicial"]).all()
        assert (p["nivel_candidato"] >= p["nivel_inicial"] - 1).all()

    def test_principais_em_categorias_distintas(self, gerado):
        _, _, df = gerado
        principais = df[df["tipo"] == "principal"]
        g = principais.groupby("participante_id")["categoria"]
        assert (g.size() == 3).all()
        assert (g.nunique() == 3).all()

    def test_reforco_segue_erro_na_mesma_categoria(self, gerado):
        _, _, df = gerado
        if _versao(gerado) != "sim-1.0":
            assert not (df["tipo"] == "reforco").any()
            return
        anterior = df.groupby("participante_id").shift(1)
        ref = df["tipo"] == "reforco"
        assert (anterior.loc[ref, "tipo"] == "principal").all()
        assert (anterior.loc[ref, "acertou"] == 0).all()
        assert (anterior.loc[ref, "categoria"] == df.loc[ref, "categoria"]).all()
        diff = anterior.loc[ref, "nivel_candidato"] - df.loc[ref, "nivel_candidato"]
        assert diff.isin([0, 1]).all()
        # todo erro em questão principal gera exatamente um reforço
        prox = df.groupby("participante_id").shift(-1)
        erro_principal = (df["tipo"] == "principal") & (df["acertou"] == 0)
        assert (prox.loc[erro_principal, "tipo"] == "reforco").all()

    def test_tamanho_da_sessao(self, gerado):
        _, _, df = gerado
        tam = df.groupby("participante_id").size()
        if _versao(gerado) == "sim-1.0":
            assert tam.min() >= 3 and tam.max() <= 6
        else:
            assert (tam == 3).all()


# ---------------------------------------------------------------------------
# Consistência das features com o histórico registrado
# ---------------------------------------------------------------------------

def test_features_recalculadas_a_partir_do_historico_sao_identicas(gerado):
    """As features de cada linha devem ser exatamente as do runtime (float32 bit a bit)."""
    _, _, df = gerado
    cols = list(C.FEATURES_NUMERICAS) + ["categoria"]
    divergencias = 0
    for _, sessao in df.groupby("participante_id", sort=False):
        hist: list[Resposta] = []
        for r in sessao.itertuples(index=False):
            e = montar_entrada(hist, int(r.nivel_inicial), int(r.categoria), int(r.nivel_candidato))
            esperado = [getattr(e, c) for c in cols]
            obtido = [getattr(r, c) for c in cols]
            if any(np.float32(a) != np.float32(b) for a, b in zip(esperado, obtido)):
                divergencias += 1
            hist.append(Resposta(int(r.categoria), int(r.nivel_candidato), bool(r.acertou),
                                 float(r.resp_tempo_gasto_s), float(r.resp_tempo_limite_s), bool(r.resp_usou_dica)))
    assert divergencias == 0


def test_rotulo_nao_vaza_para_as_features(gerado):
    """As features de uma linha não podem depender da resposta dessa mesma linha."""
    _, _, df = gerado
    pid = int(df.loc[df["ordem"] == 2, "participante_id"].iloc[0])
    sessao = df[df["participante_id"] == pid].reset_index(drop=True)
    hist = [
        Resposta(int(r.categoria), int(r.nivel_candidato), bool(r.acertou),
                 float(r.resp_tempo_gasto_s), float(r.resp_tempo_limite_s), bool(r.resp_usou_dica))
        for r in sessao.iloc[:2].itertuples(index=False)
    ]
    r2 = sessao.iloc[2]
    e = montar_entrada(hist, int(r2.nivel_inicial), int(r2.categoria), int(r2.nivel_candidato))
    assert e.n_respondidas == 2  # usa só as 2 respostas anteriores


# ---------------------------------------------------------------------------
# O oráculo p_real é de fato a probabilidade de acerto
# ---------------------------------------------------------------------------

def test_p_real_calibrado_com_acerto_observado(gerado):
    _, _, df = gerado
    assert abs(df["acertou"].mean() - df["p_real"].mean()) < 0.02
    faixas = pd.cut(df["p_real"], np.linspace(0, 1, 6), include_lowest=True)
    for _, g in df.groupby(faixas, observed=True):
        if len(g) >= 300:
            assert abs(g["acertou"].mean() - g["p_real"].mean()) < 0.05


def test_dados_tem_sinal_aprendivel(gerado):
    """Sanidade: o comportamento observado carrega informação sobre o acerto.

    Não é avaliação de modelo; só garante que o simulador não gera ruído puro.
    """
    _, _, df = gerado
    seg = df[df["ordem"] >= 1]
    alto = seg[seg["taxa_acerto_sessao"] >= 0.75]["acertou"].mean()
    baixo = seg[seg["taxa_acerto_sessao"] <= 0.25]["acertou"].mean()
    assert alto > baixo + 0.05
    nivel = df.groupby("nivel_candidato")["acertou"].mean()
    assert nivel[0] > nivel[1] > nivel[2]


# ---------------------------------------------------------------------------
# Reprodutibilidade
# ---------------------------------------------------------------------------

class TestReprodutibilidade:
    def test_mesma_semente_gera_bytes_identicos(self, tmp_path):
        a = gerar_arquivo(tmp_path / "a" / "sinteticos" / "s.csv", 200, SEMENTE)
        b = gerar_arquivo(tmp_path / "b" / "sinteticos" / "s.csv", 200, SEMENTE)
        assert a["sha256"] == b["sha256"]
        assert (tmp_path / "a" / "sinteticos" / "s.csv").read_bytes() == (tmp_path / "b" / "sinteticos" / "s.csv").read_bytes()

    def test_semente_diferente_gera_dados_diferentes(self):
        assert para_csv(simular(200, SEMENTE)) != para_csv(simular(200, SEMENTE + 1))

    def test_participante_independe_do_total_gerado(self):
        """O participante i é o mesmo gerando 50 ou 300 participantes."""
        pequeno = simular(50, SEMENTE)
        grande = [r for r in simular(300, SEMENTE) if r["participante_id"] < 50]
        assert pequeno == grande

    def test_parametros_ficam_no_manifesto(self, gerado):
        _, manifesto, _ = gerado
        esperado = dataclasses.asdict(parametros_da_versao(manifesto["versao_simulador"]))
        assert manifesto["parametros"] == json.loads(json.dumps(esperado))

    def test_csv_le_de_volta_os_mesmos_float32(self, gerado):
        caminho, _, df = gerado
        linhas = simular(N_TESTE, SEMENTE, parametros_da_versao(_versao(gerado)))
        for col in ("taxa_acerto_sessao", "tempo_medio_norm"):
            original = np.array([r[col] for r in linhas], dtype=np.float32)
            assert np.array_equal(original, df[col].to_numpy(dtype=np.float32))


def test_parametros_invalidos():
    with pytest.raises(ValueError):
        ParametrosSimulador(prob_nivel_inicial=(0.5, 0.5, 0.5))
    with pytest.raises(ValueError):
        ParametrosSimulador(n_principais=5)
    with pytest.raises(ValueError):
        simular(0)
