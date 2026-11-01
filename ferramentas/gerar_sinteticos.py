"""Gera o conjunto de dados SINTÉTICOS da Guardiã IA e seu resumo descritivo.

Uso:
    python -m ferramentas.gerar_sinteticos --semente 2026
    python -m ferramentas.gerar_sinteticos --semente 2026 --participantes 3000

Saídas (padrão):
    dados/sinteticos/sessoes_v1.csv            (não versionado; regenerável)
    dados/sinteticos/sessoes_v1.manifest.json  (semente, parâmetros, sha256, ambiente)
    resultados/sinteticos/sessoes_v1_resumo.md (estatísticas descritivas [SINTÉTICO])
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from guardia.dados import carregar
from guardia.simulador import N_PARTICIPANTES_PADRAO, SEMENTE_PADRAO, gerar_arquivo

RAIZ = Path(__file__).resolve().parents[1]
CSV_PADRAO = RAIZ / "dados" / "sinteticos" / "sessoes_v1.csv"
RESUMO_PADRAO = RAIZ / "resultados" / "sinteticos" / "sessoes_v1_resumo.md"

NOMES_NIVEL = ("Explorador", "Desafiante", "Mestre")
NOMES_CATEGORIA = ("Matemática", "Português", "Lógica", "Conhecimentos gerais")


def _pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def resumo(df: pd.DataFrame, manifesto: dict) -> str:
    por_part = df.groupby("participante_id").size()
    primeira = df[df["ordem"] == 0]
    L = [
        "# [SINTÉTICO] Resumo do conjunto `sessoes_v1`",
        "",
        "> Estatísticas descritivas de dados **gerados pelo simulador**. Não representam crianças reais "
        "e não comprovam eficácia educacional.",
        "",
        f"- **Versão do simulador:** {manifesto['versao_simulador']}",
        f"- **Semente:** {manifesto['semente']}",
        f"- **SHA-256 do CSV:** `{manifesto['sha256']}`",
        f"- **Ambiente:** Python {manifesto['ambiente']['python']}, numpy {manifesto['ambiente']['numpy']}",
        "",
        "## Tamanho",
        "",
        "| Medida | Valor |",
        "|---|---|",
        f"| Participantes | {df['participante_id'].nunique()} |",
        f"| Linhas (questões respondidas) | {len(df)} |",
        f"| Questões por participante (mín. / média / máx.) | {por_part.min()} / {por_part.mean():.2f} / {por_part.max()} |",
        f"| Questões principais / de reforço | {(df['tipo'] == 'principal').sum()} / {(df['tipo'] == 'reforco').sum()} |",
        f"| Linhas de partida a frio (1ª questão) | {len(primeira)} |",
        "",
        "## Respostas",
        "",
        "| Medida | Valor |",
        "|---|---|",
        f"| Taxa de acerto observada | {_pct(df['acertou'].mean())} |",
        f"| Média de `p_real` (probabilidade verdadeira) | {_pct(df['p_real'].mean())} |",
        f"| Uso de dica | {_pct(df['resp_usou_dica'].mean())} |",
        f"| Tempo esgotado | {_pct(df['resp_esgotou'].mean())} |",
        f"| Tempo gasto (mediana / p90), em s | {df['resp_tempo_gasto_s'].median():.1f} / {df['resp_tempo_gasto_s'].quantile(0.9):.1f} |",
        "",
        "## Participantes por nível inicial",
        "",
        "| Nível inicial | Participantes |",
        "|---|---|",
    ]
    ini = df.drop_duplicates("participante_id")["nivel_inicial"].value_counts().sort_index()
    L += [f"| {NOMES_NIVEL[k]} | {v} ({_pct(v / ini.sum())}) |" for k, v in ini.items()]

    L += ["", "## Taxa de acerto observada por nível inicial × nível da questão", "",
          "Entre parênteses: número de linhas.", "",
          "| Nível inicial \\ questão | " + " | ".join(NOMES_NIVEL) + " |", "|---|---|---|---|"]
    for i in range(3):
        cel = []
        for j in range(3):
            s = df[(df["nivel_inicial"] == i) & (df["nivel_candidato"] == j)]["acertou"]
            cel.append(f"{_pct(s.mean())} ({len(s)})" if len(s) else "—")
        L.append(f"| {NOMES_NIVEL[i]} | " + " | ".join(cel) + " |")

    L += ["", "## Taxa de acerto por categoria", "", "| Categoria | Acerto | Linhas |", "|---|---|---|"]
    for c in range(4):
        s = df[df["categoria"] == c]["acertou"]
        L.append(f"| {NOMES_CATEGORIA[c]} | {_pct(s.mean())} | {len(s)} |")

    L += ["", "## Consistência do oráculo (`p_real` × acerto observado)", "",
          "Se `p_real` é a probabilidade verdadeira, a taxa de acerto em cada faixa deve ficar próxima da média de `p_real`.", "",
          "| Faixa de `p_real` | Linhas | Média de `p_real` | Acerto observado |", "|---|---|---|---|"]
    faixas = np.linspace(0, 1, 11)
    for lo, hi in zip(faixas[:-1], faixas[1:]):
        s = df[(df["p_real"] >= lo) & ((df["p_real"] < hi) | ((hi == 1.0) & (df["p_real"] <= hi)))]
        if len(s):
            L.append(f"| {lo:.1f}–{hi:.1f} | {len(s)} | {s['p_real'].mean():.3f} | {s['acertou'].mean():.3f} |")
    L.append("")
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--semente", type=int, default=SEMENTE_PADRAO)
    ap.add_argument("--participantes", type=int, default=N_PARTICIPANTES_PADRAO)
    ap.add_argument("--saida", type=Path, default=CSV_PADRAO)
    ap.add_argument("--resumo", type=Path, default=RESUMO_PADRAO,
                    help="Arquivo Markdown do resumo; use --sem-resumo para não gerar.")
    ap.add_argument("--sem-resumo", action="store_true")
    args = ap.parse_args(argv)

    manifesto = gerar_arquivo(args.saida, args.participantes, args.semente)
    df = carregar(args.saida)  # valida o que acabou de ser gerado
    print(f"[SINTÉTICO] {manifesto['n_linhas']} linhas de {manifesto['n_participantes']} participantes")
    print(f"Semente {manifesto['semente']} · {manifesto['versao_simulador']} · sha256 {manifesto['sha256'][:16]}…")
    print(f"Arquivo: {args.saida}")
    if not args.sem_resumo:
        args.resumo.parent.mkdir(parents=True, exist_ok=True)
        args.resumo.write_text(resumo(df, manifesto), encoding="utf-8")
        print(f"Resumo: {args.resumo}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
