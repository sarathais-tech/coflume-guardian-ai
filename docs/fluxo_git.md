# Fluxo de trabalho Git

## Branches

| Branch | Uso | Pode quebrar? |
|---|---|---|
| `main` | Sempre estável; todos os testes passam | Não |
| `feat/<tema>` | Funcionalidade que vai para o `main` (ex.: `feat/simulador`) | Durante o desenvolvimento |
| `exp/<tema>` | Experimento que pode ser descartado (ex.: `exp/tflite-micro`, `exp/mlp-int8`) | Sim |
| `fix/<tema>` | Correção | Durante o desenvolvimento |

Branches `exp/*` só entram no `main` se o experimento for aprovado. Experimentos encerrados ficam no histórico e são documentados num ADR ou em `resultados/`.

## Commits

Mensagens em português, no formato [Conventional Commits](https://www.conventionalcommits.org/pt-br/):

```
feat(runtime): adiciona montar_entrada com partida a frio
fix(features): trata tempo_limite_s <= 0 como tempo esgotado
docs(contrato): define versão 1.0.0
test(equivalencia): compara Python e C++ em 200 vetores
exp(bancada): mede latência da MLP no ESP32-S3
chore: atualiza .gitignore
```

## Tags e releases

- `contrato-vX.Y.Z`: marca mudanças de contrato.
- `vX.Y.Z`: release com modelo aprovado e os arquivos do contrato anexados.
- O firmware referencia a release usada no seu próprio log de mudanças.

## Nunca versionar

- Credenciais, tokens, chaves, arquivos `.env`.
- Dados reais de participantes, mesmo anônimos.
- Modelos não aprovados (`modelos/` é ignorado; releases publicam os aprovados).
- Arquivos gerados da bancada (`embarcado/bancada_ia/*.h`).

O `.gitignore` já bloqueia esses casos, mas a responsabilidade final é de quem faz o commit.
