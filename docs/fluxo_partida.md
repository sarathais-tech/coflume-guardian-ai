# Contrato de fluxo da partida: `fluxo-0.8`

**Versão:** fluxo-0.8 (revisão 2) · **Data:** 01/11/2026 · **Situação:** arquitetura aprovada; revisão 2 aguardando revisão do branch
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
2. O jogo gera um `sessao_id` aleatório (`esp_random()`), **sorteia uma ordem para as 4 categorias** e chama `guardia::historico_limpar()`. A partida usa 3 categorias distintas; a quarta fica de reserva para o caso de célula vazia (seção 3.1).
3. Para cada pergunta `k = 0, 1, 2` (referência: `politica.decidir_pergunta`):
   1. **Níveis permitidos**
      - `k = 0`: somente o nível inicial.
      - `k = 1, 2`: nível inicial − 1, nível inicial e nível inicial + 1, limitados a 0..2.
   2. **Categoria e níveis disponíveis:** a primeira categoria ainda não usada, na ordem sorteada, que tenha pergunta em pelo menos um nível permitido. **Níveis disponíveis** são os permitidos que têm pergunta nessa categoria.
   3. **Previsão:** para cada nível **disponível**, `montar_entrada(hist, nivel_inicial, categoria, nivel)` e `prever(entrada)`.
   4. **Escolha** (seção 3). Na pergunta 1 a previsão é só registrada, sem decidir nada.
   5. O jogo apresenta uma pergunta daquele nível e categoria.
   6. A criança responde em até **30 s** e pode usar a dica (`*`). Tempo esgotado conta como **erro**.
   7. O jogo registra a resposta com `historico_adicionar()`. Se a criança errou, mostra a resposta correta e avança.
   8. O jogo escreve a linha de log (seção 5).
4. **Desbloqueio:** o validador do firmware conta os acertos. Com **2 ou mais acertos em 3**, aciona o servo. **A Guardiã nunca aciona o servo** e não participa dessa regra.

## 3. Política adaptativa do cofre

| Regra | Valor |
|---|---|
| Candidatos | Somente níveis **disponíveis** (permitidos e com pergunta na categoria) |
| Alvo | Nível com previsão mais próxima de **0,70** |
| Empate (diferença < 1e-6) | Prefere o nível inicial; entre dois níveis diferentes do inicial, o mais baixo |
| Previsão `INVALIDO`, NaN ou fora de [0, 1] em qualquer candidato | Nível inicial, se disponível; senão o disponível mais próximo dele (empate: o mais baixo) |
| Modelo desativado ou ausente | A mesma regra acima; com o banco completo, equivale ao comportamento da v0.7 |

### 3.1 Célula vazia no banco

Uma **célula** é uma combinação nível × categoria. Se ela não tiver pergunta:

1. **O nível nunca sai da faixa permitida.** A Guardiã escolhe apenas entre os níveis disponíveis, que são um subconjunto dos permitidos.
2. **A previsão registrada é sempre a do nível apresentado.** Como só os níveis disponíveis são avaliados, não existe o caso de "a Guardiã escolheu um nível e o jogo mostrou outro".
3. **Se a categoria não tiver pergunta em nenhum nível permitido**, o jogo passa para a próxima categoria não usada, na ordem sorteada. Na pergunta 1, isso significa procurar uma categoria que tenha pergunta **no nível inicial**, que nunca é trocado.
4. **Se nenhuma categoria restante servir**, o banco é inviável para aquela partida. Isso deve ser detectado **antes da feira** por `ferramentas.validar_banco`, que testa todas as 72 combinações de nível inicial e ordem de categorias. No firmware, um banco inviável deve impedir o início da partida no modo adaptativo, com mensagem de erro, em vez de quebrar a faixa ou repetir pergunta.
5. A linha de log marca `categoria_substituida` e `celula_vazia`, para que a equipe veja quando o banco interferiu na decisão.

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
| `ordem`, `nivel_inicial` | |
| `categoria_sorteada`, `categoria` (apresentada), `categoria_substituida` | Seção 3.1 |
| `niveis_permitidos`, `niveis_disponiveis`, `celula_vazia` | Seção 3.1 |
| `nivel_candidato` (apresentado) e `motivo` | `motivo` ∈ `nivel_inicial_pergunta_1`, `guardia`, `fallback_sem_modelo`, `fallback_previsao_invalida` |
| `p_previsto` | Previsão **do nível apresentado**; `INVALIDO` quando não houver |
| Previsões de cada nível disponível | `INVALIDO` quando aplicável |
| `id` da pergunta apresentada | Permite detectar perguntas fora do nível no piloto |
| As 9 features da entrada do nível apresentado | Já calculadas pelo runtime |
| `acertou`, `usou_dica`, `tempo_gasto_s`, `tempo_limite_s`, `esgotou` | |

`politica.Decisao` contém todos os campos da decisão e serve de referência para a linha de log.

O formato exato da linha será fixado na integração com o firmware e convertido para o esquema de [`dados.md`](dados.md) com `fonte = REAL`. Dados do piloto continuam fora do Git.

**Atenção:** dados reais coletados com a política adaptativa têm **viés de seleção**, porque a Guardiã escolhe os níveis. Eles servem para avaliar o modelo no uso real e devem ser analisados separadamente dos sintéticos.

## 6. Requisitos para o firmware v0.8

1. A v0.7 continua disponível como versão estável. A v0.8 pode ter um `#define GUARDIA_ADAPTATIVA 0/1`; com 0, o nível fica fixo, como na v0.7.
2. Banco de perguntas organizado por nível e categoria e aprovado por `ferramentas.validar_banco`, sem perguntas inválidas e com todas as partidas viáveis (ver [`banco_questoes.md`](banco_questoes.md)).
3. Nenhuma pergunta se repete na mesma partida.
4. O servo só é acionado pelo validador da regra de 2 acertos em 3.

## 7. Situação da Guardiã e o que este fluxo não afirma

- **Situação em 01/11/2026:** a Guardiã foi treinada e avaliada **em validação**, com **dados sintéticos** (`sessoes_v2`, execução 41329660286 do CI; ver [`treino.md`](treino.md)). O conjunto de teste **continua lacrado** e nenhum modelo foi liberado para produção.
- Ela **não foi validada com crianças reais**, e isso deve ser dito sempre que o modelo for apresentado.
- Taxas de desbloqueio e porcentagens de "zona ideal" vindas do simulador são resultados **[SINTÉTICO]** e não comprovam eficácia educacional.

## Histórico de revisões

| Revisão | Data | Mudança |
|---|---|---|
| 1 | 01/11/2026 | Versão inicial do fluxo-0.8 |
| 3 | 01/11/2026 | Seção 7 atualizada após o treino em validação (dados sintéticos; teste lacrado) |
| 2 | 01/11/2026 | Seção 7 corrigida (a Guardiã ainda não foi treinada); fallback de célula vazia (seção 3.1) com nível sempre dentro da faixa; previsão registrada sempre a do nível apresentado; campos de log ampliados |
