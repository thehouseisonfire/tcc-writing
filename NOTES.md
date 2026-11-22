# Notas sobre a campanha experimental

## Contingência do serviço de autorização HTTP

A proposta previa testar a contingência com Biscuit. A campanha final injetou falhas HTTP, totais e parciais, apenas com JWT. As 192 execuções híbridas com Biscuit ocorreram sem falhas injetadas. [Proposta original](implementation/ARTICLE.md#test-scenarios) · [Contadores da auditoria](benchmarks/final-audit-20261117/RUN-CONTRACT-COUNTERS.jsonl)

O ensaio de contingência foi retirado da Metodologia e de Resultados e Discussão por falta de um teste equivalente com Biscuit.

## MTU

A tese usa os pares JWT e Biscuit de 500 e 1.500 bytes da Parte 1. Deixe fora da análise os cenários de 200 e 9.000 bytes e os de 1.500 bytes da Parte 2, que só têm JWT. Em 9.000 bytes, a rede da qualificação tinha interfaces configuradas em 1.500 bytes e só o caso JWT sem TLS entrou na campanha final. [Índice da auditoria](benchmarks/final-audit-20261117/ANALYSIS-INDEX.csv) · [Relatório de qualificação](implementation/mqtt-auth-biscuit/benchmarks/results-qual-frozen-b23eb22-c10-m10-20260914T060835Z/_QUALIFICATION-REPORT.md)

## Atraso no serviço HTTP

A Metodologia registra os testes pareados de 200 ms da Parte 1, com JWT e Biscuit, com e sem TLS. A varredura de 200 ms e 1 s da Parte 2 só tem JWT e ficou fora da análise. A avaliação da H3 usa a comparação entre Biscuit local e JWT via HTTP. [Índice da auditoria](benchmarks/final-audit-20261117/ANALYSIS-INDEX.csv)
