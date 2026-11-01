"""Gera o conjunto de dados SINTÉTICOS da Guardiã IA e seu resumo descritivo.

Uso:
    python -m ferramentas.gerar_sinteticos --semente 2026                    # sim-1.1 -> sessoes_v2
    python -m ferramentas.gerar_sinteticos --versao sim-1.0 --semente 2026   # histórico -> sessoes_v1

Saídas (padrão, <conjunto> = sessoes_v2 para sim-1.1 e sessoes_v1 para sim-1.0):
    dados/sinteticos/<conjunto>.csv            (não versionado; regenerável)
    dados/sinteticos/<conjunto>.manifest.json  (semente, parâmetros, sha256, ambiente)
    resultados/sinteticos/<conjunto>_resumo.md (estatísticas descritivas [SINTÉTICO])
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from guardia.dados import carregar
from guardia.politica import desbloqueio_referencia
from guardia.simulador import (
    CONJUNTOS_POR_VERSAO,
    SEMENTE_PADRAO,
    VERSAO_SIMULADOR,
    gerar_arquivo,
    parametros_da_versao,
)

RAIZ = Path(__file__).resolve().parents[1]

NOMES_NIVEL = ("Explorador", "Desafiante", "Mestre")
NOMES_CATEGORIA = ("Matemática", "Português", "Lógica", "Conhecimentos gerais")


def _pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def resumo(df: pd.DataFrame, manifesto: dict) -> str:
    por_part = df.groupby("participante_id").size()
    primeira = df[df["ordem"] == 0]
    L = [
        f"# [SINTÉTICO] Resumo do conjunto `{Path(manifesto['arquivo']).stem}`",
        "",
        "> Estatísticas descritivas de dados **gerados pelo simulador**. Não representam crianças reais "
        "e não comprovam eficácia educacional.",
        "",
        f"- **Versão do simulador:** {manifesto['versao_simulador']}"
        + (f" (fluxo da partida: {manifesto['fluxo']})" if manifesto.get("fluxo") else ""),
        f"- **Política de geração dos níveis:** {manifesto.get('politica_coleta', 'exploratoria-uniforme')} "
        "(sorteio entre os níveis permitidos; **não** é a política adaptativa do cofre)",
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

    L += _secoes_fluxo(df)

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


def _secoes_fluxo(df: pd.DataFrame) -> list[str]:
    """Seções extras quando todas as partidas têm exatamente 3 perguntas (fluxo-0.8)."""
    tam = df.groupby("participante_id").size()
    if not (tam == 3).all():
        return []
    L = ["", "## Nível sorteado por posição na partida", "",
         "Distribuição gerada pela política **exploratória** de coleta. No cofre, a Guardiã escolherá o nível.", "",
         "| Pergunta | Nível inicial | " + " | ".join(NOMES_NIVEL) + " |", "|---|---|---|---|---|"]
    for ordem in range(3):
        for ini in range(3):
            s = df[(df["ordem"] == ordem) & (df["nivel_inicial"] == ini)]["nivel_candidato"]
            cel = [f"{_pct((s == n).mean())}" if (s == n).any() else "—" for n in range(3)]
            L.append(f"| {ordem + 1} | {NOMES_NIVEL[ini]} | " + " | ".join(cel) + " |")
    iguais = (df["taxa_acerto_categoria"] == df["taxa_acerto_sessao"]).mean()
    acertos = df.groupby("participante_id")["acertou"].apply(lambda s: desbloqueio_referencia(list(s.astype(bool))))
    L += ["", "## Partidas", "", "| Medida | Valor |", "|---|---|",
          f"| Categorias distintas nas 3 perguntas | {_pct((df.groupby('participante_id')['categoria'].nunique() == 3).mean())} |",
          f"| Linhas com `taxa_acerto_categoria` = `taxa_acerto_sessao` | {_pct(iguais)} |",
          f"| Partidas com ≥ 2 acertos sob a política exploratória | {_pct(acertos.mean())} |",
          "",
          "> A taxa de partidas com 2 ou mais acertos acima vem do **sorteio** de níveis usado para gerar dados. "
          "Ela **não** é a taxa de desbloqueio esperada da v0.8 nem da v0.7; essas serão estimadas na "
          "simulação de políticas (protocolo, seção 7), também com dados sintéticos."]
    return L


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--versao", default=VERSAO_SIMULADOR, choices=sorted(CONJUNTOS_POR_VERSAO))
    ap.add_argument("--semente", type=int, default=SEMENTE_PADRAO)
    ap.add_argument("--participantes", type=int, default=None, help="padrão: 3000 (sim-1.0) ou 4000 (sim-1.1)")
    ap.add_argument("--saida", type=Path, default=None)
    ap.add_argument("--resumo", type=Path, default=None,
                    help="Arquivo Markdown do resumo; use --sem-resumo para não gerar.")
    ap.add_argument("--sem-resumo", action="store_true")
    args = ap.parse_args(argv)

    conjunto, n_padrao = CONJUNTOS_POR_VERSAO[args.versao]
    args.participantes = args.participantes or n_padrao
    args.saida = args.saida or RAIZ / "dados" / "sinteticos" / f"{conjunto}.csv"
    args.resumo = args.resumo or RAIZ / "resultados" / "sinteticos" / f"{conjunto}_resumo.md"

    manifesto = gerar_arquivo(args.saida, args.participantes, args.semente, parametros_da_versao(args.versao))
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
