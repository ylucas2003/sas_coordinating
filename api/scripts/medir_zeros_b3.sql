-- Medição da B.3 — "zero × ausência nas estatísticas" (docs/32 §1.1, Onda 0)
--
-- SOMENTE LEITURA. Nenhum INSERT/UPDATE/DELETE, nenhuma tabela temporária.
-- Rodar contra PRODUÇÃO: o banco de desenvolvimento é uma cópia de 22/08 e
-- subestima o problema em 3× (docs/32 §1.1.1). Foi exatamente esse erro que
-- a primeira versão do plano cometeu.
--
-- Uso, no VPS:
--   cd /opt/sas/infra/vps
--   docker compose exec -T db psql -U postgres -d sas -f - < medir_zeros_b3.sql
--
-- Ou, do laptop, num comando só:
--   ssh sas@46.202.150.165 'cd /opt/sas/infra/vps && docker compose exec -T db \
--     psql -U postgres -d sas' < api/scripts/medir_zeros_b3.sql
--
-- Cada bloco tem um \echo dizendo o que responde e o que esperar. O que
-- interessa mesmo é o bloco 4: é ele que sustenta (ou derruba) a regra
-- proposta em docs/32 §1.4.

\pset border 2
\pset footer off
\timing off

\echo ''
\echo '════ 1 · Panorama — o tamanho do que estamos medindo ════'
\echo '(dev em 22/08, para comparar: 26.810 notas · 877 alunos · 152 simulados)'
\echo ''

select
    (select count(*) from nota)                                        as notas,
    (select count(*) from nota where presente)                         as presentes,
    (select count(*) from nota where not presente)                     as ausentes,
    (select count(*) from nota where presente and pontuacao = 0)       as zeros_com_presenca,
    round(
        100.0 * (select count(*) from nota where presente and pontuacao = 0)
              / nullif((select count(*) from nota where presente), 0)
    , 2)                                                               as pct_dos_presentes,
    (select count(*) from aluno)                                       as alunos,
    (select count(*) from simulado)                                    as simulados,
    (select count(*) from questao)                                     as questoes,
    (select count(*) from questao_resposta_aluno)                      as respostas;

\echo ''
\echo '════ 2 · O Canvas chamou algum desses zeros de falta? ════'
\echo '(esperado: nenhum. Se aparecer missing=t, a B.3 muda de natureza)'
\echo ''

select canvas_missing, canvas_excused, canvas_workflow_state, count(*)
from nota
where presente and pontuacao = 0
group by 1, 2, 3
order by 4 desc;

\echo ''
\echo '════ 3 · Como a ausência é representada hoje ════'
\echo '(o dev tinha 9 linhas presente=false; produção tem dezenas de milhares)'
\echo ''

select canvas_missing, canvas_excused, canvas_workflow_state, count(*)
from nota
where not presente
group by 1, 2, 3
order by 4 desc
limit 10;

\echo ''
\echo '════ 4 · A EVIDÊNCIA — é este bloco que decide a regra ════'
\echo 'Para cada zero com presença, olha as respostas de questão do aluno.'
\echo 'todo_em_branco = não marcou NENHUMA alternativa: é ausência, não nota.'
\echo '(dev: 414 sem dado · 54 todo em branco · 103 respondeu tudo · 15 parcial)'
\echo ''

with questoes_por_simulado as (
    select simulado_id, count(*) as n_questoes
    from questao
    group by 1
),
respostas_do_aluno as (
    select r.aluno_id,
           q.simulado_id,
           count(*)                                          as n_respostas,
           count(*) filter (where r.alternativa_id is null)   as n_brancos
    from questao_resposta_aluno r
    join questao q on q.id = r.questao_id
    group by 1, 2
),
zeros as (
    select n.aluno_id,
           n.simulado_id,
           coalesce(qs.n_questoes, 0) as n_questoes,
           coalesce(ra.n_brancos, 0)  as n_brancos
    from nota n
    left join questoes_por_simulado qs on qs.simulado_id = n.simulado_id
    left join respostas_do_aluno ra
           on ra.aluno_id = n.aluno_id and ra.simulado_id = n.simulado_id
    where n.presente and n.pontuacao = 0
)
select
    count(*)                                                              as zeros_total,
    count(*) filter (where n_questoes = 0)                                as sem_dado_de_questao,
    count(*) filter (where n_questoes > 0 and n_brancos = n_questoes)     as todo_em_branco,
    count(*) filter (where n_questoes > 0 and n_brancos = 0)              as respondeu_tudo,
    count(*) filter (where n_questoes > 0
                       and n_brancos > 0
                       and n_brancos < n_questoes)                        as parcial
from zeros;

\echo ''
\echo '════ 5 · O sinal é forte? Comparação com quem tirou mais que zero ════'
\echo '(dev: 0,003 entre notas > 0 contra 0,389 entre os zeros — 130x)'
\echo ''

with questoes_por_simulado as (
    select simulado_id, count(*) as n_questoes
    from questao
    group by 1
),
respostas_do_aluno as (
    select r.aluno_id,
           q.simulado_id,
           count(*) filter (where r.alternativa_id is null) as n_brancos
    from questao_resposta_aluno r
    join questao q on q.id = r.questao_id
    group by 1, 2
)
select
    case when n.pontuacao = 0 then 'zero' else 'nota > 0' end             as faixa,
    count(*)                                                              as notas,
    round(avg(coalesce(ra.n_brancos, 0)::numeric / qs.n_questoes), 4)     as fracao_media_em_branco
from nota n
join questoes_por_simulado qs on qs.simulado_id = n.simulado_id
left join respostas_do_aluno ra
       on ra.aluno_id = n.aluno_id and ra.simulado_id = n.simulado_id
where n.presente
group by 1
order by 1;

\echo ''
\echo '════ 6 · A regra que JÁ RODA no ingest, conferida contra a evidência ════'
\echo '"zero em 2+ provas do mesmo dia = faltou o dia inteiro" — ela apaga a'
\echo 'nota (pontuacao := null). Quantas vezes ela apagaria nota de quem'
\echo 'respondeu de verdade?   (dev: 29 confirmam, 8 contradizem = 22% de erro)'
\echo ''

with questoes_por_simulado as (
    select simulado_id, count(*) as n_questoes
    from questao
    group by 1
),
respostas_do_aluno as (
    select r.aluno_id,
           q.simulado_id,
           count(*) filter (where r.alternativa_id is null) as n_brancos
    from questao_resposta_aluno r
    join questao q on q.id = r.questao_id
    group by 1, 2
),
zeros as (
    select n.aluno_id,
           n.simulado_id,
           s.data_aplicacao,
           coalesce(qs.n_questoes, 0) as n_questoes,
           coalesce(ra.n_brancos, 0)  as n_brancos
    from nota n
    join simulado s on s.id = n.simulado_id
    left join questoes_por_simulado qs on qs.simulado_id = n.simulado_id
    left join respostas_do_aluno ra
           on ra.aluno_id = n.aluno_id and ra.simulado_id = n.simulado_id
    where n.presente and n.pontuacao = 0
),
zeros_por_dia as (
    select aluno_id, data_aplicacao, count(*) as zeros_no_dia
    from zeros
    group by 1, 2
)
select
    count(*)                                                            as celulas_que_a_regra_pega,
    count(*) filter (where z.n_questoes = 0)                            as sem_como_conferir,
    count(*) filter (where z.n_questoes > 0
                       and z.n_brancos = z.n_questoes)                  as evidencia_confirma,
    count(*) filter (where z.n_questoes > 0
                       and z.n_brancos < z.n_questoes)                  as evidencia_contradiz
from zeros z
join zeros_por_dia d
      on d.aluno_id = z.aluno_id and d.data_aplicacao = z.data_aplicacao
where d.zeros_no_dia >= 2;

\echo ''
\echo '════ 7 · Impacto na média — os 15 simulados mais afetados ════'
\echo 'Tirar os zeros "todo em branco" move a média quanto?'
\echo '(dev: entre +0,02 e +0,10. Se em produção for muito maior, a'
\echo ' coordenação precisa ser avisada antes, como na Sprint 5)'
\echo ''

with questoes_por_simulado as (
    select simulado_id, count(*) as n_questoes
    from questao
    group by 1
),
respostas_do_aluno as (
    select r.aluno_id,
           q.simulado_id,
           count(*) filter (where r.alternativa_id is null) as n_brancos
    from questao_resposta_aluno r
    join questao q on q.id = r.questao_id
    group by 1, 2
),
marcadas as (
    select n.aluno_id,
           n.simulado_id,
           n.pontuacao,
           (n.pontuacao = 0
            and qs.n_questoes > 0
            and coalesce(ra.n_brancos, 0) = qs.n_questoes) as e_branco
    from nota n
    join questoes_por_simulado qs on qs.simulado_id = n.simulado_id
    left join respostas_do_aluno ra
           on ra.aluno_id = n.aluno_id and ra.simulado_id = n.simulado_id
    where n.presente
)
select s.nome,
       count(*) filter (where m.e_branco)                              as brancos,
       count(*)                                                        as presentes,
       round(avg(m.pontuacao)::numeric, 2)                             as media_hoje,
       round(avg(m.pontuacao) filter (where not m.e_branco)::numeric, 2) as media_sem_branco,
       round((avg(m.pontuacao) filter (where not m.e_branco)
              - avg(m.pontuacao))::numeric, 2)                         as delta
from marcadas m
join simulado s on s.id = m.simulado_id
group by s.id, s.nome
having count(*) filter (where m.e_branco) > 0
order by delta desc
limit 15;

\echo ''
\echo '════ 8 · Concentração — algum simulado domina a contagem? ════'
\echo '(dev: 4_P14 Química sozinho tinha 166 dos 586 zeros — prova brutal,'
\echo ' não bug. Mas ela distorce qualquer estatística sobre "zeros")'
\echo ''

select s.nome,
       s.tipo,
       s.data_aplicacao,
       count(*) filter (where n.presente and n.pontuacao = 0) as zeros,
       count(*) filter (where n.presente)                     as presentes,
       round(avg(n.pontuacao) filter (where n.presente)::numeric, 2) as media
from nota n
join simulado s on s.id = n.simulado_id
group by s.id, s.nome, s.tipo, s.data_aplicacao
having count(*) filter (where n.presente and n.pontuacao = 0) > 0
order by zeros desc
limit 12;

\echo ''
\echo '════ 9 · Duas conferências avulsas do plano ════'
\echo 'a) O coordenador já editou alguma nota? (docs/32 §2.2 — se sim, o'
\echo '   conserto de `presente` deixa de ser preventivo)'
\echo 'b) Simulados com nota_maxima = 0 (docs/32 §8 — o fallback de 10,0'
\echo '   salva hoje, mas quebra numa prova de 15 pontos)'
\echo ''

select
    (select count(*) from nota where pontuacao_sas is not null)     as notas_editadas_pelo_sas,
    (select count(*) from nota where editada_em is not null)        as com_marca_de_edicao,
    (select count(*) from simulado where nota_maxima = 0)           as simulados_sem_nota_maxima,
    (select count(*) from simulado where nota_maxima = 0
        and exists (select 1 from nota n2
                    where n2.simulado_id = simulado.id
                      and n2.pontuacao > 10))                       as desses_com_nota_acima_de_10,
    (select count(*) from upload)                                   as uploads_de_planilha;

\echo ''
\echo '════ fim ════'
\echo ''
