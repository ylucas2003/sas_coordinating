"""Stats engine — cálculos derivados que rodam ao fim de cada upload.

Princípio: tudo é calculado no servidor e persistido em tabelas de cache
(`metrica_simulado`, `classificacao_aluno`, `alerta`). O frontend nunca
recalcula nada — só lê das tabelas.

Submódulos:
  - metricas       : agregados por simulado (geral, turma, sede + histograma)
  - classificacao  : perfil/tendência/zona dos alunos
  - alertas        : engine de 7 regras + dedup por hash
  - thresholds     : constantes calibráveis num lugar só
  - utils          : regressão linear, percentis, Welch, helpers comuns
"""
