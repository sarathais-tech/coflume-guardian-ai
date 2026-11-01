"""Exporta a MLP candidata TREINADA para a bancada do ESP32-S3 no Wokwi.

Uso:
    python -m ferramentas.exportar_bancada

Antes de gerar qualquer arquivo:
1. confere o SHA-256 de validacao.json com o publicado pelo CI (ORIGEM.json);
2. carrega os pesos de mlp_candidata.npz e confere arquitetura e parâmetros;
3. recalcula em Python as previsões de toda a VALIDAÇÃO e compara com as métricas do CI.

Saída (padrão: embarcado/bancada_wokwi/), pronta para o wokwi.com:
    sketch.ino  guardia_modelo.h  guardia_runtime.h  vetores_teste.h  diagram.json  MODELO.json

Exportação SÓ PARA A BANCADA: não é versão de produção nem release. O teste lacrado não é usado.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from guardia import contrato as C
from guardia.artefato import carregar_mlp_npz, carregar_validacao, conferir_com_validacao, sha256
from guardia.dados import carregar, carregar_split, conjunto
from guardia.exportar.mlp_cpp import gerar_cabecalho_modelo, gerar_cabecalho_vetores, gerar_casos, identificador
from guardia.features import Resposta
from guardia.treino import preparar

RAIZ = Path(__file__).resolve().parents[1]
TREINO = RAIZ / "resultados" / "sinteticos" / "treino_v2"
SKETCH = RAIZ / "embarcado" / "bancada_ia" / "bancada_ia.ino"
RUNTIME = RAIZ / "embarcado" / "runtime" / "guardia_runtime.h"
USO = "bancada (nao e versao de producao)"
SEMENTE_VETORES = 7

# Identificador da placa no Wokwi: nome comum, NÃO confirmado em documentação oficial.
# Em caso de dúvida, crie o projeto pelo modelo ESP32-S3 do próprio wokwi.com (docs/bancada_wokwi.md).
DIAGRAMA = {
    "version": 1,
    "author": "Coflume - Guardia IA (bancada)",
    "editor": "wokwi",
    "parts": [{"type": "board-esp32-s3-devkitc-1", "id": "esp", "top": 0, "left": 0, "attrs": {}}],
    "connections": [["esp:TX", "$serialMonitor:RX", "", []], ["esp:RX", "$serialMonitor:TX", "", []]],
    "dependencies": {},
}


def indices_validacao(n_linhas: int, n_vetores: int) -> list[int]:
    """Índices espaçados que alternam a posição da pergunta (1ª, 2ª, 3ª, 1ª, ...).

    As linhas da validação vêm em blocos de 3 por participante; escolher sempre o
    mesmo deslocamento pegaria só a 1ª pergunta (partida a frio).
    """
    passo = max(3, (n_linhas // n_vetores) // 3 * 3)
    return [k * passo + (k % 3) for k in range(n_vetores) if k * passo + (k % 3) < n_linhas]


def casos_validacao(df_validacao, n_vetores: int) -> list[tuple[list[Resposta], int, int, int]]:
    """Linhas da VALIDAÇÃO com o histórico real anterior do mesmo participante."""
    casos = []
    escolhidos = set(indices_validacao(len(df_validacao), n_vetores))
    for i, r in enumerate(df_validacao.itertuples(index=False)):
        if i not in escolhidos:
            continue
        anteriores = df_validacao[(df_validacao["participante_id"] == r.participante_id)
                                  & (df_validacao["ordem"] < r.ordem)].sort_values("ordem")
        hist = [Resposta(int(a.categoria), int(a.nivel_candidato), bool(a.acertou), float(a.resp_tempo_gasto_s),
                         float(a.resp_tempo_limite_s), bool(a.resp_usou_dica)) for a in anteriores.itertuples()]
        casos.append((hist, int(r.nivel_inicial), int(r.categoria), int(r.nivel_candidato)))
    return casos


def exportar(saida: Path, npz: Path, validacao_json: Path, sha_validacao: str, dados: Path, split: Path,
             n_aleatorios: int = 200, n_validacao: int = 200) -> dict:
    validacao = carregar_validacao(validacao_json, sha_validacao)
    modelo = carregar_mlp_npz(npz, uso="bancada", semente=validacao["modelos"]["mlp"]["semente_candidata"])
    d = preparar(dados, split)  # só treino e validação
    conferencia = conferir_com_validacao(modelo, validacao, d.X_va, d.y_va, d.p_real_va)

    import datetime as dt

    data_treino = dt.date.fromisoformat(validacao["execucao"]["inicio_utc"][:10])
    modelo_id = identificador(modelo, data_treino)

    df = carregar(dados)
    df_va = conjunto(df, carregar_split(split), "validacao")
    aleatorios = gerar_casos(n_aleatorios, SEMENTE_VETORES)
    reais = casos_validacao(df_va, n_validacao)

    saida = Path(saida)
    saida.mkdir(parents=True, exist_ok=True)
    cab = gerar_cabecalho_modelo(modelo, modelo_id).replace(
        f'#define GUARDIA_MODELO_FONTE "{modelo.metadados["fonte"]}"',
        f'#define GUARDIA_MODELO_FONTE "{modelo.metadados["fonte"]}"\n#define GUARDIA_MODELO_USO "{USO}"',
    )
    (saida / "guardia_modelo.h").write_text(cab, encoding="utf-8")
    vet, registros = gerar_cabecalho_vetores(modelo, modelo_id, aleatorios + reais)
    vet = vet.replace(
        f"#define GUARDIA_N_VETORES {len(aleatorios) + len(reais)}",
        f"#define GUARDIA_N_VETORES {len(aleatorios) + len(reais)}\n"
        f"#define GUARDIA_N_VETORES_ALEATORIOS {len(aleatorios)}\n"
        f"#define GUARDIA_N_VETORES_VALIDACAO {len(reais)}",
    )
    (saida / "vetores_teste.h").write_text(vet, encoding="utf-8")
    shutil.copy(RUNTIME, saida / "guardia_runtime.h")
    (saida / "sketch.ino").write_text(
        "// Gerado por ferramentas/exportar_bancada.py a partir de embarcado/bancada_ia/bancada_ia.ino.\n"
        '#define BANCADA_AMBIENTE "wokwi"\n' + SKETCH.read_text(encoding="utf-8"), encoding="utf-8")
    (saida / "diagram.json").write_text(json.dumps(DIAGRAMA, indent=2) + "\n", encoding="utf-8")

    meta = {
        "projeto": "Coflume — O Conhecimento Abre Portas",
        "ia": "Guardiã IA",
        "uso": "bancada no Wokwi e na placa; NÃO é versão de produção",
        "modelo_id": modelo_id,
        "hash_sha256": modelo.hash(),
        "contrato": C.CONTRATO_VERSAO,
        "fonte_dados": "SINTETICO",
        "arquitetura": {"entradas": C.N_ENTRADAS, "ocultas": list(modelo.ocultas), "saida": "sigmoide",
                        "n_parametros": modelo.n_parametros, "precisao": "float32"},
        "origem": {"execucao_ci": validacao["execucao"]["ci_run_id"], "commit": validacao["execucao"]["commit"],
                   "pesos_npz_sha256": sha256(npz), "validacao_json_sha256": sha_validacao},
        "conferencia_em_validacao": {k: conferencia[k] for k in ("n_validacao", "diferenca_max", "tolerancia",
                                                                  "metricas_registradas")},
        "vetores": {"aleatorios": len(aleatorios), "semente_aleatorios": SEMENTE_VETORES,
                    "validacao": len(reais),
                    "validacao_por_posicao": {f"pergunta_{k + 1}": sum(len(h) == k for h, *_ in reais) for k in range(3)},
                    "partida_a_frio": sum(r["n_hist"] == 0 for r in registros)},
        "teste_lacrado": True,
        "aviso": "Modelo treinado com dados SINTÉTICOS; não foi validado com crianças reais.",
    }
    (saida / "MODELO.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return meta


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--npz", type=Path, default=TREINO / "mlp_candidata.npz")
    ap.add_argument("--validacao", type=Path, default=TREINO / "validacao.json")
    ap.add_argument("--sha-validacao", default=None, help="padrão: o registrado em ORIGEM.json")
    ap.add_argument("--dados", type=Path, default=RAIZ / "dados" / "sinteticos" / "sessoes_v2.csv")
    ap.add_argument("--split", type=Path, default=RAIZ / "splits" / "split_v2.json")
    ap.add_argument("--saida", type=Path, default=RAIZ / "embarcado" / "bancada_wokwi")
    args = ap.parse_args(argv)

    sha = args.sha_validacao or json.loads((TREINO / "ORIGEM.json").read_text(encoding="utf-8"))[
        "validacao_json_sha256_publicado_pelo_ci"]
    meta = exportar(args.saida, args.npz, args.validacao, sha, args.dados, args.split)
    print(f"[SINTÉTICO] {meta['modelo_id']} · {meta['arquitetura']['n_parametros']} parâmetros · uso: bancada")
    print(f"Conferência em validação: diferença máx. {meta['conferencia_em_validacao']['diferenca_max']:.2e}")
    print(f"Vetores: {meta['vetores']['aleatorios']} aleatórios + {meta['vetores']['validacao']} da validação "
          f"({meta['vetores']['partida_a_frio']} de partida a frio)")
    print(f"Arquivos em {args.saida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
