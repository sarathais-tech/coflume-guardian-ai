"""Banco real da v0.7 (questoes/banco_v07.csv): integridade, classificação e cobertura."""

from collections import Counter

from guardia.banco import APTA, LayoutTFT, analisar, carregar_banco
from tests.conftest import RAIZ

BANCO = RAIZ / "questoes" / "banco_v07.csv"

# Classificação revisada em 01/11/2026 (docs/banco_questoes.md, seção 8)
CLASSIFICACAO = {
    "V07-EXP-1": (0, 0), "V07-EXP-2": (0, 3), "V07-EXP-3": (0, 1),
    "V07-DES-1": (1, 0), "V07-DES-2": (1, 3), "V07-DES-3": (1, 2),
    "V07-MES-1": (2, 0), "V07-MES-2": (2, 3), "V07-MES-3": (2, 3),
}

LAYOUT_PROPOSTO = LayoutTFT.paisagem(
    escala=2, escala_moldura=1, linhas_cabecalho=2, linhas_rodape=0, linhas_separadoras=0
)


def test_nove_perguntas_da_v07_tres_por_nivel():
    perguntas = carregar_banco(BANCO)
    assert len(perguntas) == 9
    assert {p.origem for p in perguntas} == {"v0.7"}
    assert Counter(p.nivel for p in perguntas) == {0: 3, 1: 3, 2: 3}


def test_classificacao_registrada():
    assert {p.id: (p.nivel, p.categoria) for p in carregar_banco(BANCO)} == CLASSIFICACAO


def test_texto_original_preservado_sem_acentos():
    """O texto da v0.7 é ASCII; a versão acentuada da v0.8 depende da solução de fonte."""
    for p in carregar_banco(BANCO):
        texto = " ".join([p.enunciado, p.dica, *p.alternativas.values()])
        assert texto.isascii(), p.id


def test_respostas_corretas_conferidas():
    corretas = {p.id: p.alternativas[p.correta] for p in carregar_banco(BANCO)}
    assert corretas == {
        "V07-EXP-1": "42", "V07-EXP-2": "Marte", "V07-EXP-3": "Casa",
        "V07-DES-1": "96", "V07-DES-2": "Golfinho", "V07-DES-3": "32",
        "V07-MES-1": "10", "V07-MES-2": "Golpe digital", "V07-MES-3": "G7!mP2#x",
    }
    assert 6 * 7 == 42 and 12 * 8 == 96 and int("1010", 2) == 10


def test_cobertura_e_adicionais():
    r = analisar(carregar_banco(BANCO))
    assert all(a.situacao == APTA for a in r.avaliacoes)
    assert len(r.aptas_por_celula) == 8  # 8 das 12 células
    assert (r.adicionais_necessarias(1), r.adicionais_necessarias(3), r.adicionais_necessarias(5)) == (4, 27, 51)
    assert r.problemas_viabilidade() == []


def test_todas_cabem_no_layout_proposto_para_a_st7735():
    r = analisar(carregar_banco(BANCO), LAYOUT_PROPOSTO)
    assert all(a.situacao == APTA for a in r.avaliacoes)
    maior = max(a.linhas_tela["pergunta"] for a in r.avaliacoes)
    assert maior == LAYOUT_PROPOSTO.altura_px  # V07-MES-2 usa a tela inteira: sem folga
