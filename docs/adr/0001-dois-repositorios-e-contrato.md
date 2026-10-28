# ADR 0001: Dois repositórios e contrato de integração

- **Status:** aceito
- **Data:** 2026-10-28

## Contexto
O firmware do cofre e a IA evoluem em ritmos diferentes e têm riscos diferentes. Um experimento de ML não pode quebrar a versão estável do cofre para a InovaTech (11/11/2026).

## Opções avaliadas
1. Um único repositório com pastas separadas.
2. Dois repositórios privados com contrato documentado.

## Decisão
Opção 2: `coflume` (firmware e hardware) e `coflume-guardian-ai` (IA). A integração é feita por releases versionadas contendo dois cabeçalhos C++ e um `MODELO.json`, conforme `docs/contrato_integracao.md`.

## Consequências
- Controle de acesso separado e histórico mais limpo.
- O firmware só recebe modelos aprovados.
- Exige disciplina: toda mudança de interface passa por versão do contrato.
- O firmware precisa copiar os cabeçalhos a cada release (sem submódulos, para manter o Arduino IDE simples).
