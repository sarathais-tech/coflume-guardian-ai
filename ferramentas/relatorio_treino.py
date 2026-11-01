"""Gera o relatório Markdown e o diagrama de confiabilidade a partir de validacao.json.

Uso:
    python -m ferramentas.relatorio_treino resultados/sinteticos/treino_v2/validacao.json

Saídas na mesma pasta: relatorio_validacao.md e confiabilidade_validacao.png.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

NOMES = {"baseline": "Baseline ingênuo", "arvore": "Árvore de decisão",
         "logistica": "Regressão logística", "mlp": "MLP"}
METRICAS = [("log_loss", "Log loss ↓"), ("brier", "Brier ↓"), ("roc_auc", "ROC-AUC ↑"),
            ("ece", "ECE ↓"), ("mae_p_real", "Erro vs. p_real ↓")]
MIN_N_FAIXA = 20

AZUL, TEXTO, TEXTO_2, GRADE, FUNDO = "#2a78d6", "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"


def _f(v, casas=4):
    return "—" if v is None else f"{v:.{casas}f}"


def diagrama(res: dict, destino: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    modelos = [m for m in NOMES if m in res["modelos"]]
    fig, eixos = plt.subplots(1, len(modelos), figsize=(3.2 * len(modelos), 3.5), sharey=True, facecolor=FUNDO)
    eixos = list(eixos) if len(modelos) > 1 else [eixos]
    for ax, nome in zip(eixos, modelos):
        faixas = [f for f in res["modelos"][nome]["validacao"]["diagrama"] if f["n"] >= MIN_N_FAIXA]
        x = [f["confianca_media"] for f in faixas]
        y = [f["acerto_observado"] for f in faixas]
        ax.set_facecolor(FUNDO)
        ax.plot([0, 1], [0, 1], linestyle="--", linewidth=1, color=TEXTO_2, label="calibração perfeita")
        ax.plot(x, y, color=AZUL, linewidth=2, marker="o", markersize=6,
                markeredgecolor=FUNDO, markeredgewidth=1.5)
        ece = res["modelos"][nome]["validacao"]["metricas"]["ece"]
        ax.set_title(f"{NOMES[nome]}\nECE {ece:.3f}", fontsize=10, color=TEXTO)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_xlabel("Probabilidade prevista", fontsize=9, color=TEXTO_2)
        ax.grid(color=GRADE, linewidth=0.8)
        ax.tick_params(colors=TEXTO_2, labelsize=8)
        for lado in ax.spines.values():
            lado.set_color(GRADE)
    eixos[0].set_ylabel("Acerto observado", fontsize=9, color=TEXTO_2)
    eixos[0].legend(loc="upper left", fontsize=8, frameon=False, labelcolor=TEXTO_2)
    fig.suptitle(f"[SINTÉTICO] Confiabilidade em validação (faixas com n ≥ {MIN_N_FAIXA})",
                 fontsize=11, color=TEXTO)
    fig.tight_layout()
    fig.savefig(destino, dpi=150, facecolor=FUNDO)
    plt.close(fig)


def markdown(res: dict, nome_figura: str | None) -> str:
    ex, d, amb = res["execucao"], res["dados"], res["ambiente"]
    L = [
        "# [SINTÉTICO] Treino e avaliação em validação: Etapa 2",
        "",
        "> **Validação, não teste.** O conjunto de teste continua lacrado. Estes números servem para escolher "
        "modelos e hiperparâmetros e não são o resultado final do protocolo. Os dados são **sintéticos**: "
        "nada aqui comprova eficácia educacional nem desempenho com crianças reais.",
        "",
        "## Execução",
        "",
        "| Item | Valor |",
        "|---|---|",
        f"| Versão do pipeline | {res['versao']} |",
        f"| Execução do CI | {ex.get('ci_run_id') or 'local'} |",
        f"| Commit | `{str(ex.get('commit'))[:12]}` |",
        f"| Início (UTC) | {ex.get('inicio_utc')} |",
        f"| Dados | `{d['arquivo']}` ({d['versao_simulador']}), SHA-256 `{d['sha256'][:16]}…` |",
        f"| Igual ao CSV registrado no split | {'sim' if d['identico_ao_registrado'] else '**não**'} |",
        f"| Divisão | `{d['split']}`: {d['n_participantes']['treino']} participantes no treino "
        f"({d['n_linhas']['treino']} linhas), {d['n_participantes']['validacao']} na validação "
        f"({d['n_linhas']['validacao']} linhas) |",
        f"| Conjuntos carregados | {', '.join(d['conjuntos_carregados'])} (teste lacrado) |",
        f"| Ambiente | " + ", ".join(f"{k} {v}" for k, v in amb.items() if k != "plataforma") + " |",
        f"| Sementes | geral {res['sementes']['geral']}; MLP {res['sementes']['mlp']}; "
        f"candidata {res['sementes']['mlp_candidata']} |",
        "",
        "## Desempenho em validação",
        "",
        "| Modelo | " + " | ".join(t for _, t in METRICAS) + " |",
        "|---|" + "---|" * len(METRICAS),
    ]
    for nome in NOMES:
        if nome not in res["modelos"]:
            continue
        m = res["modelos"][nome]
        if nome == "mlp":
            med, dp = m["validacao_media"], m["validacao_dp"]
            L.append(f"| MLP {m['escolhido']['arquitetura']}: média ± dp de {len(m['execucoes'])} sementes | "
                     + " | ".join(f"{_f(med[k])} ± {_f(dp[k])}" for k, _ in METRICAS) + " |")
            v = m["validacao"]["metricas"]
            L.append(f"| MLP: semente candidata {m['semente_candidata']} | "
                     + " | ".join(_f(v.get(k)) for k, _ in METRICAS) + " |")
        else:
            v = m["validacao"]["metricas"]
            L.append(f"| {NOMES[nome]} | " + " | ".join(_f(v.get(k)) for k, _ in METRICAS) + " |")
    o = res["oraculo_p_real"]["validacao"]
    L.append("| *Referência: `p_real` do simulador (oráculo)* | "
             + " | ".join(f"*{_f(o.get(k))}*" for k, _ in METRICAS) + " |")
    L += ["", "O oráculo usa a probabilidade verdadeira, que nenhum modelo pode observar. Ele mostra o melhor "
          "desempenho possível com estes dados, e sua ECE dá uma ideia do ruído de amostragem da métrica "
          f"com {d['n_linhas']['validacao']} linhas.", ""]
    if nome_figura:
        L += [f"![Diagramas de confiabilidade]({nome_figura})", ""]

    L += ["## Comparações preliminares em validação (bootstrap por participante)", "",
          "Diferença de log loss A − B: negativo favorece A. IC de 95%, 2.000 reamostragens de participantes.", "",
          "| Comparação | Diferença | IC 95% | Cruza zero? |", "|---|---|---|---|"]
    for k, c in res["comparacoes_validacao_preliminares"].items():
        a, b = k.split("_menos_")
        L.append(f"| {NOMES[a]} − {NOMES[b]} | {c['diferenca']:+.4f} | [{c['ic'][0]:+.4f}; {c['ic'][1]:+.4f}] | "
                 f"{'sim' if c['cruza_zero'] else 'não'} |")
    if "mlp" in res["modelos"]:
        L += ["", "> A MLP usou a validação para o *early stopping*. Suas métricas de validação são, por isso, "
              "levemente otimistas em relação às da árvore e da regressão logística, que nunca viram a validação. "
              "A regra de decisão do protocolo (seção 6) só se aplica no teste lacrado."]

    L += ["", "## Seleção de hiperparâmetros (GroupKFold, 5 folds, só no treino)", ""]
    for nome in ("arvore", "logistica"):
        if nome not in res["modelos"]:
            continue
        m = res["modelos"][nome]
        L += [f"### {NOMES[nome]}", "", f"Escolhido: `{m['escolhido']}`", "",
              "| Parâmetros | Log loss CV (média ± dp) |", "|---|---|"]
        for g in sorted(m["grade"], key=lambda g: g["cv_log_loss_media"]):
            L.append(f"| `{g['params']}` | {g['cv_log_loss_media']:.4f} ± {g['cv_log_loss_dp']:.4f} |")
        L.append("")
    if "mlp" in res["modelos"]:
        m = res["modelos"]["mlp"]
        L += ["### MLP", "", f"Regra: {m['regra_escolha']}. Escolhida: **{m['escolhido']['arquitetura']}** "
              f"({m['escolhido']['n_parametros']} parâmetros).", "",
              "| Arquitetura | Parâmetros | Log loss CV (média ± dp) | Época de parada por fold |", "|---|---|---|---|"]
        for g in m["grade"]:
            L.append(f"| {g['arquitetura']} | {g['n_parametros']} | {g['cv_log_loss_media']:.4f} ± "
                     f"{g['cv_log_loss_dp']:.4f} | {g['epocas_melhor_por_fold']} |")
        L += ["", "| Semente | Épocas (melhor / executadas) | Log loss | Brier | ROC-AUC | ECE |", "|---|---|---|---|---|---|"]
        for e in m["execucoes"]:
            v = e["validacao"]
            L.append(f"| {e['semente']} | {e['epocas']['melhor']} / {e['epocas']['executadas']} | "
                     f"{_f(v['log_loss'])} | {_f(v['brier'])} | {_f(v['roc_auc'])} | {_f(v['ece'])} |")
        L += ["", f"Equivalência Keras × formato do contrato (máx. |Δp|): "
              f"{m['equivalencia_keras_formato_contrato_max']:.2e}. O modelo **não** foi exportado para o ESP32.", ""]
    return "\n".join(L) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("resultado", type=Path)
    ap.add_argument("--sem-figura", action="store_true")
    args = ap.parse_args(argv)
    res = json.loads(args.resultado.read_text(encoding="utf-8"))
    pasta = args.resultado.parent
    figura = None
    if not args.sem_figura:
        figura = "confiabilidade_validacao.png"
        diagrama(res, pasta / figura)
    (pasta / "relatorio_validacao.md").write_text(markdown(res, figura), encoding="utf-8")
    print(f"Relatório: {pasta / 'relatorio_validacao.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
