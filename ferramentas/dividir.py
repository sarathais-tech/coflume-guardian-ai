"""Divide os participantes em treino/validação/teste sem vazamento (protocolo, seção 3).

Uso:
    python -m ferramentas.dividir                                   # sessoes_v2 -> splits/split_v2.json
    python -m ferramentas.dividir --dados dados/sinteticos/sessoes_v1.csv --saida splits/split_v1.json

O arquivo de divisão é versionado no Git e usado por TODOS os modelos.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from guardia.dados import (
    CONJUNTOS,
    SEMENTE_DIVISAO,
    carregar,
    carregar_split,
    criar_split,
    salvar_split,
    verificar_sem_vazamento,
)

RAIZ = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dados", type=Path, default=RAIZ / "dados" / "sinteticos" / "sessoes_v2.csv")
    ap.add_argument("--saida", type=Path, default=RAIZ / "splits" / "split_v2.json")
    ap.add_argument("--semente", type=int, default=SEMENTE_DIVISAO)
    args = ap.parse_args(argv)

    df = carregar(args.dados)
    split = criar_split(args.dados, df, args.semente, versao=args.saida.stem)
    salvar_split(split, args.saida)
    relido = carregar_split(args.saida)
    verificar_sem_vazamento(relido["participantes"])

    print(f"[{split['fonte']}] divisão por participante, semente {split['semente']}")
    for nome in CONJUNTOS:
        print(f"  {nome:<10} {split['n_participantes'][nome]:>5} participantes  {split['n_linhas'][nome]:>6} linhas")
    print("  Interseções entre conjuntos: nenhuma")
    print(f"Arquivo: {args.saida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
