# Contrato de fluxo da partida: `fluxo-0.8`

**Versão:** fluxo-0.8 · **Data:** 01/11/2026 · **Situação:** proposta aprovada para implementação na v0.8; aguardando revisão do branch
**Implementação de referência:** `guardia/politica.py` · **Decisões:** [ADR 0009](adr/0009-fluxo-v08-e-sim-1-1.md)

Este documento define como uma partida do cofre Coflume v0.8 acontece e em que ponto a Guardiã IA participa. Ele complementa o [contrato de integração](contrato_integracao.md), que continua na versão **1.0.0** sem nenhuma alteração.

> O firmware **v0.7 permanece intacto**. A v0.8 é uma nova versão, desenvolvida no repositório `coflume` só depois da aprovação deste fluxo.

## 1. Comparação com a v0.7

| Aspecto | v0.7 (atual) | fluxo-0.8 |
|---|---|---|
| Perguntas por partida | 3 | **3** |
| Nível inicial | Escolhido pela criança | **Escolhido pela criança** |
| Dificuldade da pergunta 1 | Nível escolhido | **Nível escolhido** |
| Dificuldade das perguntas 2 e 3 | Nível escolhido | **Escolhida pela Guardiã, na faixa nível inicial ± 1** |
| Categorias | Ordem fixa do banco | **3 categorias distintas, sorteadas pelo jogo** |
| Tempo limite | 30 s | **30 s** |
| Dica (tecla `*`) | Sim | **Sim** |
| Resposta errada | Mostra a correta e avança | **Mostra a correta e avança** |
| Reforço | Não existe | **Não existe** |
| Desbloqueio | ≥ 2 acertos em 3 | **≥ 2 acertos em 3 (inalterado)** |

## 2. Sequência

1. A criança escolhe **Explorador (0)**, **Desafiante (1)** ou **Mestre (2)**.
2. O jogo gera um `sessao_id` aleatório (`esp_random()`), sorteia **3 categorias distintas** entre as 4 e chama `guardia::historico_limpar()`.
3. Para cada pergunta `k = 0, 1, 2`:
   1. **Níveis permitidos**
      - `k = 0`: somente o nível inicial.
      - `k = 1, 2`: nível inicial − 1, nível inicial e nível inicial + 1, limitados a 0..2.
   2. **Previsão:** para cada nível permitido, `montar_entrada(hist, nivel_inicial, categoria, nivel)` e `prever(entrada)`.
   3. **Escolha** (seção 3). Na pergunta 1 a previsão é só registrada, sem decidir nada.
   4. O jogo apresenta uma pergunta daquele nível e categoria que ainda não foi usada na partida.
   5. A criança responde em até **30 s** e pode usar a dica (`*`). Tempo esgotado conta como **erro**.
   6. O jogo registra a resposta com `historico_adicionar()`. Se a criança errou, mostra a resposta correta e avança.
   7. O jogo escreve a linha de log (seção 5).
4. **Desbloqueio:** o validador do firmware conta os acertos. Com **2 ou mais acertos em 3**, aciona o servo. **A Guardiã nunca aciona o servo** e não participa dessa regra.

## 3. Política adaptativa do cofre

| Regra | Valor |
|---|---|
| Alvo | Nível com previsão mais próxima de **0,70** |
| Empate (diferença < 1e-6) | Prefere o nível inicial; entre dois níveis diferentes do inicial, o mais baixo |
| Previsão `INVALIDO`, NaN ou fora de [0, 1] em qualquer candidato | Usa o nível inicial |
| Modelo desativado ou ausente | Usa o nível inicial, o que equivale ao comportamento da v0.7 |

Por que 0,70: se cada pergunta tiver chance de acerto `p`, a chance de abrir o cofre é `3p² − 2p³`. Com `p = 0,70`, isso dá 78%. A conta assume perguntas independentes e é só uma ilustração; o efeito real será estimado na simulação de políticas (protocolo, seção 7).

### Duas políticas que não podem ser confundidas

| | Política exploratória (geração de dados) | Política adaptativa (cofre) |
|---|---|---|
| Onde roda | Simulador `sim-1.1`, no PC | Firmware v0.8, no ESP32-S3 |
| Como escolhe o nível | **Sorteio uniforme** entre os níveis permitidos | **Previsão da Guardiã** mais próxima de 0,70 |
| Para quê | Gerar dados de treino sem viés de seleção | Ajustar o desafio para a criança |
| Código | `guardia/simulador.py` | `guardia/politica.py` (referência) e firmware |
| Em comum | `politica.niveis_permitidos()`: o modelo é treinado exatamente sobre os níveis que o cofre pode consultar | |

## 4. Uso das features (contrato 1.0.0 sem alterações)

- `nivel_candidato` é a dificuldade avaliada; a categoria entra pelas 4 posições one-hot.
- A Guardiã **não escolhe a categoria**: ela é sorteada pelo jogo, para garantir variedade e evitar que a IA fuja sempre para a matéria "mais fácil".
- Como as 3 categorias são distintas, a categoria candidata nunca tem respostas anteriores. Nesse caso `montar_entrada()` usa `taxa_acerto_sessao` como valor de `taxa_acerto_categoria` (implementação em Python e em C++). Por isso, no fluxo-0.8, **as duas features são sempre iguais**. Isso é redundante, mas válido, e a feature continua útil se uma versão futura repetir categorias. Os testes verificam a igualdade e a contraprova.
- Faixas efetivas: `n_respondidas` ∈ {0, 1, 2} e `sequencia` ∈ [−2, 2], ambas dentro do contrato.
- A dica continua sendo registrada e entra em `dicas_por_questao` a partir da pergunta 2.

## 5. Log por pergunta (para piloto real)

Uma linha na Serial por pergunta respondida, sem nenhum dado pessoal:

| Campo | Observação |
|---|---|
| `GUARDIA_MODELO_ID` | Rastreabilidade do modelo |
| `sessao_id` | Aleatório; sem relação com a pessoa |
| `ordem`, `nivel_inicial`, `categoria`, `nivel_candidato` (escolhido) | |
| As 9 features da entrada usada na escolha | Já calculadas pelo runtime |
| Previsões para cada nível permitido | `INVALIDO` quando aplicável |
| `acertou`, `usou_dica`, `tempo_gasto_s`, `tempo_limite_s`, `esgotou` | |

O formato exato da linha será fixado na integração com o firmware e convertido para o esquema de [`dados.md`](dados.md) com `fonte = REAL`. Dados do piloto continuam fora do Git.

**Atenção:** dados reais coletados com a política adaptativa têm **viés de seleção**, porque a Guardiã escolhe os níveis. Eles servem para avaliar o modelo no uso real e devem ser analisados separadamente dos sintéticos.

## 6. Requisitos para o firmware v0.8

1. A v0.7 continua disponível como versão estável. A v0.8 pode ter um `#define GUARDIA_ADAPTATIVA 0/1`; com 0, o nível fica fixo, como na v0.7.
2. Banco de perguntas organizado por nível e categoria (ver [`banco_questoes.md`](banco_questoes.md)).
3. Nenhuma pergunta se repete na mesma partida.
4. O servo só é acionado pelo validador da regra de 2 acertos em 3.

## 7. O que este fluxo não afirma

- A Guardiã foi treinada e avaliada apenas com **dados sintéticos**. **Ela não foi validada com crianças reais.**
- Taxas de desbloqueio e porcentagens de "zona ideal" vindas do simulador são resultados **[SINTÉTICO]** e não comprovam eficácia educacional.
