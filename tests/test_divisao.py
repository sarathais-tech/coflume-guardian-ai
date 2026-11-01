"""Divisão por participante: ausência de vazamento, proporções, determinismo e teste lacrado."""

import numpy as np
import pytest

from guardia import contrato as C
from guardia.dados import (
    CONJUNTOS,
    ConjuntoLacradoError,
    carregar,
    carregar_split,
    conferir_hash_dados,
    conjunto,
    criar_split,
    dividir_participantes,
    matriz,
    salvar_split,
    verificar_sem_vazamento,
)
from guardia.features import vetorizar, Entrada
from guardia.simulador import gerar_arquivo
from tests.conftest import RAIZ

SPLIT_VERSIONADO = RAIZ / "splits" / "split_v1.json"


@pytest.fixture(scope="module")
def dados(tmp_path_factory):
    caminho = tmp_path_factory.mktemp("d") / "sinteticos" / "s.csv"
    gerar_arquivo(caminho, 1000, 2026)
    df = carregar(caminho)
    split = criar_split(caminho, df)
    return caminho, df, split


def test_divisao_sem_vazamento(dados):
    """Exigido no protocolo, seção 3: nenhum participante em mais de um conjunto."""
    _, df, split = dados
    p = split["participantes"]
    for i, a in enumerate(CONJUNTOS):
        for b in CONJUNTOS[i + 1:]:
            assert not set(p[a]) & set(p[b]), f"{a} ∩ {b}"
    # todas as linhas de um participante caem no mesmo conjunto
    rotulo = {pid: nome for nome in CONJUNTOS for pid in p[nome]}
    por_linha = df["participante_id"].map(rotulo)
    assert por_linha.notna().all()
    assert (df.assign(c=por_linha).groupby("participante_id")["c"].nunique() == 1).all()


def test_particao_completa_e_proporcoes(dados):
    _, df, split = dados
    p = split["participantes"]
    todos = sorted(p["treino"] + p["validacao"] + p["teste"])
    assert todos == sorted(df["participante_id"].unique())
    assert (len(p["treino"]), len(p["validacao"]), len(p["teste"])) == (700, 150, 150)
    assert sum(split["n_linhas"].values()) == len(df)


def test_determinismo_e_dependencia_da_semente():
    ids = np.arange(500)
    assert dividir_participantes(ids, 2026) == dividir_participantes(ids, 2026)
    assert dividir_participantes(ids, 2026) != dividir_participantes(ids, 7)
    # a ordem e a repetição dos IDs nas linhas não alteram a divisão
    linhas = np.repeat(ids, 4)
    np.random.default_rng(0).shuffle(linhas)
    assert dividir_participantes(linhas, 2026) == dividir_participantes(ids, 2026)


def test_detector_de_vazamento():
    with pytest.raises(ValueError, match="Vazamento"):
        verificar_sem_vazamento({"treino": [1, 2, 3], "validacao": [3, 4], "teste": [5]})


def test_teste_lacrado(dados):
    _, df, split = dados
    with pytest.raises(ConjuntoLacradoError):
        conjunto(df, split, "teste")
    t = conjunto(df, split, "teste", abrir_teste=True)
    assert set(t["participante_id"]) == set(split["participantes"]["teste"])


def test_split_nao_se_aplica_a_outros_dados(dados, tmp_path):
    _, _, split = dados
    outro = tmp_path / "sinteticos" / "o.csv"
    gerar_arquivo(outro, 800, 2026)
    with pytest.raises(ValueError, match="não correspondem"):
        conjunto(carregar(outro), split, "treino")


def test_salvar_e_reler(dados, tmp_path):
    caminho, df, split = dados
    destino = tmp_path / "split.json"
    salvar_split(split, destino)
    assert carregar_split(destino) == split
    assert conferir_hash_dados(split, caminho)


def test_matriz_usa_so_as_features_do_contrato(dados):
    _, df, _ = dados
    X, y, g = matriz(df)
    assert X.shape == (len(df), C.N_ENTRADAS) and X.dtype == np.float32
    import dataclasses
    campos = [f.name for f in dataclasses.fields(Entrada)]
    for i in (0, 1, 7, len(df) - 1):
        r = df.iloc[i]
        e = Entrada(*[int(r[c]) if c in ("nivel_candidato", "nivel_inicial", "n_respondidas", "categoria",
                                         "resultado_ultima", "sequencia") else float(r[c]) for c in campos])
        assert np.array_equal(X[i], vetorizar(e))
    assert np.array_equal(y, df["acertou"].to_numpy(np.float32))
    assert np.array_equal(g, df["participante_id"].to_numpy())


# ---------------------------------------------------------------------------
# Arquivo versionado splits/split_v1.json
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not SPLIT_VERSIONADO.exists(), reason="splits/split_v1.json ainda não gerado")
class TestSplitVersionado:
    def test_estrutura_e_sem_vazamento(self):
        s = carregar_split(SPLIT_VERSIONADO)
        assert s["fonte"] == "SINTETICO"
        assert s["semente"] == 2026
        assert s["n_participantes"] == {"treino": 2100, "validacao": 450, "teste": 450}
        assert {k: len(v) for k, v in s["participantes"].items()} == s["n_participantes"]

    def test_reproduzivel_a_partir_dos_ids(self):
        """A divisão depende só dos IDs e da semente, não do conteúdo do CSV."""
        s = carregar_split(SPLIT_VERSIONADO)
        assert dividir_participantes(np.arange(3000), s["semente"]) == s["participantes"]
