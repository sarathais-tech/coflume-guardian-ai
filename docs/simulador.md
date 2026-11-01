# Simulador de dados sintéticos

**Versão atual:** `sim-1.1` (fluxo-0.8) · **Histórico:** `sim-1.0` · **Código:** `guardia/simulador.py` · **Decisões:** [ADR 0008](adr/0008-simulador-e-politica-de-coleta.md), [ADR 0009](adr/0009-fluxo-v08-e-sim-1-1.md)

> Tudo o que este simulador gera é **SINTÉTICO**. Serve para construir e testar o pipeline e comparar modelos em condições controladas. **Não** representa crianças reais e **não** comprova eficácia educacional.

## 1. Gerar os dados

```bash
# Atual (sim-1.1, fluxo-0.8): 4.000 participantes
python -m ferramentas.gerar_sinteticos --semente 2026
python -m ferramentas.dividir                                   # splits/split_v2.json

# Histórico (sim-1.0): 3.000 participantes
python -m ferramentas.gerar_sinteticos --versao sim-1.0 --semente 2026
python -m ferramentas.dividir --dados dados/sinteticos/sessoes_v1.csv --saida splits/split_v1.json
```

| Versão | Conjunto | Participantes / linhas | Split | Resumo (versionado) |
|---|---|---|---|---|
| **sim-1.1** | `sessoes_v2` | 4.000 / 12.000 | `splits/split_v2.json` (2.800 / 600 / 600) | `resultados/sinteticos/sessoes_v2_resumo.md` |
| sim-1.0 | `sessoes_v1` | 3.000 / 12.248 | `splits/split_v1.json` (2.100 / 450 / 450) | `resultados/sinteticos/sessoes_v1_resumo.md` |

Os CSVs e manifestos (`dados/sinteticos/`) não são versionados e são regenerados pelos comandos acima. O teste `test_conjunto_versionado_e_reproduzivel` regenera os dois conjuntos e compara com o SHA-256 registrado nos resumos, quando a versão do NumPy é a mesma.

## 2. Participantes simulados

Cada participante é um "aluno virtual" sem nenhum dado pessoal. Seu identificador é apenas o índice `0, 1, 2, …`.

| Atributo latente (nunca exportado) | Distribuição | Por quê |
|---|---|---|
| Nível inicial escolhido | Explorador 40%, Desafiante 35%, Mestre 25% | Crianças tendem a escolher níveis mais fáceis |
| Habilidade geral | Normal, média −0,7 / 0 / +0,7 conforme o nível inicial, desvio 0,8 | A escolha do nível se relaciona com a habilidade, mas de forma imperfeita |
| Habilidade por categoria | Habilidade geral + Normal(0; 0,5) | Uma criança pode ir bem em Matemática e mal em Português |
| Propensão a pedir dica | Normal(0; 0,8) | Algumas crianças pedem dica mais que outras |
| Velocidade | Log-normal, desvio 0,25 | Algumas crianças são mais rápidas |

O ganho de usar o nível inicial como sinal está nos dados, mas é **parcial**: há Exploradores habilidosos e Mestres com dificuldade.

## 3. Fluxo da partida simulada

| | **sim-1.1 (atual)** | sim-1.0 (histórico) |
|---|---|---|
| Referência | [fluxo-0.8](fluxo_partida.md), conferido com a descrição do firmware v0.7 feita pela equipe | Etapa 1 do projeto |
| Perguntas | **Exatamente 3**, categorias distintas sorteadas | 3 principais + até 3 reforços |
| Nível da pergunta 1 | **Nível escolhido pela criança** | Sorteado entre `nivel_inicial − 1` e `nivel_inicial` |
| Nível das perguntas 2 e 3 | **Sorteado na faixa nível inicial ± 1** | Sorteado entre os 3 níveis |
| Reforço após erro | **Não** | Sim (mesmo nível ou um abaixo, 50% / 50%) |
| Ganho de habilidade após erro | **0** | +0,3 |
| Dica (`*`) | Sim | Sim |
| Tempo limite | 30 s | 30 s |

### Política exploratória de geração × política adaptativa do cofre

Em **todas** as versões o simulador **sorteia** o nível entre os níveis permitidos. Essa é a **política exploratória de coleta**, que existe só para gerar dados sem viés de seleção.

A **política adaptativa do cofre** escolhe o nível pela previsão da Guardiã (alvo de 0,70). Ela está em `guardia/politica.py` e no firmware v0.8, e **não é usada para gerar dados de treino**. No `sim-1.1` as duas compartilham `politica.niveis_permitidos()`, então o modelo é treinado exatamente sobre os níveis que o cofre pode consultar. Detalhes em [`fluxo_partida.md`](fluxo_partida.md), seção 3.

Consequência: a taxa de partidas com 2 ou mais acertos nos dados gerados (67,3% no `sessoes_v2`) **não** é a taxa de desbloqueio esperada da v0.7 nem da v0.8.

## 4. Modelo de resposta

Para uma questão de nível `n` na categoria `c`:

1. **Dificuldade:** `b = [−1, 0, +1][n] + Normal(0; 0,3)`. A variação simula questões mais fáceis ou mais difíceis dentro do mesmo nível.
2. **Dica:** usada com probabilidade `sigmoide(−1,2 + 1,0 · (b − θc) + propensão)`. Quanto mais difícil a questão para a criança, maior a chance de pedir dica.
3. **Tempo:** log-normal com mediana `(10 s · e^(0,3·(b − θc)) + 4 s · dica) · velocidade` e desvio 0,45 no log. Ao passar do limite, o tempo fica em 30 s e a resposta conta como **erro**.
4. **Acerto, se não esgotou:**

   `P = 0,25 + 0,75 · sigmoide(1,2 · (θc − b) + 0,8 · dica)`

   É o modelo de 3 parâmetros da Teoria de Resposta ao Item. O piso de 0,25 representa o chute com 4 alternativas (A–D).
5. **Aprendizagem após erro:** no `sim-1.0`, a habilidade na categoria sobe 0,3 depois de um erro, para dar sentido ao reforço. No `sim-1.1` o ganho é **0**: não há reforço e a categoria não se repete na partida. O parâmetro `ganho_feedback_apos_erro` continua disponível para análise de sensibilidade.

Ordem fixa dos sorteios em cada questão: dificuldade, dica, tempo, acerto.

### `p_real`: a probabilidade verdadeira

O modelo da Guardiã precisa prever o acerto **antes** de saber se haverá dica ou tempo esgotado. Por isso o simulador registra:

```
p_real = Σ_dica  P(dica) · (1 − P(esgotar | dica)) · P(correta | dica)
```

Essa probabilidade é calculada no mesmo instante em que as features. Ela permite medir o erro de cada modelo em relação à verdade, como prevê o [protocolo](protocolo_avaliacao.md), seção 5. **É um oráculo: nunca pode ser feature.**

Verificação: em 30.000 participantes simulados (semente 99), a taxa de acerto observada ficou a até 2,1 erros-padrão da média de `p_real` em todas as 10 faixas. Diferença global entre acerto observado e média de `p_real`: 63,7% contra 63,6% no `sessoes_v1` e 62,7% contra 63,1% no `sessoes_v2` (cerca de 1 erro-padrão).

## 5. Features

As 9 features e a categoria de cada linha são calculadas por `guardia.features.montar_entrada`, com o histórico **anterior** à questão. É a mesma especificação que o runtime C++ segue (ver [`features.md`](features.md)). O teste `test_features_recalculadas_a_partir_do_historico_sao_identicas` reconstrói o histórico de cada sessão a partir das colunas `resp_*` e confirma que as features são idênticas bit a bit.

O tempo é registrado com resolução de 0,01 s, e as features usam esse mesmo valor arredondado.

## 6. Reprodutibilidade

- **Semente padrão: 2026**, registrada no manifesto.
- Cada participante tem um gerador próprio, derivado de `SeedSequence(semente, spawn_key=(id,))`. Por isso o participante 17 é idêntico gerando 50 ou 3.000 participantes.
- O CSV usa fim de linha `\n` e formatação fixa, o que dá bytes idênticos no mesmo ambiente.
- O manifesto registra a semente, todos os parâmetros, o SHA-256 do CSV e as versões de Python e numpy.
- **Limite:** o NumPy não garante a mesma sequência aleatória entre versões diferentes. Em outra versão, o CSV pode mudar. A **divisão por participante não muda**, porque depende só dos IDs e da semente. `conferir_hash_dados()` avisa quando o CSV difere do usado na criação do split.

## 7. Limitações

1. **O modelo aprende o simulador.** Os parâmetros foram escolhidos por plausibilidade, não estimados de dados reais de crianças.
2. **A forma da verdade é conhecida.** O acerto segue uma fórmula logística com piso, então modelos com estrutura parecida têm vantagem natural. Isso foi registrado no protocolo **antes** dos resultados, e os parâmetros não serão ajustados para favorecer nenhum modelo.
3. **Política de coleta diferente da de uso.** Os níveis são sorteados uniformemente dentro da faixa permitida. No cofre, a Guardiã vai escolher os níveis, e os dados reais terão outra distribuição.
4. **Comportamentos não simulados:** cansaço, distração, chute rápido, crianças que respondem em grupo, dificuldade real de cada questão do banco, leitura lenta de enunciados longos no TFT.
5. **Sessões curtas:** no `sim-1.1`, `n_respondidas` vai só de 0 a 2 e `sequencia` de −2 a +2, embora o contrato aceite até 8 e ±3. Isso é coerente com o fluxo-0.8, mas o modelo não terá experiência com sessões mais longas.
6. **Fluxo conferido com a descrição da v0.7 feita pela equipe, não com o código do firmware**, que está fora do escopo deste repositório.
7. **Banco real de questões:** o simulador supõe dificuldade coerente com o nível (desvio de 0,3). Perguntas fora do nível no banco real reduzirão a precisão (ver [`banco_questoes.md`](banco_questoes.md)).
8. **Nada aqui foi validado com crianças reais.**
