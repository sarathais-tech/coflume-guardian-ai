# Coflume — Guardiã IA

> **Coflume — O Conhecimento Abre Portas**
> Repositório da inteligência artificial **Guardiã IA**, que estima a probabilidade de acerto do participante e participa da seleção adaptativa de desafios do cofre Coflume.

Apresentação prevista: **InovaTech, 11/11/2026**.

---

## O que este repositório contém

| Contém | Não contém |
|---|---|
| Rede neural MLP (modelo experimental principal) | Firmware do cofre (fica em `coflume`) |
| Árvore de decisão (baseline e alternativa) | Controle do servo, TFT, teclado ou LEDs |
| Especificação e cálculo das features | Regras de desbloqueio do cofre |
| Dados **sintéticos** e simulador | Dados pessoais de participantes |
| Treino, avaliação e métricas | Credenciais de qualquer tipo |
| Exportação do modelo para C++ e runtime de inferência | |
| Teste isolado de viabilidade no ESP32-S3 | |
| Documentação técnica e científica | |

## Como os dois repositórios se relacionam

```
coflume-guardian-ai  (este)                         coflume  (firmware)
─────────────────────────────                       ──────────────────────────
treino → avaliação → aprovação ──► release vX.Y.Z ──► copia 2 arquivos .h
                                   (guardia_runtime.h      e chama guardia::prever()
                                    guardia_modelo.h)
```

O firmware **só recebe um modelo depois que ele passa em todos os testes** deste repositório. O formato, as entradas, as saídas e as versões estão definidos em [`docs/contrato_integracao.md`](docs/contrato_integracao.md).

## O que é Machine Learning e o que não é

- **Machine Learning (aqui):** o modelo que estima `P(acerto)` a partir do comportamento do participante na sessão. Os pesos são aprendidos dos dados, nunca escritos à mão.
- **Lógica tradicional (no firmware):** escolher o nível com probabilidade próxima de 70%, evitar repetição, regras de reforço, critério de desbloqueio e acionamento do servo.

Detalhes em [`docs/arquitetura.md`](docs/arquitetura.md).

## Estado atual

| Item | Situação |
|---|---|
| Contrato de integração v1.0.0 | Definido |
| Especificação das features (incluindo primeira questão) | Definida e testada |
| Runtime C++ da MLP float32 | Implementado, equivalência com Python testada no PC |
| Teste de viabilidade no ESP32-S3 (pesos aleatórios) | **Pronto para rodar na placa**, resultados pendentes |
| Simulador de dados sintéticos | Próxima etapa |
| Treino e avaliação (MLP × árvore) | Próxima etapa |

## Início rápido

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate   |   Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt          # núcleo: numpy, scikit-learn, pytest
pip install -r requirements-treino.txt   # TensorFlow/Keras, só para treinar
pytest                                   # roda todos os testes
```

Os testes de equivalência C++ precisam de um compilador (`g++` ou `clang++`). Sem compilador, eles são pulados com aviso.

Gerar o teste de bancada para o ESP32-S3:

```bash
python -m ferramentas.gerar_bancada --semente 2026
```

Depois abra `embarcado/bancada_ia/bancada_ia.ino` no Arduino IDE. O procedimento completo está em [`docs/viabilidade_embarcada.md`](docs/viabilidade_embarcada.md).

## Estrutura

```
coflume-guardian-ai/
├── guardia/                  # pacote Python
│   ├── contrato.py           # versões e constantes do contrato
│   ├── features.py           # cálculo das entradas (fonte da verdade)
│   ├── inferencia_ref.py     # inferência de referência em numpy (float32)
│   ├── mlp.py                # construção e treino da MLP (Keras)
│   └── exportar/mlp_cpp.py   # gera guardia_modelo.h
├── embarcado/
│   ├── runtime/              # guardia_runtime.h (escrito à mão, versionado)
│   └── bancada_ia/           # sketch de viabilidade no ESP32-S3
├── ferramentas/              # scripts de linha de comando
├── tests/                    # pytest + testes C++ compilados no PC
├── docs/                     # arquitetura, contrato, protocolo, ADRs
├── dados/
│   ├── sinteticos/           # gerados por script (não versionados)
│   └── reais/                # NUNCA versionados
├── resultados/
│   ├── sinteticos/           # métricas obtidas com dados simulados
│   └── reais/                # métricas com dados reais (se houver piloto)
└── modelos/                  # modelos treinados (só os aprovados vão para release)
```

## Documentação

- [Arquitetura](docs/arquitetura.md)
- [Contrato de integração com o firmware](docs/contrato_integracao.md)
- [Especificação das features e da primeira questão](docs/features.md)
- [Protocolo de avaliação (pré-registrado)](docs/protocolo_avaliacao.md)
- [Dados: sintéticos × reais](docs/dados.md)
- [Viabilidade embarcada](docs/viabilidade_embarcada.md)
- [Reprodução do treinamento](docs/reproducao.md)
- [Fluxo de trabalho Git](docs/fluxo_git.md)
- [Registros de decisão (ADRs)](docs/adr/)

## Aviso sobre resultados

Resultados obtidos com **dados sintéticos** demonstram que o pipeline funciona e permitem comparar modelos em condições controladas. Eles **não** comprovam eficácia educacional. Qualquer afirmação sobre aprendizagem real exigiria dados reais coletados com consentimento e um desenho de estudo adequado.

## Privacidade

Nenhum dado pessoal é coletado: não há nome, idade, foto, escola ou identificador ligado a uma pessoa. Os logs de eventual piloto contêm apenas features numéricas e o resultado da questão, com um identificador de sessão aleatório. Esses logs não são versionados.
