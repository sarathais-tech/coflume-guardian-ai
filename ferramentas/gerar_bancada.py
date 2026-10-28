"""Gera os cabeçalhos do teste de bancada no ESP32-S3.

Uso:
    python -m ferramentas.gerar_bancada --semente 2026
    python -m ferramentas.gerar_bancada --ocultas 32 16

Usa pesos ALEATÓRIOS: o objetivo é medir viabilidade embarcada (memória,
latência, equivalência numérica), não qualidade de previsão. Um modelo
treinado com a mesma arquitetura tem exatamente o mesmo custo.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from guardia.exportar.mlp_cpp import exportar
from guardia.inferencia_ref import ModeloMLP

RAIZ = Path(__file__).resolve().parents[1]
PADRAO_SAIDA = RAIZ / "embarcado" / "bancada_ia"
RUNTIME = RAIZ / "embarcado" / "runtime" / "guardia_runtime.h"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--semente", type=int, default=2026)
    ap.add_argument("--ocultas", type=int, nargs="+", default=[16, 8])
    ap.add_argument("--vetores", type=int, default=200)
    ap.add_argument("--saida", type=Path, default=PADRAO_SAIDA)
    args = ap.parse_args(argv)

    modelo = ModeloMLP.aleatorio(args.semente, tuple(args.ocultas))
    info = exportar(modelo, args.saida, n_vetores=args.vetores)
    shutil.copy(RUNTIME, args.saida / "guardia_runtime.h")
    (args.saida / "MODELO.json").unlink()  # metadados de bancada não são release

    n_frio = sum(r["n_hist"] == 0 for r in info["registros"])
    print(f"Modelo de bancada: {info['modelo_id']}  (pesos ALEATÓRIOS)")
    print(f"Parâmetros: {modelo.n_parametros}  ·  vetores: {args.vetores} ({n_frio} de partida a frio)")
    print(f"Arquivos em: {args.saida}")
    print("Próximo passo: abra embarcado/bancada_ia/bancada_ia.ino no Arduino IDE e grave na placa.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
