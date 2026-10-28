# ADR 0005: ESP-DL descartado

- **Status:** descartado
- **Data:** 2026-10-28

## Contexto
O ESP-DL é o framework de inferência da Espressif, com quantização via ESP-PPQ.

## Motivos
- Requer ESP-IDF v5.3 ou superior; o projeto usa Arduino IDE.
- Exige o formato `.espdl`, gerado pelo ESP-PPQ a partir de ONNX ou PyTorch; modelos Keras teriam de passar por ONNX.
- A documentação recomenda PC com Linux; a equipe usa VS Code em ambiente diverso.
- O foco do framework é visão e áudio; a aceleração não traz ganho perceptível para 369 parâmetros.
- O prazo até 11/11/2026 não comporta a migração de toolchain.

## Consequências
Registrado como alternativa avaliada. Pode ser reconsiderado se o projeto continuar após a feira com modelos maiores.
