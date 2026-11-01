"""Valida e classifica um banco de perguntas para o fluxo-0.8 (tela ST7735).

Uso:
    python -m ferramentas.validar_banco questoes/banco_v07.csv
    python -m ferramentas.validar_banco questoes/banco_v07.csv --orientacao paisagem --meta 5
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
    ap.add_argument("--escala", type=int, default=1, help="setTextSize do TFT (padrão 1)")
    ap.add_argument("--meta", type=int, default=3, help="perguntas aptas desejadas por célula (padrão 3)")
    ap.add_argument("--relatorio", type=Path, default=None)
    args = ap.parse_args(argv)

    layout = LayoutTFT.paisagem(escala=args.escala) if args.orientacao == "paisagem" else LayoutTFT(escala=args.escala)
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
