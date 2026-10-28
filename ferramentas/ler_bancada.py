"""Lê a saída serial da bancada e gera um relatório em Markdown.

Uso:
    python -m ferramentas.ler_bancada log_serial.txt
    python -m ferramentas.ler_bancada log_serial.txt --salvar

Com --salvar, grava em resultados/embarcado/<modelo_id>.md.
"""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

CRITERIOS = [
    ("Erro máximo de P(acerto) vs. Python", "erro_p_max", "< 1e-5"),
    ("Erro máximo nas features", "erro_features_max", "≤ 1e-6"),
    ("Divergências em features inteiras", "falhas_inteiras", "0"),
    ("Saídas inválidas", "invalidos", "0"),
    ("Latência média de prever()", "latencia_prever_us_media", "< 1000 µs"),
    ("Pior latência observada de prever()", "latencia_prever_us_pior", "< 1000 µs"),
    ("Decisão completa (3 níveis)", "latencia_decisao_3_niveis_us_media", "informativo"),
    ("Heap consumido", "heap_consumido", "0 bytes"),
]


def ler(texto: str) -> dict[str, str]:
    valores: dict[str, str] = {}
    for linha in texto.splitlines():
        partes = linha.strip().split(",", 2)
        if len(partes) == 3 and partes[0] == "BANCADA":
            valores[partes[1]] = partes[2]
    if valores.get("fim") != "ok":
        raise ValueError("Log incompleto: a linha 'BANCADA,fim,ok' não foi encontrada.")
    return valores


def relatorio(v: dict[str, str], data: dt.date | None = None) -> str:
    data = data or dt.date.today()
    linhas = [
        f"# Bancada ESP32-S3 — {v['modelo_id']}",
        "",
        f"- **Data:** {data:%d/%m/%Y}",
        f"- **Chip:** {v.get('chip', '?')} a {v.get('cpu_mhz', '?')} MHz",
        f"- **Contrato:** {v.get('contrato', '?')}",
        f"- **Fonte dos pesos:** {v.get('modelo_fonte', '?')}",
        f"- **Parâmetros:** {v.get('n_parametros', '?')} ({v.get('pesos_bytes', '?')} bytes de pesos e padronização)",
        f"- **Tamanho do sketch:** {v.get('sketch_bytes', '?')} bytes",
        f"- **Hash:** `{v.get('modelo_hash', '?')}`",
        "",
        "| Critério | Medido | Exigido |",
        "|---|---|---|",
    ]
    for nome, chave, exigido in CRITERIOS:
        linhas.append(f"| {nome} | {v.get(chave, '—')} | {exigido} |")
    linhas += [
        "",
        f"- Equivalência: **{v.get('criterio_equivalencia')}**",
        f"- Latência: **{v.get('criterio_latencia')}**",
        f"- Sem alocação dinâmica: **{v.get('criterio_sem_alocacao')}**",
        "",
        f"## Resultado: **{v.get('resultado')}**",
        "",
    ]
    if v.get("modelo_fonte") == "ALEATORIO":
        linhas.append(
            "> Pesos ALEATÓRIOS: este relatório mede viabilidade embarcada, não qualidade de previsão."
        )
    return "\n".join(linhas) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("log", type=Path)
    ap.add_argument("--salvar", action="store_true")
    args = ap.parse_args(argv)

    v = ler(args.log.read_text(encoding="utf-8", errors="replace"))
    md = relatorio(v)
    print(md)
    if args.salvar:
        destino = RAIZ / "resultados" / "embarcado" / f"{v['modelo_id']}.md"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(md, encoding="utf-8")
        print(f"Salvo em {destino}")
    return 0 if v.get("resultado") == "APROVADO" else 1


if __name__ == "__main__":
    raise SystemExit(main())
