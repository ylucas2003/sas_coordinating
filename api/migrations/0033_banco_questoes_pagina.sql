-- Modo página para o acervo histórico do banco de questões (docs/24).
--
-- O recorte fino da questão (heurística de bbox, sem coordenada persistida)
-- provou-se frágil no acervo histórico — "Bug D", docs/23 §12.1: crops vazios
-- (3-10px de altura) ou que capturam a questão vizinha (página inteira em
-- duas colunas). E a transcrição de texto que serve de exibição alternativa
-- gerou dez rodadas de correção (docs/23 §10-20: espaço espúrio, fonte Symbol
-- remapeada, conteúdo perdido, questões fundidas) e AINDA ASSIM reapareceu em
-- produção — a causa é estrutural, não um bug pontual.
--
-- Decisão: para o acervo histórico, a imagem deixa de ser um recorte fino e
-- passa a ser a PÁGINA INTEIRA do PDF onde a questão está (1 ou 2, compostas
-- verticalmente quando a questão atravessa a virada de página) — a prova
-- real, sem risco de exibir algo malformado. `extraido_por = 'pagina'` marca
-- esse modo, terceiro valor ao lado de 'pipeline' (recorte fino) e 'visao'
-- (piloto 1973, texto por IA é o principal). O enunciado_md das questões já
-- transcritas NÃO é apagado — só deixa de ser a fonte de exibição.
--
-- A segunda parte desta migration existe por causa do lote de ingestão nova
-- (lotes C/D, docs/24): esses PDFs nunca vão ganhar transcrição — é
-- exatamente o ponto da decisão ("não precisamos transcrever o enunciado").
-- `enunciado_md NOT NULL` (0028) quebraria a importação dessas questões, e
-- por isso relaxa, mas só quando `extraido_por = 'pagina'` — todo o resto do
-- acervo (pipeline/visao) continua exigindo texto, sem abrir brecha geral.

BEGIN;

ALTER TABLE questao_vestibular
    DROP CONSTRAINT questao_vestibular_extraido_por_check;

ALTER TABLE questao_vestibular
    ADD CONSTRAINT questao_vestibular_extraido_por_check
        CHECK (extraido_por IN ('pipeline', 'visao', 'pagina'));

ALTER TABLE questao_vestibular
    ALTER COLUMN enunciado_md DROP NOT NULL;

ALTER TABLE questao_vestibular
    ADD CONSTRAINT questao_vestibular_enunciado_presente
        CHECK (enunciado_md IS NOT NULL OR extraido_por = 'pagina');

COMMENT ON COLUMN questao_vestibular.extraido_por IS
  '''pipeline'' = PDF nativo, recorte fino da questão; ''visao'' = página '
  'escaneada lida como imagem porque o OCR não dá conta de prova '
  'datilografada (piloto 1973); ''pagina'' = a imagem é a PÁGINA INTEIRA do '
  'PDF onde a questão está (1 ou 2 páginas compostas verticalmente), sem '
  'recorte fino nem transcrição — usado no acervo histórico (docs/24) onde o '
  'recorte por heurística de bbox provou frágil (docs/23 §12.1) e a '
  'transcrição gerava bug atrás de bug (docs/23 §10-20). enunciado_md pode '
  'ser NULL só neste modo (CHECK abaixo).';
COMMENT ON COLUMN questao_vestibular.enunciado_md IS
  'Texto do enunciado. NULL só é permitido quando extraido_por = ''pagina'' '
  '— questão ingerida sem transcrição, exibida só pela imagem da página '
  '(docs/24). Em todo outro modo continua obrigatório.';

COMMIT;
