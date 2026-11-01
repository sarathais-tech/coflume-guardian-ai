"""Validador do banco de perguntas (fluxo-0.8, tela ST7735).

As perguntas abaixo são DADOS DE TESTE, não fazem parte de nenhum banco real.
"""

import csv

import pytest

from ferramentas import validar_banco
from guardia.banco import (
    AJUSTAR,
    APTA,
    COLUNAS_BANCO,
    INVALIDA,
    PENDENTE,
    LayoutTFT,
    analisar,
    carregar_banco,
    linhas_por_tela,
    quebrar,
)
from tests.conftest import RAIZ


def linha(id_, nivel="0", categoria="0", enunciado="Quanto e 2 + 3?", alts=("4", "5", "6", "7"),
          correta="B", dica="Conte nos dedos.", origem="teste", revisor="equipe"):
    return dict(zip(COLUNAS_BANCO, (id_, origem, nivel, categoria, enunciado, *alts, correta, dica, revisor)))


def gravar(tmp_path, linhas):
    caminho = tmp_path / "banco.csv"
    with open(caminho, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS_BANCO)
        w.writeheader()
        w.writerows(linhas)
    return caminho


def banco_completo(por_celula=1):
    return [linha(f"T-{n}-{c}-{k}", str(n), str(c), f"Pergunta de teste {n}{c}{k}?")
            for n in range(3) for c in range(4) for k in range(por_celula)]


class TestTela:
    def test_dimensoes_st7735(self):
        assert (LayoutTFT().colunas, LayoutTFT().linhas) == (21, 20)
        assert (LayoutTFT.paisagem().colunas, LayoutTFT.paisagem().linhas) == (26, 16)
        assert (LayoutTFT(escala=2).colunas, LayoutTFT(escala=2).linhas) == (10, 10)

    def test_quebra_respeita_largura_e_recuo(self):
        linhas = quebrar("A) uma alternativa bem comprida para testar a quebra", 21, recuo=3)
        assert len(linhas[0]) <= 21 and all(len(x) <= 18 for x in linhas[1:])
        assert " ".join(linhas).split() == "A) uma alternativa bem comprida para testar a quebra".split()

    def test_palavra_maior_que_a_linha_e_cortada(self):
        assert quebrar("abcdefghijkl", 5) == ["abcde", "fghij", "kl"]

    def test_contagem_de_linhas(self, tmp_path):
        p = carregar_banco(gravar(tmp_path, [linha("T1")]))[0]
        # cabeçalho + 1 enunciado + separador + 4 alternativas + rodapé
        assert linhas_por_tela(p, LayoutTFT())["pergunta"] == 8

    def test_texto_longo_pede_ajuste(self, tmp_path):
        longo = " ".join(["palavra"] * 60)
        r = analisar(carregar_banco(gravar(tmp_path, [linha("T1", enunciado=longo)])))
        a = r.avaliacoes[0]
        assert a.situacao == AJUSTAR and "tela de pergunta" in a.motivos[0]

    def test_mesmo_texto_cabe_em_paisagem_mas_nao_com_escala_2(self, tmp_path):
        texto = "Qual numero completa a sequencia 2, 4, 8, 16 e qual e a regra usada nela?"
        p = gravar(tmp_path, [linha("T1", enunciado=texto)])
        assert analisar(carregar_banco(p), LayoutTFT.paisagem()).avaliacoes[0].situacao == APTA
        assert analisar(carregar_banco(p), LayoutTFT(escala=2)).avaliacoes[0].situacao == AJUSTAR

    def test_altura_em_pixels_com_moldura_menor(self, tmp_path):
        p = carregar_banco(gravar(tmp_path, [linha("T1")]))[0]
        from guardia.banco import altura_por_tela
        uniforme = altura_por_tela(p, LayoutTFT())
        assert uniforme["pergunta"] == 8 * 8  # equivale às 8 linhas do tamanho 1
        misto = altura_por_tela(p, LayoutTFT(escala=2, escala_moldura=1, linhas_cabecalho=2))
        # cabeçalho (2) + rodapé (1) em tamanho 1; corpo em tamanho 2 com 10 colunas:
        # enunciado "Quanto e 2 + 3?" quebra em 2 linhas + separador (1) + 4 alternativas
        assert misto["pergunta"] == 3 * 8 + (2 + 1 + 4) * 16

    def test_cabecalho_com_temporizador_e_progresso(self, tmp_path):
        from guardia.banco import relatorio_markdown
        r = analisar(carregar_banco(gravar(tmp_path, [linha("T1")])), LayoutTFT(escala=2))
        assert "**não cabe** em 10 colunas" in relatorio_markdown(r, "x")
        r = analisar(carregar_banco(gravar(tmp_path, [linha("T1")])), LayoutTFT(escala=2, escala_moldura=1))
        assert "cabe." in relatorio_markdown(r, "x")

    def test_acentos_geram_aviso(self, tmp_path):
        r = analisar(carregar_banco(gravar(tmp_path, [linha("T1", enunciado="Qual é a estação?")])))
        a = r.avaliacoes[0]
        assert a.situacao == APTA
        assert any("ASCII" in av and "é" in av and "ç" in av and "ã" in av for av in a.avisos)


class TestSituacao:
    def test_sem_classificacao_fica_pendente(self, tmp_path):
        r = analisar(carregar_banco(gravar(tmp_path, [linha("T1", nivel="", categoria="")])))
        assert r.avaliacoes[0].situacao == PENDENTE

    def test_invalidas(self, tmp_path):
        r = analisar(carregar_banco(gravar(tmp_path, [
            linha("T1", alts=("4", "", "6", "7")),
            linha("T2", correta="E"),
            linha("T3", alts=("4", "4", "6", "7")),
            linha("T4"), linha("T4"),
        ])))
        assert [a.situacao for a in r.avaliacoes] == [INVALIDA] * 5
        assert r.duplicados == ["T4"]

    def test_sem_dica_pede_ajuste(self, tmp_path):
        r = analisar(carregar_banco(gravar(tmp_path, [linha("T1", dica="")])))
        assert r.avaliacoes[0].situacao == AJUSTAR

    def test_nivel_fora_da_faixa_e_rejeitado_na_leitura(self, tmp_path):
        with pytest.raises(ValueError, match="fora de 0..2"):
            carregar_banco(gravar(tmp_path, [linha("T1", nivel="3")]))

    def test_colunas_erradas(self, tmp_path):
        caminho = tmp_path / "x.csv"
        caminho.write_text("id,texto\n1,a\n", encoding="utf-8")
        with pytest.raises(ValueError, match="Colunas esperadas"):
            carregar_banco(caminho)


class TestCobertura:
    def test_banco_completo_com_tres_por_celula(self, tmp_path):
        r = analisar(carregar_banco(gravar(tmp_path, banco_completo(3))), meta_por_celula=3)
        assert r.adicionais_necessarias() == 0
        assert r.adicionais_necessarias(5) == 24
        assert r.problemas_viabilidade() == []

    def test_nove_perguntas_tres_por_nivel(self, tmp_path):
        """Situação parecida com a v0.7: 3 perguntas por nível, cobrindo 3 das 4 categorias."""
        linhas = [linha(f"T-{n}-{c}", str(n), str(c), f"Pergunta de teste {n}{c}?") for n in range(3) for c in range(3)]
        r = analisar(carregar_banco(gravar(tmp_path, linhas)))
        assert r.adicionais_necessarias(1) == 3
        assert r.adicionais_necessarias(3) == 27
        assert r.adicionais_necessarias(5) == 51
        assert r.problemas_viabilidade() == []  # a substituição de categoria cobre a 4ª categoria vazia

    def test_so_aptas_contam_para_cobertura(self, tmp_path):
        linhas = banco_completo(1)
        linhas[0]["dica"] = ""  # célula (0, 0) passa a precisar de ajuste
        r = analisar(carregar_banco(gravar(tmp_path, linhas)))
        assert r.aptas_por_celula[(0, 0)] == 0
        assert r.adicionais_necessarias(1) == 1


def test_modelo_versionado_tem_o_cabecalho_correto():
    cabecalho = (RAIZ / "questoes" / "banco_modelo.csv").read_text(encoding="utf-8").strip()
    assert tuple(cabecalho.split(",")) == COLUNAS_BANCO


def test_linha_de_comando(tmp_path, capsys):
    caminho = gravar(tmp_path, banco_completo(1))
    saida = tmp_path / "rel.md"
    assert validar_banco.main([str(caminho), "--relatorio", str(saida)]) == 0
    texto = saida.read_text(encoding="utf-8")
    assert "corpo tamanho 1 (21 colunas)" in texto and "Todas as partidas possíveis são viáveis." in texto
    ruim = gravar(tmp_path, [linha("T1", correta="Z")])
    assert validar_banco.main([str(ruim)]) == 1
