"""Banco da v0.8 (questoes/banco_v08.csv) e preservação do histórico da v0.7."""

import hashlib
from collections import Counter

from guardia.banco import APTA, LayoutTFT, analisar, carregar_banco, quebrar
from tests.conftest import RAIZ

V07 = RAIZ / "questoes" / "banco_v07.csv"
V08 = RAIZ / "questoes" / "banco_v08.csv"

# Conteúdo do banco_v07.csv aprovado na revisão de feat/banco-v07: não pode mudar.
SHA_BANCO_V07 = "6f6115c58954a568d5c6a7aeead62986bf2cdc91fbcf1b516e15f48d04216b09"

LAYOUT = LayoutTFT.paisagem(
    escala=2, escala_moldura=1, linhas_cabecalho=2, linhas_rodape=0, linhas_separadoras=0, margem_px=16
)


def _por_id():
    return {p.id: p for p in carregar_banco(V08)}


def test_banco_v07_preservado():
    assert hashlib.sha256(V07.read_bytes()).hexdigest() == SHA_BANCO_V07


def test_treze_perguntas_cobrindo_as_doze_celulas():
    perguntas = carregar_banco(V08)
    assert len(perguntas) == 13
    celulas = Counter((p.nivel, p.categoria) for p in perguntas)
    assert set(celulas) == {(n, c) for n in range(3) for c in range(4)}
    assert celulas[(2, 3)] == 2  # V07-MES-2-R1 e V07-MES-3


def test_origem_rastreavel():
    v07 = {p.id: p for p in carregar_banco(V07)}
    for p in carregar_banco(V08):
        if p.origem == "v0.7":
            assert v07[p.id] == p.__class__(**{**p.__dict__, "linha_csv": v07[p.id].linha_csv})
        elif p.origem == "v0.7-revisada":
            original = v07[p.id.removesuffix("-R1")]
            assert (p.nivel, p.categoria) == (original.nivel, original.categoria)
        else:
            assert p.origem == "nova-v0.8" and p.id.startswith("V08-")


def test_revisoes_pedidas():
    v = _por_id()
    exp3 = v["V07-EXP-3-R1"]
    assert exp3.alternativas == {"A": "Caza", "B": "Casa", "C": "Kasa", "D": "Casza"}
    assert "Cassa" not in exp3.alternativas.values() and exp3.correta == "B"
    assert v["V07-MES-1-R1"].dica == "Use potências de 2"
    assert v["V07-MES-1-R1"].alternativas == {"A": "8", "B": "9", "C": "10", "D": "12"}
    mes2 = v["V07-MES-2-R1"]
    assert mes2.alternativas[mes2.correta] == "Golpe digital"
    assert len(quebrar(mes2.enunciado, LAYOUT.colunas)) == 1  # enunciado em 1 linha libera a margem


def test_respostas_inequivocas_conferidas():
    v = _por_id()
    certa = lambda i: v[i].alternativas[v[i].correta]  # noqa: E731
    # Lógica: as sequências seguem a regra da dica
    assert int(certa("V08-EXP-LOG-1")) == 7 + 2
    assert int(certa("V08-MES-LOG-1")) == 3 + 5
    assert [int(a) for a in v["V08-EXP-LOG-1"].alternativas.values()].count(9) == 1
    # Português: só uma forma correta
    assert certa("V08-DES-POR-1") == "Flores"
    assert certa("V08-MES-POR-1") == "jogaram"
    assert certa("V07-EXP-3-R1") == "Casa"
    assert certa("V07-MES-1-R1") == str(int("1010", 2))


def test_todas_tem_quatro_alternativas_distintas_e_dica():
    for p in carregar_banco(V08):
        valores = list(p.alternativas.values())
        assert all(valores) and len({x.casefold() for x in valores}) == 4, p.id
        assert p.dica, p.id


def test_novas_perguntas_sem_caracteres_que_dependam_da_fonte():
    for p in carregar_banco(V08):
        if p.origem == "nova-v0.8":
            assert " ".join([p.enunciado, p.dica, *p.alternativas.values()]).isascii(), p.id


def test_todas_aptas_na_st7735_paisagem_com_margem():
    r = analisar(carregar_banco(V08), LAYOUT)
    assert [a.pergunta.id for a in r.avaliacoes if a.situacao != APTA] == []
    assert max(a.linhas_tela["pergunta"] for a in r.avaliacoes) <= LAYOUT.altura_px - 16
    assert r.adicionais_necessarias(1) == 0
    assert (r.adicionais_necessarias(3), r.adicionais_necessarias(5)) == (23, 47)
    assert r.problemas_viabilidade() == []
