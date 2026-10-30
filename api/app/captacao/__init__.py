"""Captação externa — candidatos de FORA do colégio, achados por resultado
público de olimpíada, vestibular e concurso (docs/41).

Aqui mora o domínio que a tela e o assistente dividem: as leituras de
`consultas.py`. O HTTP fica em `routes/captacao.py`; as tools da coordenação,
em `chat/tools/captacao.py`. Quem escreve conquista e perfil continuam sendo
os scripts de `api/scripts/` (importador e resolver) e as rotas do modo
avançado — nada daqui escreve.

⚠️ `candidato_externo` NÃO é `aluno`. É gente que nunca pôs os pés no colégio,
muitas vezes menor de idade, e que não se cadastrou no SAS (migration 0056).
"""
