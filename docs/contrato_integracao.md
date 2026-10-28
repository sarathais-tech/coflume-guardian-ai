# Contrato de integração: Guardiã IA ↔ firmware Coflume

**Versão do contrato:** 1.0.0
**Data:** 28/10/2026
**Partes:** `coflume-guardian-ai` (fornecedor) e `coflume` (consumidor)

Este documento define tudo o que o firmware pode assumir sobre a Guardiã IA. O que não estiver aqui não é garantido.

## 1. Versionamento

Usamos [SemVer](https://semver.org/lang/pt-BR/) para o contrato:

| Mudança | Versão |
|---|---|
| Muda a struct, a ordem ou o significado das features, ou a assinatura das funções | **MAJOR** (2.0.0) |
| Acrescenta função ou campo opcional sem quebrar o uso atual (ex.: árvore embarcada) | MINOR (1.1.0) |
| Correção no runtime sem mudança de interface | PATCH (1.0.1) |

O **modelo** tem identificador próprio, independente do contrato. Trocar os pesos por um modelo retreinado **não** muda a versão do contrato, desde que as entradas sejam as mesmas.

Formato do identificador do modelo:
```
<arquitetura>-<fonte>-<AAAAMMDD>-<hash8>
ex.: mlp16x8-sint-20261102-3fa9c1d2
```
`fonte` é `sint` (sintético), `real`, `misto` ou `aleat` (pesos aleatórios, apenas para bancada).

## 2. Artefatos entregues por release

Cada release `vX.Y.Z` do `coflume-guardian-ai` publica:

| Arquivo | Descrição | Editável? |
|---|---|---|
| `guardia_runtime.h` | Inferência e cálculo de features, escrito à mão e versionado | Não |
| `guardia_modelo.h` | Pesos, média e desvio, metadados (gerado) | **Nunca editar à mão** |
| `MODELO.json` | Metadados: id, contrato, fonte dos dados, métricas, hash, commit | Não |
| `vetores_teste.h` | 200 entradas com saídas esperadas, para autoteste opcional | Não |

O firmware copia `guardia_runtime.h` e `guardia_modelo.h` para a pasta do sketch. Ambos são *header-only*: não há `.cpp` nem biblioteca externa.

## 3. Interface C++

```cpp
#include "guardia_modelo.h"
#include "guardia_runtime.h"

// Verificação de compatibilidade em tempo de compilação
static_assert(GUARDIA_CONTRATO_MAJOR == 1, "Contrato da Guardiã incompatível");

guardia::Historico hist;                 // um por sessão
guardia::historico_limpar(hist);         // no início da sessão

// após cada questão respondida:
guardia::Resposta r{categoria, nivel, acertou, tempo_gasto_s, tempo_limite_s, usou_dica};
guardia::historico_adicionar(hist, r);

// para avaliar um candidato:
guardia::Entrada e = guardia::montar_entrada(hist, nivel_inicial, categoria, nivel_candidato);
float p = guardia::prever(e);            // [0, 1] ou guardia::INVALIDO
```

### Tipos

```cpp
namespace guardia {
  struct Resposta {
    uint8_t categoria;        // 0..3
    uint8_t nivel;            // 0..2
    bool    acertou;
    float   tempo_gasto_s;    // >= 0
    float   tempo_limite_s;   // > 0
    bool    usou_dica;
  };
  struct Historico { Resposta itens[GUARDIA_HIST_MAX]; uint8_t n; };
  struct Entrada {            // features já calculadas, NÃO normalizadas
    uint8_t nivel_candidato, nivel_inicial, n_respondidas, categoria;
    float   taxa_acerto_sessao, taxa_acerto_categoria, tempo_medio_norm, dicas_por_questao;
    int8_t  resultado_ultima, sequencia;
  };
  constexpr float INVALIDO = -1.0f;
}
```

As definições exatas das features estão em [`features.md`](features.md).

## 4. Garantias do fornecedor

`guardia::prever()`:

1. Retorna um valor em **[0, 1]** para toda entrada válida.
2. Retorna **`INVALIDO` (−1,0)** se qualquer campo estiver fora da faixa ou for NaN.
3. É uma **função pura**: mesma entrada, mesma saída; sem estado global, sem alocação dinâmica, sem `Serial`, sem acesso a hardware.
4. Usa memória de pilha menor que 256 bytes.
5. Executa em **menos de 1 ms** no ESP32-S3 a 240 MHz (medido na bancada).
6. Reproduz a saída do modelo Python com erro absoluto **< 1e-5** nos vetores de teste publicados.

## 5. Responsabilidades do consumidor (firmware)

1. Registrar cada resposta com `historico_adicionar`, inclusive a primeira questão e as de reforço.
2. Tratar `INVALIDO` com fallback: árvore (quando o contrato 1.1 existir) ou regra fixa (nível inicial).
3. **Nunca** acionar o servo com base na saída da Guardiã. O desbloqueio depende apenas do validador do jogo.
4. Não editar `guardia_modelo.h` nem `guardia_runtime.h`. Problemas devem virar *issue* neste repositório.
5. Registrar no log serial o `GUARDIA_MODELO_ID` em uso, para rastreabilidade.

## 6. Portões de aprovação para release

Um modelo só é publicado se:

- [ ] Todos os testes do `pytest` passam, incluindo equivalência Python × C++.
- [ ] O modelo cumpre o [protocolo de avaliação](protocolo_avaliacao.md) (comparação com baseline e árvore no teste lacrado).
- [ ] A bancada no ESP32-S3 foi executada com este modelo e os critérios de [`viabilidade_embarcada.md`](viabilidade_embarcada.md) foram atendidos.
- [ ] `MODELO.json` informa corretamente a fonte dos dados (`SINTETICO`, `REAL` ou `MISTO`).
- [ ] O `model card` correspondente foi escrito, com a seção de limitações.

## 7. Histórico

| Versão | Data | Mudança |
|---|---|---|
| 1.0.0 | 28/10/2026 | Versão inicial: MLP float32, features v1.0 com partida a frio |
