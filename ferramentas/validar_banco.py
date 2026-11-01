"""Valida e classifica um banco de perguntas para o fluxo-0.8 (tela ST7735).

Uso:
    python -m ferramentas.validar_banco questoes/banco_v07.csv
    python -m ferramentas.validar_banco questoes/banco_v07.csv --orientacao paisagem --meta 5
    python -m ferramentas.validar_banco questoes/banco_v07.csv --escala 2 --escala-moldura 1 --linhas-cabecalho 2
    python -m ferramentas.validar_banco questoes/banco_v07.csv --relatorio resultados/banco/banco_v07.md

Formato do CSV: questoes/banco_modelo.csv. Saída 0 se nenhuma pergunta for inválida.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from guardia.banco import INVALIDA, LayoutTFT, analisar, carregar_banco, relatorio_markdown


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("banco", type=Path)
    ap.add_argument("--orientacao", choices=("retrato", "paisagem"), default="retrato")
    ap.add_argument("--escala", type=int, default=1, help="setTextSize do corpo do texto (padrão 1)")
    ap.add_argument("--escala-moldura", type=int, default=None,
                    help="setTextSize do cabeçalho e do rodapé (padrão: igual a --escala)")
    ap.add_argument("--linhas-cabecalho", type=int, default=1,
                    help="linhas do cabeçalho: nível/progresso e, se houver, barra do temporizador")
    ap.add_argument("--sem-separador", action="store_true", help="sem linha em branco antes das alternativas")
    ap.add_argument("--linhas-rodape", type=int, default=1, help="linhas do rodapé (0 se a dica for indicada no cabeçalho)")
    ap.add_argument("--meta", type=int, default=3, help="perguntas aptas desejadas por célula (padrão 3)")
    ap.add_argument("--relatorio", type=Path, default=None)
    args = ap.parse_args(argv)

    kw = dict(escala=args.escala, escala_moldura=args.escala_moldura, linhas_cabecalho=args.linhas_cabecalho,
              linhas_rodape=args.linhas_rodape, linhas_separadoras=0 if args.sem_separador else 1)
    layout = LayoutTFT.paisagem(**kw) if args.orientacao == "paisagem" else LayoutTFT(**kw)
    r = analisar(carregar_banco(args.banco), layout, args.meta)
    md = relatorio_markdown(r, f"Classificação do banco `{args.banco.name}`")
    print(md)
    if args.relatorio:
        args.relatorio.parent.mkdir(parents=True, exist_ok=True)
        args.relatorio.write_text(md, encoding="utf-8")
        print(f"Relatório: {args.relatorio}")
    return 1 if any(a.situacao == INVALIDA for a in r.avaliacoes) else 0


if __name__ == "__main__":
    raise SystemExit(main())
