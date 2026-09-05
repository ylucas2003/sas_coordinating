-- Reverte a 0045.
--
-- DESTRUTIVO no sentido que importa: apaga QUEM é administrador. Voltar a
-- subir a 0045 devolve todo mundo para 'coordenador' (o default), e a
-- promoção precisa ser refeita à mão.
--
-- ⚠️ NÃO DESÇA SÓ ESTA MIGRATION. O código de 04/09 em diante PEDE a coluna
-- ao PostgREST, e coluna ausente não é campo nulo: o PostgREST recusa o SELECT
-- inteiro com 400 `42703` e o cliente levanta APIError. Ordem obrigatória:
-- primeiro a API volta para a versão anterior à 0045 (que não conhece `papel`),
-- só então este `down`. O caminho inverso deixa telas quebradas.
--
--   * `/auth/login` sobrevive — e é o único que sobrevive por desenho:
--     `app/routes/auth.py` (`_buscar_conta`) refaz o SELECT sem `papel` quando
--     vê o 42703, e todo mundo entra como coordenador;
--   * `GET /administracao/coordenadores` (a tela de contas) e
--     `scripts/criar_coordenador.py` (`--listar` e a gravação) pedem `papel`
--     sem alternativa — 42703, que chega ao coordenador como erro na tela.
--
-- E o efeito no acesso é o CONTRÁRIO de "não tranca ninguém": sem a coluna
-- ninguém volta a logar como administrador, então `PATCH /notas/{aluno}/{simulado}`
-- e as três rotas de conta passam a devolver 403 para a casa inteira. Quem já
-- estiver logado como administrador continua passando até o token expirar
-- (8 h): `papel_da_sessao` lê o claim do token, não o banco.

BEGIN;

ALTER TABLE usuario_coordenacao DROP COLUMN IF EXISTS papel;

COMMIT;
