"""Treina os modelos da Guardiã IA e avalia em VALIDAÇÃO (o teste continua lacrado).

Uso:
    python -m ferramentas.treinar                         # todos os modelos (MLP exige TensorFlow)
    python -m ferramentas.treinar --modelos baseline arvore logistica
    python -m ferramentas.treinar --anotacoes             # no CI: publica o resultado como anotações

Saídas (padrão em resultados/sinteticos/treino_v2/):
    validacao.json   resultados completos, sementes, versões e configurações
Com --salvar-modelos <pasta>: árvore e logística (joblib) e MLP candidata (.npz, formato do contrato).
O modelo NÃO é exportado para o ESP32 nesta etapa.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import gzip
import hashlib
import json
import os
import subprocess
from pathlib import Path

from guardia.treino import executar, tensorflow_disponivel

RAIZ = Path(__file__).resolve().parents[1]
# O GitHub corta cada anotação em 4.096 caracteres e aceita no máximo 10 avisos
# (notice) por etapa: o resumo ocupa 1, sobram 9 partes de até 3.900 caracteres.
TAMANHO_PARTE = 3_900
MAX_PARTES = 9
TITULO_PARTE = "guardia-resultado"


def _commit() -> str | None:
    if os.environ.get("GITHUB_SHA"):
        return os.environ["GITHUB_SHA"]
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=RAIZ, capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def serializar(res: dict) -> bytes:
    return (json.dumps(res, ensure_ascii=False, indent=1, sort_keys=True) + "\n").encode("utf-8")


def anotacoes(conteudo: bytes, resumo: str) -> list[str]:
    """Linhas ``::notice`` com o JSON compactado (gzip + base64) em partes, mais um resumo legível."""
    sha = hashlib.sha256(conteudo).hexdigest()
    codificado = base64.b64encode(gzip.compress(conteudo, mtime=0)).decode("ascii")
    partes = [codificado[i : i + TAMANHO_PARTE] for i in range(0, len(codificado), TAMANHO_PARTE)]
    linhas = [f"::notice title=guardia-resumo::{resumo}"]
    if len(partes) > MAX_PARTES:
        return linhas + [f"::warning title=guardia-resultado-grande::{len(partes)} partes excedem o limite de "
                         f"{MAX_PARTES}; use o artefato da execução (sha256={sha})"]
    linhas += [f"::notice title={TITULO_PARTE} {i}/{len(partes)} sha256={sha}::{p}" for i, p in enumerate(partes, 1)]
    return linhas


def resumo_curto(res: dict) -> str:
    itens = []
    for nome, m in res["modelos"].items():
        v = m["validacao"]["metricas"]
        itens.append(f"{nome}: logloss={v['log_loss']:.4f} brier={v['brier']:.4f} auc={v['roc_auc']:.4f} ece={v['ece']:.4f}")
    return " | ".join(itens) + f" | dados_identicos={res['dados']['identico_ao_registrado']}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dados", type=Path, default=RAIZ / "dados" / "sinteticos" / "sessoes_v2.csv")
    ap.add_argument("--split", type=Path, default=RAIZ / "splits" / "split_v2.json")
    ap.add_argument("--saida", type=Path, default=RAIZ / "resultados" / "sinteticos" / "treino_v2")
    ap.add_argument("--modelos", nargs="+", default=["baseline", "arvore", "logistica", "mlp"],
                    choices=["baseline", "arvore", "logistica", "mlp"])
    ap.add_argument("--salvar-modelos", type=Path, default=None)
    ap.add_argument("--anotacoes", action="store_true")
    args = ap.parse_args(argv)

    if "mlp" in args.modelos and not tensorflow_disponivel():
        ap.error("A MLP exige TensorFlow (pip install -r requirements-treino.txt) ou use --modelos sem 'mlp'.")

    res, objetos = executar(args.dados, args.split, tuple(args.modelos))
    res["execucao"] = {
        "commit": _commit(),
        "ci_run_id": os.environ.get("GITHUB_RUN_ID"),
        "inicio_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "modelos_pedidos": args.modelos,
    }
    conteudo = serializar(res)
    args.saida.mkdir(parents=True, exist_ok=True)
    (args.saida / "validacao.json").write_bytes(conteudo)
    print(f"[SINTÉTICO] {resumo_curto(res)}")
    print(f"Resultados: {args.saida / 'validacao.json'} (sha256 {hashlib.sha256(conteudo).hexdigest()[:16]}…)")

    if args.salvar_modelos:
        import joblib

        args.salvar_modelos.mkdir(parents=True, exist_ok=True)
        for nome in ("arvore", "logistica"):
            if nome in objetos:
                joblib.dump(objetos[nome], args.salvar_modelos / f"{nome}.joblib")
        if "mlp" in objetos:
            m = objetos["mlp"]
            import numpy as np

            np.savez(args.salvar_modelos / "mlp_candidata.npz", media=m.media, desvio=m.desvio,
                     **{f"W{i}": W for i, (W, _) in enumerate(m.camadas)},
                     **{f"b{i}": b for i, (_, b) in enumerate(m.camadas)})

    if args.anotacoes:
        for linha in anotacoes(conteudo, resumo_curto(res)):
            print(linha)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
