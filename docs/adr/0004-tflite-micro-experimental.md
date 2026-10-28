# ADR 0004: TensorFlow Lite Micro apenas como experimento

- **Status:** aceito
- **Data:** 2026-10-28

## Contexto
O TFLite Micro é o framework padrão da indústria para ML em microcontroladores. O suporte oficial da Espressif (`esp-tflite-micro`) é para ESP-IDF. Para Arduino existem ports da comunidade (ex.: `Chirale_TensorFlowLite`, última versão em julho de 2024), anteriores ao Arduino-ESP32 3.x.

## Decisão
Usar o TFLite Micro apenas num sketch de bancada separado, em branch `exp/*`, para comparar tamanho, memória e latência com o runtime próprio. Ele nunca entra no firmware da feira. Se não compilar no Arduino-ESP32 3.x até o portão G1 (30/10/2026), o experimento é encerrado e o resultado é documentado.

## Consequências
- Comparação com o padrão da indústria sem risco para o cofre.
- Primeiro item a ser cortado se o prazo apertar.
