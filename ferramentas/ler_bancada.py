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

CRITERIOS_FUNCIONAIS = [
    ("Erro máximo de P(acerto) vs. Python: vetores aleatórios", "erro_p_max_aleatorios", "< 1e-5"),
    ("Erro máximo de P(acerto) vs. Python: vetores de validação", "erro_p_max_validacao", "< 1e-5"),
    ("Erro máximo nas features", "erro_features_max", "≤ 1e-6"),
    ("Divergências em features inteiras", "falhas_inteiras", "0"),
    ("Saídas inválidas para entradas válidas", "invalidos", "0"),
    ("Entradas inválidas e partida a frio tratadas corretamente", "casos_entrada_corretos", "todos os casos"),
    ("Variação do heap em 10.000 chamadas de prever()", "heap_variacao_prever_bytes", "0 bytes"),
    ("Variação do heap em 10.000 chamadas de montar_entrada()", "heap_variacao_montar_entrada_bytes", "0 bytes"),
]
LATENCIA = [
    ("Latência média de prever()", "latencia_prever_us_media"),
    ("Pior latência observada de prever()", "latencia_prever_us_pior"),
    ("Decisão completa (3 níveis)", "latencia_decisao_3_niveis_us_media"),
]
APROVACOES = {"APROVADO", "APROVADO_FUNCIONAL"}


def ler(texto: str) -> dict[str, str]:
    valores: dict[str, str] = {}
    for linha in texto.splitlines():
        partes = linha.strip().split(",", 2)
        if len(partes) == 3 and partes[0] == "BANCADA":
            valores[partes[1]] = partes[2]
    if valores.get("fim") != "ok":
        raise ValueError("Log incompleto: a linha 'BANCADA,fim,ok' não foi encontrada.")
    if valores.get("inicio") != "guardia_bancada_v2":
        raise ValueError("Log de outra versão da bancada; use o sketch atual (guardia_bancada_v2).")
    return valores


def relatorio(v: dict[str, str], data: dt.date | None = None) -> str:
    data = data or dt.date.today()
    na_placa = v.get("ambiente") == "placa"
    L = [
        f"# Bancada ESP32-S3 ({v.get('ambiente')}): {v['modelo_id']}",
        "",
        f"- **Data:** {data:%d/%m/%Y}",
        f"- **Ambiente:** {v.get('ambiente')} · chip {v.get('chip', '?')}",
        f"- **Contrato:** {v.get('contrato', '?')} · **uso do modelo:** {v.get('modelo_uso', '?')}",
        f"- **Fonte dos pesos:** {v.get('modelo_fonte', '?')}",
        f"- **Parâmetros:** {v.get('n_parametros', '?')} ({v.get('camadas_ocultas', '?')} camada(s) oculta(s); "
        f"{v.get('pesos_bytes', '?')} bytes de pesos e padronização)",
        f"- **Hash do modelo:** `{v.get('modelo_hash', '?')}`",
        f"- **Vetores:** {v.get('n_vetores_aleatorios', '?')} aleatórios + {v.get('n_vetores_validacao', '?')} da validação",
        "",
        "## Correção funcional",
        "",
        "| Critério | Medido | Exigido |",
        "|---|---|---|",
    ]
    for nome, chave, exigido in CRITERIOS_FUNCIONAIS:
        valor = v.get(chave, "—")
        if chave == "casos_entrada_corretos":
            valor = f"{valor} de {v.get('casos_entrada_testados', '?')}"
        L.append(f"| {nome} | {valor} | {exigido} |")
    L += [
        "",
        f"- Equivalência: **{v.get('criterio_equivalencia')}**",
        f"- Entradas inválidas e partida a frio: **{v.get('criterio_entradas')}**",
        f"- Sem alocação dinâmica nas funções da Guardiã: **{v.get('criterio_sem_alocacao')}**",
        "",
        f"Informativo (não é critério): heap livre total {v.get('heap_livre_total_informativo', '?')} bytes; "
        f"mínimo livre {v.get('heap_minimo_livre_informativo', '?')} bytes; sketch {v.get('sketch_bytes', '?')} bytes.",
        "",
        "## Latência",
        "",
        "| Medida | Valor (µs) |",
        "|---|---|",
    ]
    L += [f"| {nome} | {v.get(chave, '—')} |" for nome, chave in LATENCIA]
    if na_placa:
        L += ["", f"Critério (< 1000 µs, média e pior caso): **{v.get('criterio_latencia')}**"]
    else:
        L += ["", "> **Latência simulada, apenas indicativa.** O Wokwi executa a CPU mais devagar que a placa real; "
              "estes valores **não** representam o desempenho do ESP32-S3 físico. O critério de latência só é "
              "avaliado na placa."]
    L += ["", f"## Resultado: **{v.get('resultado')}**", ""]
    if v.get("modelo_fonte") == "ALEATORIO":
        L.append("> Pesos ALEATÓRIOS: este relatório mede viabilidade embarcada, não qualidade de previsão.")
    elif v.get("modelo_fonte") == "SINTETICO":
        L.append("> Modelo treinado com dados SINTÉTICOS. Exportado só para a bancada: não é versão de produção.")
    return "\n".join(L) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("log", type=Path)
    ap.add_argument("--salvar", action="store_true")
    args = ap.parse_args(argv)

    v = ler(args.log.read_text(encoding="utf-8", errors="replace"))
    md = relatorio(v)
    print(md)
    if args.salvar:
        destino = RAIZ / "resultados" / "embarcado" / f"{v['modelo_id']}_{v.get('ambiente', 'placa')}.md"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(md, encoding="utf-8")
        print(f"Salvo em {destino}")
    return 0 if v.get("resultado") in APROVACOES else 1


if __name__ == "__main__":
    raise SystemExit(main())
