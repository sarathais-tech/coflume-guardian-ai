"""Recupera o resultado do treino oficial publicado pelo CI como anotações.

Uso:
    python -m ferramentas.ler_resultado_ci --run <id> --saida resultados/sinteticos/treino_v2/validacao.json

Requer o GitHub CLI (``gh``) autenticado. O JSON é remontado das partes,
descompactado e conferido pelo SHA-256 publicado pelo próprio CI.
"""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import re
import subprocess
from pathlib import Path

from ferramentas.treinar import TITULO_PARTE

PADRAO = re.compile(rf"^{TITULO_PARTE} (\d+)/(\d+) sha256=([0-9a-f]{{64}})$")


def reconstruir(anotacoes: list[dict]) -> bytes:
    """Remonta o conteúdo a partir de anotações {'title', 'message'} e confere o SHA-256."""
    partes, total, sha = {}, None, None
    for a in anotacoes:
        m = PADRAO.match((a.get("title") or "").strip())
        if not m:
            continue
        i, n, s = int(m.group(1)), int(m.group(2)), m.group(3)
        if (total, sha) not in ((None, None), (n, s)):
            raise ValueError("Anotações de execuções diferentes misturadas.")
        total, sha = n, s
        partes[i] = a["message"].strip()
    if not partes:
        raise ValueError("Nenhuma parte do resultado encontrada nas anotações.")
    faltando = sorted(set(range(1, total + 1)) - set(partes))
    if faltando:
        raise ValueError(f"Partes ausentes: {faltando}")
    conteudo = gzip.decompress(base64.b64decode("".join(partes[i] for i in range(1, total + 1))))
    if hashlib.sha256(conteudo).hexdigest() != sha:
        raise ValueError("SHA-256 do conteúdo não confere com o publicado pelo CI.")
    return conteudo


def _gh(caminho: str):
    saida = subprocess.run(["gh", "api", "--paginate", caminho], capture_output=True, text=True, check=True).stdout
    return json.loads(saida) if saida.strip().startswith(("{", "[")) else saida


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True, help="ID da execução do workflow 'treino'")
    ap.add_argument("--repo", default="sarathais-tech/coflume-guardian-ai")
    ap.add_argument("--saida", type=Path, required=True)
    args = ap.parse_args(argv)

    jobs = _gh(f"repos/{args.repo}/actions/runs/{args.run}/jobs")["jobs"]
    anotacoes = []
    for job in jobs:
        anotacoes += _gh(f"repos/{args.repo}/check-runs/{job['id']}/annotations")
    conteudo = reconstruir(anotacoes)
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_bytes(conteudo)
    res = json.loads(conteudo)
    print(f"Execução {res['execucao'].get('ci_run_id')} · commit {str(res['execucao'].get('commit'))[:7]}")
    print(f"Conteúdo verificado (sha256 {hashlib.sha256(conteudo).hexdigest()[:16]}…) → {args.saida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
