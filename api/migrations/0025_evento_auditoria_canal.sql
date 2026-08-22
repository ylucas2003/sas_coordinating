-- Compartimenta a trilha de auditoria por canal (docs/18 §3.2).
--
-- A coordenação pediu "um grupo de logs só de sincronização" para reconstruir
-- na linha do tempo o que foi alterado. É uma COLUNA, e não uma tabela nova
-- nem um prefixo em `acao`, porque:
--   * tabela separada obriga UNION para responder "o que aconteceu naquela
--     tarde?" — que é a única pergunta que interessa e cruza canais;
--   * prefixo em texto compartimenta por convenção, e some do filtro no dia
--     em que alguém escrever `canvas_nota_enviada` em vez de `canvas.nota`;
--   * coluna é indexável, filtrável na tela, e permite retenção diferente
--     por canal — relevante porque são dados de menores (LGPD art. 37).

BEGIN;

ALTER TABLE evento_auditoria
    ADD COLUMN IF NOT EXISTS canal text;

-- Os eventos que já existem são todos de acesso.
UPDATE evento_auditoria SET canal = 'acesso'
 WHERE canal IS NULL AND acao IN ('login_ok', 'login_falhou', 'primeiro_acesso_bloqueado');

CREATE INDEX IF NOT EXISTS idx_evento_auditoria_canal
    ON evento_auditoria (canal, ocorrido_em DESC);

COMMENT ON COLUMN evento_auditoria.canal IS 'acesso | nota | simulado | ciclo | canvas. Filtro da linha do tempo; permite retenção por canal.';
COMMENT ON COLUMN evento_auditoria.acao  IS 'login_ok, login_falhou, primeiro_acesso_bloqueado, nota_editada, simulado_criado, simulado_editado, simulado_removido, ciclo_criado, enviado_ao_canvas, acesso_resetado, …';

COMMIT;
