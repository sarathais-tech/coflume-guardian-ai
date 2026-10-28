"""Exporta uma MLP para C++ conforme o contrato 1.x.

Gera três artefatos:
- guardia_modelo.h : pesos, média, desvio e metadados (constexpr, vai para a Flash)
- vetores_teste.h  : históricos e saídas esperadas, para testes no PC e na placa
- MODELO.json      : metadados legíveis por pessoas e scripts

Os floats são escritos com 9 dígitos significativos, o que garante que o
compilador reconstrua exatamente o mesmo float32 do Python.
"""

from __future__ import annotations

import datetime as _dt
import json
from dataclasses import asdict
from pathlib import Path
from typing import Sequence

import numpy as np

from guardia import contrato as C
from guardia.features import Entrada, Resposta, montar_entrada
from guardia.inferencia_ref import ModeloMLP, prever

AVISO = "// ARQUIVO GERADO AUTOMATICAMENTE — NÃO EDITAR À MÃO."


def _f(v: float) -> str:
    s = f"{float(np.float32(v)):.9g}"
    if "e" not in s and "." not in s and "inf" not in s and "nan" not in s:
        s += ".0"
    return s + "f"


def _vetor(valores: np.ndarray, por_linha: int = 8) -> str:
    itens = [_f(v) for v in np.asarray(valores).reshape(-1)]
    linhas = [", ".join(itens[i : i + por_linha]) for i in range(0, len(itens), por_linha)]
    return "{\n    " + ",\n    ".join(linhas) + "\n}"


def _matriz(W: np.ndarray) -> str:
    return "{\n  " + ",\n  ".join(_vetor(linha, 16).replace("\n", "") for linha in W) + "\n}"


def identificador(modelo: ModeloMLP, data: _dt.date | None = None) -> str:
    fonte = modelo.metadados.get("fonte", "ALEATORIO")
    if fonte not in C.FONTES_VALIDAS:
        raise ValueError(f"Fonte inválida: {fonte!r}. Use uma de {C.FONTES_VALIDAS}.")
    arq = "mlp" + "x".join(str(h) for h in modelo.ocultas)
    data = data or _dt.date.today()
    return f"{arq}-{C.FONTE_PREFIXO[fonte]}-{data:%Y%m%d}-{modelo.hash()[:8]}"


def gerar_cabecalho_modelo(modelo: ModeloMLP, modelo_id: str) -> str:
    ocultas = modelo.ocultas
    h1 = ocultas[0]
    h2 = ocultas[1] if len(ocultas) > 1 else 0
    fonte = modelo.metadados.get("fonte", "ALEATORIO")

    partes = [
        "// =============================================================================",
        "//  guardia_modelo.h — Guardiã IA · Coflume — O Conhecimento Abre Portas",
        AVISO,
        f"//  Modelo: {modelo_id}",
        f"//  Fonte dos dados: {fonte}",
        "// =============================================================================",
        "#pragma once",
        "#define GUARDIA_MODELO_H_INCLUIDO 1",
        "",
        f"#define GUARDIA_MODELO_CONTRATO_MAJOR {C.CONTRATO_MAJOR}",
        f"#define GUARDIA_MODELO_CONTRATO_VERSAO \"{C.CONTRATO_VERSAO}\"",
        f"#define GUARDIA_MODELO_ID \"{modelo_id}\"",
        f"#define GUARDIA_MODELO_HASH \"{modelo.hash()}\"",
        f"#define GUARDIA_MODELO_FONTE \"{fonte}\"",
        f"#define GUARDIA_MODELO_N_PARAMETROS {modelo.n_parametros}",
        f"#define GUARDIA_N_ENTRADAS {C.N_ENTRADAS}",
        f"#define GUARDIA_H1 {h1}",
        f"#define GUARDIA_H2 {h2}",
        "",
        "// Padronização das 9 features numéricas (média e desvio do conjunto de treino).",
        f"constexpr float GUARDIA_MEDIA[{C.N_NUMERICAS}] = {_vetor(modelo.media)};",
        f"constexpr float GUARDIA_DESVIO[{C.N_NUMERICAS}] = {_vetor(modelo.desvio)};",
        "",
        "// Camada oculta 1: W[saida][entrada]",
        f"constexpr float GUARDIA_W_O1[{h1}][{C.N_ENTRADAS}] = {_matriz(modelo.camadas[0][0])};",
        f"constexpr float GUARDIA_B_O1[{h1}] = {_vetor(modelo.camadas[0][1])};",
        "",
    ]
    if h2:
        partes += [
            "// Camada oculta 2",
            f"constexpr float GUARDIA_W_O2[{h2}][{h1}] = {_matriz(modelo.camadas[1][0])};",
            f"constexpr float GUARDIA_B_O2[{h2}] = {_vetor(modelo.camadas[1][1])};",
            "",
        ]
    W_s, b_s = modelo.camadas[-1]
    partes += [
        "// Camada de saída (sigmoide aplicada no runtime)",
        f"constexpr float GUARDIA_W_SAIDA[{W_s.shape[1]}] = {_vetor(W_s[0])};",
        f"constexpr float GUARDIA_B_SAIDA = {_f(b_s[0])};",
        "",
    ]
    return "\n".join(partes)


# ---------------------------------------------------------------------------
# Vetores de teste
# ---------------------------------------------------------------------------

def gerar_casos(n: int, semente: int, frac_frio: float = 0.2) -> list[tuple[list[Resposta], int, int, int]]:
    """Históricos e candidatos aleatórios, incluindo partida a frio e casos-limite."""
    rng = np.random.default_rng(semente)
    casos: list[tuple[list[Resposta], int, int, int]] = []
    for i in range(n):
        if i < n * frac_frio:
            tam = 0
        else:
            tam = int(rng.integers(1, 9))
        hist = []
        for _ in range(tam):
            limite = float(rng.choice([20.0, 30.0, 40.0]))
            # inclui tempos acima do limite (esgotado) e limites inválidos raros
            gasto = float(rng.uniform(0, limite * 1.2))
            if rng.random() < 0.03:
                limite = 0.0
            hist.append(
                Resposta(
                    categoria=int(rng.integers(0, C.N_CATEGORIAS)),
                    nivel=int(rng.integers(0, C.N_NIVEIS)),
                    acertou=bool(rng.random() < 0.6),
                    tempo_gasto_s=gasto,
                    tempo_limite_s=limite,
                    usou_dica=bool(rng.random() < 0.3),
                )
            )
        casos.append(
            (
                hist,
                int(rng.integers(0, C.N_NIVEIS)),
                int(rng.integers(0, C.N_CATEGORIAS)),
                int(rng.integers(0, C.N_NIVEIS)),
            )
        )
    return casos


def _resposta_cpp(r: Resposta) -> str:
    return (
        f"{{{r.categoria}, {r.nivel}, {str(r.acertou).lower()}, "
        f"{_f(r.tempo_gasto_s)}, {_f(r.tempo_limite_s)}, {str(r.usou_dica).lower()}}}"
    )


def _entrada_cpp(e: Entrada) -> str:
    return (
        f"{{{e.nivel_candidato}, {e.nivel_inicial}, {e.n_respondidas}, {e.categoria}, "
        f"{_f(e.taxa_acerto_sessao)}, {_f(e.taxa_acerto_categoria)}, {_f(e.tempo_medio_norm)}, "
        f"{_f(e.dicas_por_questao)}, {e.resultado_ultima}, {e.sequencia}}}"
    )


def gerar_cabecalho_vetores(
    modelo: ModeloMLP, modelo_id: str, casos: Sequence[tuple[list[Resposta], int, int, int]]
) -> tuple[str, list[dict]]:
    """Gera vetores_teste.h e devolve os casos com as saídas esperadas do Python."""
    hist_max_caso = max((len(h) for h, *_ in casos), default=0)
    hist_max_caso = max(hist_max_caso, 1)
    linhas = []
    registros = []
    for hist, nivel_ini, cat, nivel_cand in casos:
        e = montar_entrada(hist, nivel_ini, cat, nivel_cand)
        p = prever(modelo, e)
        itens = [_resposta_cpp(r) for r in hist] or ["{0, 0, false, 0.0f, 1.0f, false}"]
        linhas.append(
            f"  {{ {{{', '.join(itens)}}}, {len(hist)}, {nivel_ini}, {cat}, {nivel_cand},\n"
            f"    {_entrada_cpp(e)}, {_f(p)} }}"
        )
        registros.append({"entrada": asdict(e), "p": p, "n_hist": len(hist)})

    cab = "\n".join(
        [
            "// =============================================================================",
            "//  vetores_teste.h — casos de equivalência Python × C++ da Guardiã IA",
            AVISO,
            f"//  Modelo: {modelo_id}",
            "// =============================================================================",
            "#pragma once",
            f"#define GUARDIA_VETORES_MODELO_ID \"{modelo_id}\"",
            f"#define GUARDIA_VETORES_HIST_MAX {hist_max_caso}",
            f"#define GUARDIA_N_VETORES {len(casos)}",
            "",
            "struct GuardiaVetorTeste {",
            "  guardia::Resposta historico[GUARDIA_VETORES_HIST_MAX];",
            "  uint8_t n_historico;",
            "  uint8_t nivel_inicial, categoria, nivel_candidato;",
            "  guardia::Entrada entrada_esperada;",
            "  float p_esperado;",
            "};",
            "",
            "const GuardiaVetorTeste GUARDIA_VETORES[GUARDIA_N_VETORES] = {",
            ",\n".join(linhas),
            "};",
            "",
        ]
    )
    return cab, registros


def exportar(
    modelo: ModeloMLP,
    pasta: Path,
    n_vetores: int = 200,
    semente_vetores: int = 7,
    data: _dt.date | None = None,
    metricas: dict | None = None,
) -> dict:
    """Escreve guardia_modelo.h, vetores_teste.h e MODELO.json em `pasta`."""
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    modelo_id = identificador(modelo, data)

    (pasta / "guardia_modelo.h").write_text(gerar_cabecalho_modelo(modelo, modelo_id), encoding="utf-8")
    casos = gerar_casos(n_vetores, semente_vetores)
    cab_vetores, registros = gerar_cabecalho_vetores(modelo, modelo_id, casos)
    (pasta / "vetores_teste.h").write_text(cab_vetores, encoding="utf-8")

    meta = {
        "projeto": "Coflume — O Conhecimento Abre Portas",
        "ia": "Guardiã IA",
        "modelo_id": modelo_id,
        "contrato": C.CONTRATO_VERSAO,
        "arquitetura": {
            "tipo": "MLP",
            "entradas": C.N_ENTRADAS,
            "ocultas": list(modelo.ocultas),
            "ativacao_oculta": "relu",
            "saida": "sigmoide",
            "n_parametros": modelo.n_parametros,
            "precisao": "float32",
        },
        "fonte_dados": modelo.metadados.get("fonte", "ALEATORIO"),
        "hash_sha256": modelo.hash(),
        "features": list(C.FEATURES_NUMERICAS) + [f"categoria_{i}" for i in range(C.N_CATEGORIAS)],
        "vetores_teste": {"n": n_vetores, "semente": semente_vetores},
        "metricas": metricas or {},
        "metadados": {k: v for k, v in modelo.metadados.items() if k != "fonte"},
        "aviso": (
            "Resultados com dados SINTETICOS ou pesos ALEATORIOS não comprovam eficácia educacional."
        ),
    }
    (pasta / "MODELO.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"modelo_id": modelo_id, "registros": registros, "meta": meta}
