# Notas sobre a campanha experimental

## Contingência do serviço de autorização HTTP

A proposta previa testar a contingência com Biscuit. A campanha final injetou falhas HTTP, totais e parciais, apenas com JWT. As 192 execuções híbridas com Biscuit ocorreram sem falhas injetadas. [Proposta original](implementation/ARTICLE.md#test-scenarios) · [Contadores da auditoria](benchmarks/final-audit-20261117/RUN-CONTRACT-COUNTERS.jsonl)

O ensaio de contingência foi retirado da Metodologia e de Resultados e Discussão por falta de um teste equivalente com Biscuit.
