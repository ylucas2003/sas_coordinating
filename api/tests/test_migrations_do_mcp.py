"""As migrations do MCP da coordenação, conferidas sem banco (docs/43 §5.2).

A prova de verdade é contra o Postgres — `scripts/verificar_papeis_do_mcp.py`,
rodado depois de toda migration que mexa na lista branca. Estes testes pegam,
no PR, o que não precisa de banco para ser pego: o par `.down`, tabela ou
coluna sensível entrando na lista branca, concessão aos papéis do MCP (ou a
PUBLIC, de quem o sas_mcp herda) fora das formas permitidas, DEFAULT
PRIVILEGES, função SECURITY DEFINER ou com SQL dinâmico que o sas_mcp
executaria, o gatilho que confina o MCP à própria trilha, o login PRÓPRIO do
postgrest_mcp (membro só do sas_mcp, sem senha no arquivo) e o compose que
deixaria o MCP fora do papel restrito ou de volta ao login da API.

A lista branca e a auditoria são as MESMAS do verificador
(`verificar_papeis_do_mcp.lista_branca` e `auditar_migrations`): o arquivo diz
o que o banco tem de ser, o script confere o banco, e aqui se confere o
arquivo. A auditoria é a parte que falha fechado — na revisão de 24/10, 14 de
17 concessões perigosas passavam por estes testes porque o leitor só via a
forma exata `GRANT SELECT … TO sas_leitura` e ignorava o resto; os casos de
`MUTACOES` abaixo são essas 17 e mais as que a revisão abriu.
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.chat.tools.trilha import ACOES_FORA_DA_TRILHA, CANAIS_DA_TRILHA, DETALHE_POR_ACAO
from app.mcp.dados import TABELA_DA_SONDA
from scripts.verificar_papeis_do_mcp import (
    ACOES_FORA_DA_TRILHA_NA_VIEW,
    CANAIS_DA_TRILHA_NA_VIEW,
    COLUNAS_DA_TRILHA,
    COLUNAS_PROIBIDAS_DA_CAPTACAO,
    COLUNAS_PROIBIDAS_DO_ALUNO,
    COLUNAS_PROIBIDAS_POR_TABELA,
    LOGIN_DO_MCP,
    PAPEIS_DO_MCP,
    PREFIXOS_PROIBIDOS,
    TABELAS_PROIBIDAS,
    VIEWS_DA_LISTA_BRANCA,
    VIEWS_DO_MCP,
    _auditar_view,
    _chaves_sensiveis,
    _comandos,
    _evento,
    _julgar,
    _separar,
    _views,
    auditar_funcoes,
    auditar_migrations,
    lista_branca,
    tabela_proibida,
)
from tests.test_mcp_tokens import ACOES_DO_SAS_MCP, gatilho_da_0072_aceita

DIR_API = Path(__file__).resolve().parent.parent
DIR_MIGRATIONS = DIR_API / "migrations"
RAIZ = DIR_API.parent
DIR_INIT = RAIZ / "infra" / "postgres" / "init"
_PADRAO_UP = re.compile(r"^(\d{4})_[a-z0-9_]+\.sql$")


def _ups() -> list[Path]:
    return sorted(p for p in DIR_MIGRATIONS.iterdir() if _PADRAO_UP.match(p.name))


def _comandos_de(*caminhos: Path) -> list[str]:
    return [c for p in caminhos for c in _comandos(p.read_text(encoding="utf-8"))]


def _todos_os_comandos() -> list[str]:
    return _comandos_de(*_ups())


def _arquivo(prefixo: str) -> Path:
    achados = [p for p in _ups() if p.name.startswith(prefixo)]
    assert len(achados) == 1, f"esperava uma migration {prefixo}, achei {achados}"
    return achados[0]


# ─── O par .down ─────────────────────────────────────────────────────────


def test_toda_migration_tem_down():
    # O runner aceita migration sem .down e só avisa (scripts/migrate.py); o
    # par é regra do projeto (CLAUDE.md) e é o que torna a 0071 reversível.
    sem_down = [p.name for p in _ups() if not p.with_name(p.name.replace(".sql", ".down.sql")).exists()]
    assert sem_down == []


def test_as_migrations_do_mcp_existem_com_down():
    for prefixo in ("0071_", "0072_", "0073_", "0074_", "0075_", "0076_", "0077_"):
        up = _arquivo(prefixo)
        assert up.with_name(up.name.replace(".sql", ".down.sql")).exists()


# ─── A lista branca ──────────────────────────────────────────────────────


def test_lista_branca_nao_tem_tabela_sensivel():
    branca = lista_branca(DIR_MIGRATIONS)
    assert branca, "nenhum GRANT SELECT ao sas_leitura — a 0071 sumiu?"
    assert set(branca) & set(TABELAS_PROIBIDAS) == set()
    assert [t for t in branca if tabela_proibida(t)] == []


def test_aluno_so_por_coluna_e_sem_as_proibidas():
    colunas = lista_branca(DIR_MIGRATIONS).get("aluno")
    assert colunas is not None, "aluno tem de ir por coluna, nunca a tabela inteira"
    assert colunas & set(COLUNAS_PROIBIDAS_DO_ALUNO) == set()
    # O mínimo que as tools e o pseudonimizador do MCP leem.
    assert {"id", "matricula", "nome", "ativo"} <= colunas


def test_toda_tabela_da_lista_vai_por_coluna():
    # Coluna nova nasce invisível ao MCP, como tabela nova (0071): um GRANT na
    # tabela inteira abriria amanhã o que for acrescentado a ela.
    inteiras = [t for t, colunas in lista_branca(DIR_MIGRATIONS).items() if colunas is None]
    assert inteiras == []


def test_colunas_de_bastidor_ficam_fora():
    branca = lista_branca(DIR_MIGRATIONS)
    fora = {
        # As duas origens da pontuação e o estado do Canvas entraram em 30/10,
        # com `pendencias_canvas_do_ciclo` no MCP (0074). Quem lançou, não.
        "nota": {"editada_por", "grader_canvas_user_id"},
        "matricula_turma": {"last_activity_at", "last_attended_at", "canvas_enrollment_id"},
        "questao_resposta_aluno": {"aluno_id", "alternativa_id"},
        "simulado": {"arquivo_storage_path", "motivo_zero_e_ausencia"},
        "ciclo": {"canvas_assignment_group_id"},
        # `criado_por` saiu daqui em 30/10 (0077): é a coluna "Quem" da tela de
        # Calibração, e `calibracao_da_importancia` a lê. O `id` continua fora.
        "parametro_importancia": {"id"},
        "questao_vestibular": {"fonte_pdf", "arquivo_origem", "classificado_por"},
        # Entrou em 26/10 (listar_alertas, com o nome liberado): só o que a tool lê.
        "alerta": {"dados_brutos", "hash_dedup", "resolvido_em"},
        # A cantina (0075): sem a conta que lançou e sem carimbo de bastidor.
        "cantina": {"criado_em"},
        "cardapio": {"criado_por", "criado_em", "atualizado_em"},
        "pedido_refeicao": {"atualizado_em"},
        # A captação (0076): gente de fora, só o que a tela mostra. `observacoes`
        # é o texto livre do funil, onde um telefone anotado à mão apareceria.
        "candidato_externo": {"observacoes", "retrato_editado_a_mao", "atualizado_em"},
        "conquista_externa": {"nome_informado", "raspado_em", "serie_referencia_min", "serie_referencia_max"},
        "prova_externa": {"abrangencia", "fonte_resultado"},
        # A 0074: `disparo` só se conta, e o resto é e-mail, corpo e nome.
        "disparo": {"destinatario", "assunto", "corpo", "contexto", "erro", "regra_lembrete_id"},
        "evento_agenda": {"criado_por"},
        "curso_monitorado_gravacao": {"professor_padrao", "canvas_modulo_id", "canvas_modulo_generico_id"},
        "trilha_de_alteracoes": {"ip", "request_id"},
        "nome_da_coordenacao": {"email", "senha_hash", "papel", "foto_perfil_storage"},
        "aula_gravacao_para_ia": {
            "canvas_pagina_slug", "s3_bucket", "s3_chave_composto", "conferencia_id",
        },
    }
    for tabela, colunas in fora.items():
        assert tabela in branca, tabela
        assert branca[tabela] & colunas == set(), tabela


def test_sas_mcp_nao_recebe_select_direto():
    # O que o sas_mcp lê vem do sas_leitura, e só de lá: a lista branca é uma.
    assert lista_branca(DIR_MIGRATIONS, papel="sas_mcp") == {}
    # E o login nem isso: é NOINHERIT, e não lê nada por si (0071).
    assert lista_branca(DIR_MIGRATIONS, papel=LOGIN_DO_MCP) == {}


# ─── A 0075: a cantina ───────────────────────────────────────────────────


def test_a_cantina_entra_sem_a_conta_de_acesso_nem_as_views():
    branca = lista_branca(DIR_MIGRATIONS)
    # A conta segue proibida pelo nome e pelo prefixo: é ela que guarda e-mail,
    # último login e senha_hash (0047).
    assert "usuario_cantina" in TABELAS_PROIBIDAS and "usuario_cantina".startswith(PREFIXOS_PROIBIDOS)
    assert "usuario_cantina" not in branca
    # View roda com o privilégio do dono: o MCP faz a conta nas tabelas (0071).
    assert {"v_pedidos_por_cardapio", "v_contagem_pedidos_por_opcao"} & set(branca) == set()


def test_a_restricao_alimentar_entra_so_pela_0075_e_em_grant_proprio():
    # Dado de saúde de menor (LGPD art. 11): ela sai sozinha por um REVOKE, sem
    # desfazer o resto, e nenhum outro GRANT a arrasta junto.
    com_ela = [c for c in _todos_os_comandos() if c.startswith("GRANT") and "restricao_alimentar" in c]
    assert com_ela == ["GRANT SELECT (restricao_alimentar) ON aluno TO sas_leitura"]
    assert "GRANT SELECT (restricao_alimentar) ON aluno TO sas_leitura" in _comandos_de(_arquivo("0075_"))


def test_o_comment_da_coluna_deixa_de_dizer_em_lugar_nenhum_mais():
    texto = " ".join(_arquivo("0075_").read_text(encoding="utf-8").split())
    assert "restricoes_alimentares, e só nela" in texto
    assert "LGPD art. 11" in texto


def test_o_down_da_0075_devolve_cada_grant_e_o_comment_da_0049():
    up = _arquivo("0075_")
    down = up.with_name(up.name.replace(".sql", ".down.sql"))
    # O que a 0075 concede: (tabela, colunas), lido do GRANT.
    concedido = {}
    for c in _comandos_de(up):
        m = re.fullmatch(r"GRANT SELECT \((?P<colunas>[^)]+)\) ON (?P<tabela>\w+) TO sas_leitura", c)
        if m:
            concedido[m["tabela"]] = {x.strip() for x in m["colunas"].split(",")}
    revogado = {}
    for c in _comandos_de(down):
        m = re.fullmatch(r"REVOKE SELECT \((?P<colunas>[^)]+)\) ON (?P<tabela>\w+) FROM sas_leitura", c)
        if m:
            revogado[m["tabela"]] = {x.strip() for x in m["colunas"].split(",")}
    assert concedido and revogado == concedido
    # Por coluna: em `aluno`, o que a 0071 deu continua valendo depois do down.
    assert revogado["aluno"] == {"restricao_alimentar"}
    texto_0049 = next(p for p in _ups() if p.name.startswith("0049_")).read_text(encoding="utf-8")
    trecho = "e em lugar nenhum mais — não entra em ficha, painel, dossiê nem chat (docs/38 §2.6)."
    assert trecho in texto_0049 and trecho in down.read_text(encoding="utf-8")


def test_a_chave_de_saude_segue_sensivel_para_toda_tool_menos_a_dela():
    # O GRANT é do papel, e não da tool: tirar a coluna de
    # COLUNAS_PROIBIDAS_DO_ALUNO não pode desligar o vigia das outras 37.
    resultado = {"alunos": [{"nome": "x", "restricaoAlimentar": "y"}]}

    class Registro:
        def __init__(self):
            self.falhas: list[str] = []
            self.oks: list[str] = []

        def falha(self, texto):
            self.falhas.append(texto)

        def ok(self, texto):
            self.oks.append(texto)

    outra = Registro()
    _julgar(outra, "pedidos_da_refeicao", resultado, [], [], ferramenta="pedidos_da_refeicao")
    assert len(outra.falhas) == 1 and "alunos[0].restricaoAlimentar" in outra.falhas[0]
    sem_nome = Registro()
    _julgar(sem_nome, "qualquer", resultado, [], [])
    assert len(sem_nome.falhas) == 1

    a_dela = Registro()
    _julgar(a_dela, "restricoes_alimentares", resultado, [], [], ferramenta="restricoes_alimentares")
    assert a_dela.falhas == [] and len(a_dela.oks) == 1


def test_a_excecao_da_tool_de_saude_nao_abre_as_outras_chaves():
    assert _chaves_sensiveis({"senha_hash": "x", "restricao_alimentar": "y"}, permitidas=frozenset({"restricaoalimentar"})) == [
        "senha_hash"
    ]


def test_as_tabelas_da_cantina_nao_sao_mais_proibidas():
    # O que mudou em 30/10, e só isso: sem esta conferência, um prefixo esquecido
    # reprovaria a 0075, e um removido a mais abriria outra coisa.
    for tabela in ("cantina", "cardapio", "cardapio_bloco", "cardapio_opcao",
                   "direito_refeicao_aluno", "pedido_refeicao", "pedido_refeicao_item"):
        assert tabela not in TABELAS_PROIBIDAS and not tabela.startswith(PREFIXOS_PROIBIDOS), tabela
    assert "oauth_pedido_mcp" in TABELAS_PROIBIDAS and "oauth_pedido_mcp".startswith(PREFIXOS_PROIBIDOS)


# ─── As views das listas (0077) ──────────────────────────────────────────


def _corpo_da_view_das_listas(nome: str) -> str:
    """O CREATE VIEW da 0077, sem comentário e com o espaço normalizado, mas com
    os literais: o `_comandos` os esvazia, e aqui o literal é o que importa."""
    texto = re.sub(r"--[^\n]*", "", _arquivo("0077_").read_text(encoding="utf-8"))
    (corpo,) = re.findall(rf"CREATE VIEW {nome}\b.*?;", texto, re.S)
    return " ".join(corpo.split())


def test_as_views_das_listas_trazem_so_o_lado_da_coordenacao():
    """O WHERE é o que segura a linha, e nem coluna nem GRANT o denunciam: uma view
    mais larga passaria por todo o resto desta suíte. Por isso o corpo vai inteiro."""
    assert _corpo_da_view_das_listas("lista_questoes_da_coordenacao") == (
        "CREATE VIEW lista_questoes_da_coordenacao WITH (security_barrier = true) AS "
        "SELECT l.id, l.titulo, l.dono_tipo, l.dono_id, l.criada_em, l.atualizada_em "
        "FROM lista_questoes AS l WHERE l.dono_tipo = 'coordenacao';"
    )
    assert _corpo_da_view_das_listas("lista_questoes_item_da_coordenacao") == (
        "CREATE VIEW lista_questoes_item_da_coordenacao WITH (security_barrier = true) AS "
        "SELECT i.lista_id, i.questao_id, i.posicao FROM lista_questoes_item AS i "
        "WHERE i.lista_id IN (SELECT l.id FROM lista_questoes AS l WHERE l.dono_tipo = 'coordenacao');"
    )


def test_as_views_das_listas_rodam_como_o_dono():
    """O sas_mcp não tem acesso às tabelas: com `security_invoker`, a view voltaria
    42501 em toda leitura. É o oposto das views da captação, e é de propósito."""
    for nome in VIEWS_DO_MCP:
        if nome.startswith("lista_questoes"):
            assert "security_invoker" not in _corpo_da_view_das_listas(nome)


def test_o_mcp_le_a_view_e_a_tabela_de_baixo_continua_proibida():
    branca = lista_branca(DIR_MIGRATIONS)
    for tabela in ("lista_questoes", "lista_questoes_item"):
        assert tabela in TABELAS_PROIBIDAS and tabela not in branca
    assert branca["lista_questoes_da_coordenacao"] == {
        "id", "titulo", "dono_tipo", "dono_id", "criada_em", "atualizada_em",
    }
    assert branca["lista_questoes_item_da_coordenacao"] == {"lista_id", "questao_id", "posicao"}


def test_as_views_do_mcp_nao_caem_na_regra_do_prefixo():
    """Sem `v_` de propósito: a trava do prefixo segue valendo para toda outra view."""
    for nome in VIEWS_DO_MCP:
        assert nome not in TABELAS_PROIBIDAS and not nome.startswith(PREFIXOS_PROIBIDOS)


@pytest.mark.parametrize(
    "comando",
    [
        # `CREATE OR REPLACE` sem o WITH zera as opções: a barreira sai calada.
        "CREATE OR REPLACE VIEW lista_questoes_da_coordenacao AS SELECT 1",
        "CREATE VIEW lista_questoes_item_da_coordenacao AS SELECT 1",
        "ALTER VIEW lista_questoes_da_coordenacao RESET (security_barrier)",
        "ALTER TABLE lista_questoes_item_da_coordenacao OWNER TO postgres",
    ],
)
def test_nem_migration_do_mcp_tira_a_barreira(comando):
    assert _auditar_view(comando, do_mcp=True)


def test_a_view_da_lista_recriada_com_a_barreira_passa_na_migration_do_mcp():
    comando = "CREATE OR REPLACE VIEW lista_questoes_da_coordenacao WITH (security_barrier = true) AS SELECT 1"
    assert _auditar_view(comando, do_mcp=True) == []


# ─── A auditoria: o que o leitor não entende falha ───────────────────────


def test_migrations_so_concedem_de_forma_permitida():
    # Vazia = toda concessão que toca sas_leitura, sas_mcp ou PUBLIC — nos
    # ups, nos downs e no init dos papéis — é de uma forma que a lista
    # branca, o verificador e estes testes entendem.
    assert auditar_migrations(DIR_MIGRATIONS, DIR_INIT) == []


#: Cada uma, sozinha numa 0099 nova, tem de virar problema. Estão aqui as 17
#: mutações da revisão de 24/10 (a 18ª de lá era o controle sem mutação), das
#: quais os testes de antes só pegavam três: SELECT direto numa tabela
#: proibida, `pg_read_all_data` e SELECT direto ao sas_mcp.
MUTACOES: dict[str, str] = {
    "select_em_tabela_proibida": "GRANT SELECT ON usuario_coordenacao TO sas_leitura;",
    # Na forma EXATA das linhas da lista branca — a mutação mais provável é
    # alguém copiar uma delas e trocar a tabela ou a coluna.
    "select_por_coluna_em_tabela_proibida": "GRANT SELECT (email, senha_hash) ON usuario_coordenacao TO sas_leitura;",
    "coluna_proibida_do_aluno": "GRANT SELECT (senha_hash) ON aluno TO sas_leitura;",
    "conversa_por_coluna": "GRANT SELECT (conteudo) ON chat_mensagem TO sas_leitura;",
    "update_em_nota": "GRANT UPDATE ON nota TO sas_leitura;",
    "delete_em_nota": "GRANT DELETE ON nota TO sas_leitura;",
    "sas_service_dentro_do_sas_leitura": "GRANT sas_service TO sas_leitura;",
    "all_em_usuario_coordenacao": "GRANT ALL ON usuario_coordenacao TO sas_leitura;",
    "select_e_insert_em_chat": "GRANT SELECT, INSERT ON chat_mensagem TO sas_leitura;",
    "duas_tabelas_num_grant": "GRANT SELECT ON chat_mensagem, usuario_coordenacao TO sas_leitura;",
    "email_e_update_no_aluno": "GRANT SELECT (email), UPDATE (nome) ON aluno TO sas_leitura;",
    "nomes_entre_aspas": 'GRANT SELECT ON TABLE public."chat_mensagem" TO "sas_leitura";',
    "execute_da_definer_ao_sas_leitura": (
        "GRANT EXECUTE ON FUNCTION atualizar_v_candidato_externo_por_nome() TO sas_leitura;"
    ),
    "login_com_senha": "ALTER ROLE sas_mcp LOGIN PASSWORD 'x';",
    "superuser": "ALTER ROLE sas_leitura SUPERUSER;",
    "pg_read_all_data": "GRANT pg_read_all_data TO sas_leitura;",
    "select_direto_ao_sas_mcp": "GRANT SELECT ON usuario_coordenacao TO sas_mcp;",
    "select_a_public": "GRANT SELECT ON chat_mensagem TO PUBLIC;",
    "default_privileges_a_public": "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO PUBLIC;",
    "alter_function_vira_definer": (
        "ALTER FUNCTION buscar_candidatos_por_conquista(text[], text[], integer, integer, text[], "
        "integer, text, text, integer, text, integer, integer) SECURITY DEFINER;"
    ),
    # E as que a mesma revisão abriu, ou que o leitor novo tinha de cobrir:
    "grant_dentro_de_do": "DO $$ BEGIN GRANT UPDATE ON nota TO sas_leitura; END $$;",
    "grant_dinamico_em_do": (
        "DO $do$ BEGIN EXECUTE format('GRANT %s ON nota TO %I', 'UPDATE', 'sas_' || 'leitura'); END $do$;"
    ),
    "grant_por_concatenacao_em_do": (
        "DO $$ BEGIN EXECUTE 'GR' || 'ANT UPDATE ON nota TO sas_' || 'leitura'; END $$;"
    ),
    "comando_inteiro_no_porcento_s": (
        "DO $$ BEGIN EXECUTE format('%s ON nota TO %I', 'GR' || 'ANT UPDATE', 'sas_' || 'leitura'); END $$;"
    ),
    "comando_numa_variavel": (
        "DO $$ DECLARE v text := 'GR' || 'ANT UPDATE ON nota TO sas_' || 'leitura'; BEGIN EXECUTE v; END $$;"
    ),
    "apostrofo_em_comentario": "-- it's a trap\nGRANT UPDATE ON nota TO sas_leitura;\nCOMMENT ON TABLE nota IS 'x';",
    "select_numa_view": "GRANT SELECT (aluno_id) ON v_nota_dimensoes TO sas_leitura;",
    # A captação (0076): a liberação é pelo NOME e por coluna, não pelo prefixo.
    "observacoes_do_funil": "GRANT SELECT (observacoes) ON candidato_externo TO sas_leitura;",
    "nome_como_a_fonte_escreveu": "GRANT SELECT (nome_informado) ON conquista_externa TO sas_leitura;",
    "view_do_perfil_que_cita_observacoes": "GRANT SELECT (id) ON v_candidato_externo TO sas_leitura;",
    "tabela_nova_da_captacao": "GRANT SELECT (telefone) ON candidato_externo_contato TO sas_leitura;",
    "tabela_inteira_da_captacao": "GRANT SELECT ON candidato_externo TO sas_leitura;",
    "select_na_tabela_inteira": "GRANT SELECT ON materia TO sas_leitura;",
    "with_grant_option": "GRANT SELECT (nome) ON aluno TO sas_leitura WITH GRANT OPTION;",
    "dono_da_tabela": "ALTER TABLE nota OWNER TO sas_mcp;",
    "sas_mcp_dentro_de_outro_papel": "CREATE ROLE intruso NOLOGIN ROLE sas_mcp;",
    "sas_leitura_ao_authenticator": "GRANT sas_leitura TO authenticator;",
    "insert_no_id_da_trilha": "GRANT INSERT (id) ON evento_auditoria TO sas_mcp;",
    "definer_nova_sem_revoke": (
        "CREATE FUNCTION abre_tudo() RETURNS void LANGUAGE sql SECURITY DEFINER AS $$ SELECT 1 $$;"
    ),
    "definer_recriada": (
        "DROP FUNCTION atualizar_v_candidato_externo_por_nome();\n"
        "CREATE FUNCTION atualizar_v_candidato_externo_por_nome() RETURNS void LANGUAGE sql "
        "SECURITY DEFINER AS $$ SELECT 1 $$;"
    ),
    "sql_dinamico_que_o_mcp_executa": (
        "CREATE FUNCTION roda(p text) RETURNS void LANGUAGE plpgsql AS $$ BEGIN EXECUTE p; END $$;"
    ),
    "funcao_que_troca_de_papel": (
        "CREATE FUNCTION vira_api() RETURNS void LANGUAGE sql SET role = 'sas_service' AS $$ SELECT 1 $$;"
    ),
    "set_role_no_corpo": (
        "CREATE FUNCTION vira_api() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN SET ROLE sas_service; "
        "RETURN NEW; END $$;"
    ),
    "revoke_que_o_leitor_nao_modela": "REVOKE SELECT ON aluno, nota FROM sas_leitura;",
    # O login próprio do postgrest_mcp (0071) e o que o desfaria: voltar a
    # alcançar o sas_service, herdar, senha no git, config do PostgREST ou
    # papel de entrada gravados no login, e os dois tetos desligados.
    "login_membro_do_sas_service": "GRANT sas_service TO autenticador_mcp;",
    "authenticator_de_volta_ao_sas_mcp": "GRANT sas_mcp TO authenticator;",
    "login_herda_o_sas_mcp": "GRANT sas_mcp TO autenticador_mcp WITH INHERIT TRUE;",
    "login_com_admin_no_sas_mcp": "GRANT sas_mcp TO autenticador_mcp WITH ADMIN OPTION;",
    "login_com_senha_no_arquivo": "ALTER ROLE autenticador_mcp PASSWORD 'segredo';",
    "login_nasce_com_senha": "CREATE ROLE autenticador_mcp LOGIN PASSWORD 'segredo';",
    "login_herda_privilegio": "ALTER ROLE autenticador_mcp INHERIT;",
    "login_superusuario": "ALTER ROLE autenticador_mcp SUPERUSER;",
    "login_sem_teto_de_conexoes": "ALTER ROLE autenticador_mcp CONNECTION LIMIT -1;",
    "anon_role_no_papel_de_login": "ALTER ROLE autenticador_mcp SET pgrst.db_anon_role = 'sas_service';",
    "jwt_secret_no_papel_de_login": "ALTER ROLE autenticador_mcp SET pgrst.jwt_secret = 'x';",
    "login_ja_entra_como_sas_service": "ALTER ROLE autenticador_mcp SET role = 'sas_service';",
    "teto_de_duracao_desligado": "ALTER ROLE autenticador_mcp SET statement_timeout = '0';",
    "teto_de_duracao_acima_do_prazo": "ALTER ROLE autenticador_mcp SET statement_timeout = '10min';",
    "select_direto_ao_login": "GRANT SELECT (nome) ON aluno TO autenticador_mcp;",
    "login_ganha_o_sas_leitura": "GRANT sas_leitura TO autenticador_mcp;",
    # As tabelas e as views que a 0074 abriu: coluna proibida em tabela aberta,
    # a tabela de baixo pela porta da frente, e a view do MCP mexida fora dele.
    "email_do_destinatario": "GRANT SELECT (destinatario) ON disparo TO sas_leitura;",
    "corpo_do_lembrete": "GRANT SELECT (corpo, contexto) ON disparo TO sas_leitura;",
    "quem_agendou": "GRANT SELECT (criado_por) ON evento_agenda TO sas_leitura;",
    "trilha_pela_tabela": "GRANT SELECT (ip, detalhe) ON evento_auditoria TO sas_leitura;",
    "aula_pela_tabela": "GRANT SELECT (youtube_video_id) ON aula_gravacao TO sas_leitura;",
    "nome_pela_tabela": "GRANT SELECT (id, nome) ON usuario_coordenacao TO sas_leitura;",
    "view_do_mcp_alargada_fora_dele": (
        "CREATE OR REPLACE VIEW trilha_de_alteracoes WITH (security_barrier = true) AS "
        "SELECT * FROM evento_auditoria;"
    ),
    "view_do_mcp_derrubada_fora_dele": "DROP VIEW nome_da_coordenacao;",
    "view_do_mcp_perde_a_barreira": "ALTER VIEW trilha_de_alteracoes RESET (security_barrier);",
    "view_do_mcp_troca_de_dono": "ALTER TABLE aula_gravacao_para_ia OWNER TO sas_service;",
    # As views das listas (0077): a tabela de baixo pela porta da frente, a view
    # mexida fora de uma migration do MCP, e outra view tentando entrar igual.
    "lista_de_aluno_pela_tabela": "GRANT SELECT (titulo) ON lista_questoes TO sas_leitura;",
    "itens_de_aluno_pela_tabela": "GRANT SELECT (questao_id) ON lista_questoes_item TO sas_leitura;",
    "view_das_listas_alargada_fora_do_mcp": (
        "CREATE OR REPLACE VIEW lista_questoes_da_coordenacao WITH (security_barrier = true) AS "
        "SELECT id FROM lista_questoes;"
    ),
    "view_das_listas_derrubada_fora_do_mcp": "DROP VIEW lista_questoes_item_da_coordenacao;",
    "view_das_listas_perde_a_barreira": "ALTER VIEW lista_questoes_da_coordenacao RESET (security_barrier);",
    "view_das_listas_vira_invoker": "ALTER VIEW lista_questoes_da_coordenacao SET (security_invoker = true);",
    "view_das_listas_troca_de_dono": "ALTER TABLE lista_questoes_item_da_coordenacao OWNER TO sas_service;",
    "outra_view_na_lista_branca": (
        "CREATE VIEW outra_lista AS SELECT 1 AS a;\nGRANT SELECT (a) ON outra_lista TO sas_leitura;"
    ),
}


def _migrations_com(tmp_path: Path, up: str = "-- nada\n", down: str = "-- nada\n") -> Path:
    destino = tmp_path / "migrations"
    shutil.copytree(DIR_MIGRATIONS, destino)
    (destino / "0099_mutante.sql").write_text(f"BEGIN;\n{up}\nCOMMIT;\n", encoding="utf-8")
    (destino / "0099_mutante.down.sql").write_text(f"BEGIN;\n{down}\nCOMMIT;\n", encoding="utf-8")
    return destino


@pytest.mark.parametrize("mutacao", sorted(MUTACOES))
def test_auditoria_recusa_concessao_perigosa(tmp_path, mutacao):
    problemas = auditar_migrations(_migrations_com(tmp_path, up=MUTACOES[mutacao]), dir_init=None)
    # A base é limpa (teste acima): o problema tem de ser o da mutação.
    assert any(p.startswith(("0099_mutante.sql:", "funções:")) for p in problemas), problemas


@pytest.mark.parametrize(
    "mutacao",
    [
        # Sem o WITH, o CREATE OR REPLACE DESLIGA a opção (provado em 30/10).
        "CREATE OR REPLACE VIEW v_prova_externa_resumo AS SELECT p.nome FROM prova_externa p;",
        "ALTER VIEW v_prova_externa_resumo RESET (security_invoker);",
        "ALTER VIEW v_prova_externa_resumo SET (security_invoker = false);",
    ],
)
def test_a_view_da_lista_branca_nao_volta_a_rodar_como_dono(tmp_path, mutacao):
    """A 0076 dá GRANT numa view só porque ela lê com o privilégio de quem
    chama. A auditoria olha o ESTADO FINAL: quem a devolve ao dono reprova no
    GRANT da 0076, que é o comando que passa a expor o que ela lê."""
    problemas = auditar_migrations(_migrations_com(tmp_path, up=mutacao), dir_init=None)
    assert any("v_prova_externa_resumo é view" in p for p in problemas), problemas


def test_recriar_a_view_com_a_opcao_mantem_a_view_fora_da_regua_do_dono(tmp_path):
    recriada = (
        "CREATE OR REPLACE VIEW v_prova_externa_resumo WITH (security_invoker = true) AS "
        "SELECT p.nome FROM prova_externa p;"
    )
    assert auditar_migrations(_migrations_com(tmp_path, up=recriada), dir_init=None) == []


def test_as_views_da_lista_branca_nao_rodam_como_dono():
    comandos = [c for p in _ups() for c in _separar(p.read_text(encoding="utf-8"))]
    do_dono = _views(comandos)
    assert VIEWS_DA_LISTA_BRANCA - set(lista_branca(DIR_MIGRATIONS)) == set()
    assert VIEWS_DA_LISTA_BRANCA & do_dono == set()
    # E as que ficaram de fora continuam sendo do dono: a do perfil cita
    # `observacoes`, e por isso a ficha lê `candidato_externo` direto.
    assert "v_candidato_externo" in do_dono


def test_recriar_a_view_materializada_tira_ela_da_lista_branca(tmp_path):
    """O GRANT morre com o objeto: foi o que a 0065 e a 0068 fizeram com ela.
    O leitor segue o DROP, e `test_lista_branca_cobre_as_tabelas_das_tools_expostas`
    reprova a migration que recriar a view sem repetir o GRANT."""
    recriada = (
        "DROP MATERIALIZED VIEW v_candidato_externo_por_nome;\n"
        "CREATE MATERIALIZED VIEW v_candidato_externo_por_nome AS SELECT c.nome FROM candidato_externo c;"
    )
    migrations = _migrations_com(tmp_path, up=recriada)
    assert "v_candidato_externo_por_nome" not in lista_branca(migrations)

    regrant = f"{recriada}\nGRANT SELECT (nome) ON v_candidato_externo_por_nome TO sas_leitura;"
    (migrations / "0099_mutante.sql").write_text(f"BEGIN;\n{regrant}\nCOMMIT;\n", encoding="utf-8")
    assert lista_branca(migrations)["v_candidato_externo_por_nome"] == frozenset({"nome"})


def test_a_regua_da_captacao_libera_tres_tabelas_e_nao_o_prefixo():
    assert not tabela_proibida("candidato_externo")
    assert tabela_proibida("candidato_externo_contato")
    assert tabela_proibida("conquista_externa_rascunho")
    assert tabela_proibida("v_candidato_externo")
    assert not tabela_proibida("v_candidato_externo_por_nome")
    assert set(COLUNAS_PROIBIDAS_DA_CAPTACAO) == {"candidato_externo", "conquista_externa"}


def test_a_funcao_da_busca_por_conquista_so_cita_coluna_da_lista_branca():
    """Ela é SECURITY INVOKER: roda com o privilégio do sas_mcp, e o Postgres
    exige SELECT em toda coluna citada. Coluna nova no corpo dela, sem GRANT,
    seria 42501 só em produção, numa tool que a suíte diz que funciona."""
    corpo = next(
        c.corpos[0]
        for c in _separar(_arquivo("0068_").read_text(encoding="utf-8"))
        if c.texto.startswith("CREATE FUNCTION buscar_candidatos_por_conquista")
    )
    apelidos = {
        "ce": "conquista_externa", "c": "candidato_externo", "p": "prova_externa",
        "v": "v_candidato_externo_por_nome",
    }
    citadas = {(apelidos[a], coluna) for a, coluna in re.findall(r"\b(ce|c|p|v)\.(\w+)", corpo)}
    branca = lista_branca(DIR_MIGRATIONS)
    assert len(citadas) > 20  # senão o regex parou de achar o corpo
    assert [(t, c) for t, c in sorted(citadas) if c not in (branca[t] or frozenset())] == []


def test_a_0076_so_concede_select_e_o_down_a_espelha():
    up = _comandos_de(_arquivo("0076_"))
    down = _comandos_de(_arquivo("0076_").with_name(_arquivo("0076_").name.replace(".sql", ".down.sql")))
    concessoes = [c for c in up if c.startswith("GRANT")]
    assert len(concessoes) == 5
    assert all(c.startswith("GRANT SELECT (") and c.endswith(" TO sas_leitura") for c in concessoes)
    # Coluna a coluna: o .down tira exatamente o que o up deu, sem tocar no resto.
    espelho = sorted(c.replace("GRANT ", "REVOKE ", 1).replace(" TO sas_leitura", " FROM sas_leitura") for c in concessoes)
    assert sorted(c for c in down if c.startswith("REVOKE")) == espelho
    assert "ALTER VIEW v_prova_externa_resumo RESET (security_invoker)" in down


def test_auditoria_le_os_downs_tambem(tmp_path):
    # Um .down que concede algo vale enquanto a migration dele estiver revertida.
    problemas = auditar_migrations(_migrations_com(tmp_path, down=MUTACOES["update_em_nota"]), dir_init=None)
    assert [p for p in problemas if p.startswith("0099_mutante.down.sql:")]


@pytest.mark.parametrize(
    "linha",
    [
        "psql -c 'GRANT SELECT ON chat_mensagem TO PUBLIC;'",
        # O login do MCP não nasce no init: lá ele ganharia a senha do env num
        # SQL que só roda na criação do volume — e a 0071 o põe em NULL depois.
        "psql -c \"CREATE ROLE autenticador_mcp LOGIN PASSWORD '$POSTGREST_MCP_PASSWORD';\"",
    ],
)
def test_auditoria_le_o_init_dos_papeis(tmp_path, linha):
    init = tmp_path / "init"
    shutil.copytree(DIR_INIT, init)
    with (init / "01-papeis.sh").open("a", encoding="utf-8") as arquivo:
        arquivo.write(f"\n# it's: apóstrofo de comentário de shell\n{linha}\n")
    assert auditar_migrations(DIR_MIGRATIONS, init)
    assert auditar_migrations(DIR_MIGRATIONS, DIR_INIT) == []


def _corpo_da_view(nome: str) -> str:
    """O CREATE VIEW da 0074, sem comentário e com o espaço normalizado, mas com
    os literais: `_separar` os troca por `''`, e aqui eles são a regra."""
    texto = re.sub(r"--[^\n]*", "", _arquivo("0074_").read_text(encoding="utf-8"))
    (corpo,) = re.findall(rf"CREATE VIEW {nome}\b.*?;", texto, re.S)
    return " ".join(corpo.split())


def test_o_verificador_sonda_os_mesmos_canais_que_a_trilha_le():
    assert set(CANAIS_DA_TRILHA_NA_VIEW) == set(CANAIS_DA_TRILHA)
    assert set(ACOES_FORA_DA_TRILHA_NA_VIEW) == set(ACOES_FORA_DA_TRILHA)


def test_a_view_da_trilha_corta_os_logins_que_o_canal_da_cantina_grava():
    """O canal não basta: `cantina` grava `login_falhou`, com o que a pessoa digitou
    em `ator_id`. Abrir o canal sem isto reabria o motivo de a view existir."""
    corpo = _corpo_da_view("trilha_de_alteracoes")
    achado = re.search(r"e\.acao NOT IN \((?P<lista>[^)]*)\)", corpo)
    assert achado and set(re.findall(r"'(\w+)'", achado["lista"])) == set(ACOES_FORA_DA_TRILHA)


#: As duas das listas estão na 0077, com o corpo e o down travados em testes próprios.
VIEWS_DA_0074 = VIEWS_DO_MCP - {"lista_questoes_da_coordenacao", "lista_questoes_item_da_coordenacao"}


def test_as_views_do_mcp_sao_as_da_0074_com_barreira_e_com_grant_por_coluna():
    branca = lista_branca(DIR_MIGRATIONS)
    for nome in VIEWS_DA_0074:
        assert f"CREATE VIEW {nome} WITH (security_barrier = true) AS" in _corpo_da_view(nome)
        assert branca[nome], nome
        assert nome not in TABELAS_PROIBIDAS and not nome.startswith(PREFIXOS_PROIBIDOS)


def test_o_que_o_mcp_le_por_view_continua_fechado_como_tabela():
    """A view é o caminho; a tabela segue dando 42501. `usuario_coordenacao` é
    também a sonda do boot: o GRANT nela impediria o MCP de subir (dados.py)."""
    branca = lista_branca(DIR_MIGRATIONS)
    assert TABELA_DA_SONDA == "usuario_coordenacao"
    for tabela in ("usuario_coordenacao", "evento_auditoria", "aula_gravacao"):
        assert tabela in TABELAS_PROIBIDAS and tabela not in branca


def test_a_view_da_trilha_e_a_lista_da_tool_nao_divergem():
    """Dois lados da mesma regra: o da tool é o que ela mostra; o da view, o que
    o MCP consegue ler. Canal novo na tool sem a view volta vazio; chave nova na
    view sem revisão sai do banco para quem não devia ler."""
    corpo = _corpo_da_view("trilha_de_alteracoes")
    canais = re.search(r"WHERE e\.canal IN \((?P<lista>[^)]*)\)", corpo)
    assert canais and set(re.findall(r"'(\w+)'", canais["lista"])) == set(CANAIS_DA_TRILHA)
    chaves = re.search(r"WHERE d\.chave IN \((?P<lista>[^)]*)\)", corpo)
    assert chaves
    assert set(re.findall(r"'(\w+)'", chaves["lista"])) == {c for lista in DETALHE_POR_ACAO.values() for c in lista}


def test_a_view_da_trilha_nao_tem_a_coluna_do_ip():
    corpo = _corpo_da_view("trilha_de_alteracoes").split(" FROM evento_auditoria")[0]
    assert not re.search(r"\be\.(?:ip|request_id)\b", corpo)


def test_a_view_dos_nomes_entrega_o_par_e_mais_nada():
    assert _corpo_da_view("nome_da_coordenacao").endswith("AS SELECT u.id, u.nome FROM usuario_coordenacao AS u;")


def test_a_view_das_aulas_entrega_o_link_e_nao_o_s3():
    """O link sai por decisão da coordenação (30/10), como a tela o mostra. O
    S3, onde o vídeo mora, não sai, nem dentro do erro: a view corta a linha que
    o Postgres despeja."""
    corpo = _corpo_da_view("aula_gravacao_para_ia")
    assert "[vídeo]" in corpo and "Failing row contains" in corpo
    for coluna in ("a.youtube_video_id", "a.youtube_titulo", "a.canvas_pagina_url"):
        assert coluna in corpo
    assert not re.search(r"s3_|conferencia|canvas_pagina_slug", corpo)


@pytest.mark.parametrize(
    "comando",
    [
        "CREATE VIEW nome_da_coordenacao AS SELECT 1",
        "CREATE OR REPLACE VIEW aula_gravacao_para_ia AS SELECT 1",
        "ALTER VIEW trilha_de_alteracoes SET (security_barrier = true)",
    ],
)
def test_nem_a_migration_do_mcp_tira_a_barreira(comando):
    assert _auditar_view(comando, do_mcp=True)


def test_a_regra_das_views_nao_alcanca_a_view_comum():
    assert _auditar_view("CREATE VIEW v_qualquer AS SELECT 1", do_mcp=False) == []
    assert _auditar_view("DROP VIEW IF EXISTS trilha_de_alteracoes", do_mcp=True) == []


def test_as_colunas_proibidas_das_tabelas_abertas_nao_estao_na_lista():
    branca = lista_branca(DIR_MIGRATIONS)
    for tabela, colunas in COLUNAS_PROIBIDAS_POR_TABELA.items():
        assert branca[tabela] & set(colunas) == set(), tabela


def test_o_down_da_0074_tira_so_o_que_ela_deu():
    """Em `simulado`, `ciclo` e `nota` a 0071 já concedia colunas: o down revoga
    por coluna, e um REVOKE na tabela inteira tiraria a lista dela junto."""
    up = _arquivo("0074_")
    down = _comandos_de(up.with_name(up.name.replace(".sql", ".down.sql")))
    for tabela in ("simulado", "ciclo", "nota"):
        fim = f") ON {tabela} FROM sas_leitura"
        assert len([c for c in down if c.startswith("REVOKE SELECT (") and c.endswith(fim)]) == 1, tabela
    for nome in VIEWS_DA_0074:
        assert f"DROP VIEW IF EXISTS {nome}" in down


def test_o_que_o_sas_mcp_recebe_direto_e_so_o_da_0071_e_da_0072():
    concessoes = sorted(c for c in _todos_os_comandos() if re.fullmatch(r"GRANT .+ TO sas_mcp", c))
    assert concessoes == sorted([
        "GRANT EXECUTE ON FUNCTION mcp_conferir_token(text) TO sas_mcp",
        "GRANT INSERT (acao, canal, ator_tipo, ator_id, recurso, ip, detalhe, request_id) ON evento_auditoria TO sas_mcp",
        "GRANT USAGE ON SEQUENCE evento_auditoria_id_seq TO sas_mcp",
        "GRANT sas_leitura TO sas_mcp",
    ])


def test_o_login_recebe_so_o_sas_mcp_e_sem_herdar():
    # Tudo o que o autenticador_mcp é está nesta linha: troca para o sas_mcp,
    # não herda dele, e não alcança o sas_service por cadeia nenhuma (0071).
    concessoes = [c for c in _todos_os_comandos() if re.search(rf"\bTO {LOGIN_DO_MCP}\b", c)]
    assert concessoes == [f"GRANT sas_mcp TO {LOGIN_DO_MCP} WITH INHERIT FALSE"]
    # E o login da API não volta a ser membro de papel do MCP: era o desenho da
    # primeira versão da 0071, e o authenticator é membro do sas_service.
    assert [c for c in _todos_os_comandos() if re.search(r"\bauthenticator\b", c)] == []


# ─── Sem DEFAULT PRIVILEGES ──────────────────────────────────────────────


def test_sem_default_privileges_para_os_papeis_do_mcp_nem_para_public():
    # Tabela nova nasce invisível ao MCP: é a falha fechada da 0071. PUBLIC
    # conta porque o sas_mcp herda de PUBLIC. O init dos papéis entra porque é
    # lá que mora o DEFAULT PRIVILEGES do sas_service.
    textos = [c for c in _todos_os_comandos()]
    textos += [p.read_text(encoding="utf-8") for p in DIR_INIT.glob("*")]
    for texto in textos:
        for trecho in re.findall(r"ALTER\s+DEFAULT\s+PRIVILEGES[^;]*", texto, flags=re.IGNORECASE):
            assert not any(p in trecho.lower() for p in PAPEIS_DO_MCP), trecho
            assert not re.search(r"\bTO\s+(?:\w+\s*,\s*)*PUBLIC\b", trecho, flags=re.IGNORECASE), trecho


# ─── Os papéis ───────────────────────────────────────────────────────────


_ALTER_DO_LOGIN = (
    f"ALTER ROLE {LOGIN_DO_MCP} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION "
    "NOBYPASSRLS CONNECTION LIMIT 10 PASSWORD NULL"
)
_TETO_DE_DURACAO = f"ALTER ROLE {LOGIN_DO_MCP} SET statement_timeout = ''"


def test_papeis_nascem_nologin_e_o_login_entra_sem_senha_no_arquivo():
    lidos = _separar(_arquivo("0071_").read_text(encoding="utf-8"))
    comandos = [c.texto for c in lidos]
    (criacao,) = [c.corpos[0] for c in lidos if any("CREATE ROLE" in corpo for corpo in c.corpos)]
    # Os três nascem NOLOGIN dentro do DO; o LOGIN do login vem à vista, num
    # ALTER que a auditoria lê, com PASSWORD NULL — ninguém entra até a
    # operação definir a senha (0071, docker-compose.yml).
    for papel in PAPEIS_DO_MCP:
        assert f"CREATE ROLE {papel} NOLOGIN;" in criacao, papel
    assert _ALTER_DO_LOGIN in comandos
    assert "GRANT sas_leitura TO sas_mcp" in comandos
    assert f"GRANT sas_mcp TO {LOGIN_DO_MCP} WITH INHERIT FALSE" in comandos


def test_nenhuma_migration_escreve_senha():
    # A senha do login do MCP é da operação (POSTGREST_MCP_PASSWORD): o arquivo
    # vai para o git. `PASSWORD NULL` é ausência de senha, e é a única forma.
    for caminho in sorted(DIR_MIGRATIONS.glob("*.sql")):
        for comando in _separar(caminho.read_text(encoding="utf-8")):
            for trecho in (comando.texto, *comando.corpos):
                for m in re.finditer(r"\bPASSWORD\b\s*(\S*)", trecho, flags=re.IGNORECASE):
                    assert m[1].upper().rstrip(";") == "NULL", (caminho.name, trecho[:160])


def test_o_teto_de_duracao_do_login_fica_abaixo_do_prazo_das_tools():
    from app.chat.ferramentas import PRAZO_PADRAO_S

    (comando,) = [
        c for c in _separar(_arquivo("0071_").read_text(encoding="utf-8")) if c.texto == _TETO_DE_DURACAO
    ]
    valor = re.fullmatch(r"'(\d+)s'", comando.literais[0])
    # Abaixo do prazo: quando ele abandona a thread, a consulta ainda roda no
    # Postgres da API — e é este teto que a mata lá (0071).
    assert valor and 0 < int(valor[1]) < PRAZO_PADRAO_S, comando.literais


def test_papel_que_ja_existia_volta_ao_que_a_0071_diz():
    # Papel é global no cluster: um sas_mcp antigo, membro do sas_service, saía
    # da 0071 "ok" e lendo senha_hash (revisão de 24/10). A 0071 tira todo
    # pertencimento que toque os três papéis — dos dois lados, o que tira o
    # `GRANT sas_mcp TO authenticator` da primeira versão — e toda config deles
    # ANTES de dar os dois certos: na ordem inversa, o laço revogaria o
    # `GRANT sas_leitura TO sas_mcp`, e o RESET ALL apagaria o teto de duração.
    lidos = _separar(_arquivo("0071_").read_text(encoding="utf-8"))
    comandos = [c.texto for c in lidos]
    limpeza = next(i for i, c in enumerate(lidos) if any("pg_auth_members" in corpo for corpo in c.corpos))
    corpo = " ".join(lidos[limpeza].corpos[0].split())
    assert "WHERE (membro.rolname IN ('sas_leitura', 'sas_mcp', 'autenticador_mcp')" in corpo
    assert "OR papel.rolname IN ('sas_leitura', 'sas_mcp', 'autenticador_mcp'))" in corpo
    assert "AND membro.rolname <> current_user" in corpo
    assert "format('REVOKE %I FROM %I GRANTED BY %I CASCADE'" in corpo
    assert "format('ALTER ROLE %I IN DATABASE %I RESET ALL'" in corpo
    for comando in (
        _ALTER_DO_LOGIN,
        "ALTER ROLE sas_leitura RESET ALL",
        "ALTER ROLE sas_mcp RESET ALL",
        f"ALTER ROLE {LOGIN_DO_MCP} RESET ALL",
        "REVOKE ALL ON SCHEMA public FROM sas_leitura, sas_mcp, autenticador_mcp",
    ):
        assert comandos.index(comando) < comandos.index("GRANT sas_leitura TO sas_mcp"), comando
    assert (
        limpeza
        < comandos.index("GRANT sas_leitura TO sas_mcp")
        < comandos.index(f"GRANT sas_mcp TO {LOGIN_DO_MCP} WITH INHERIT FALSE")
        < comandos.index(_TETO_DE_DURACAO)
    )


def test_o_down_tira_o_login_junto():
    # Papel é global no cluster: um login que sobrasse do down entraria no
    # Postgres com a senha antiga, e o `up` seguinte o reaproveitaria.
    down = _arquivo("0071_").with_name(_arquivo("0071_").name.replace(".sql", ".down.sql"))
    (corpo,) = [c.corpos[0] for c in _separar(down.read_text(encoding="utf-8")) if c.corpos]
    for papel in PAPEIS_DO_MCP:
        assert f"DROP OWNED BY {papel};" in corpo, papel
        assert f"DROP ROLE {papel};" in corpo, papel
    # O login sai antes do sas_mcp, de quem é membro.
    assert corpo.index(f"DROP ROLE {LOGIN_DO_MCP};") < corpo.index("DROP ROLE sas_mcp;")


# ─── A função de conferência e as SECURITY DEFINER ───────────────────────


def _cabecalho_da_funcao(texto: str, nome: str) -> str:
    """O CREATE FUNCTION sem o corpo — onde ficam SECURITY e SET."""
    for comando in _comandos(texto):
        if re.match(rf"CREATE (?:OR REPLACE )?FUNCTION {nome}\b", comando, flags=re.IGNORECASE):
            return comando
    raise AssertionError(f"CREATE FUNCTION {nome} não encontrado")


def test_mcp_conferir_token_e_security_definer_com_search_path_fixo():
    texto = _arquivo("0072_").read_text(encoding="utf-8")
    cabecalho = _cabecalho_da_funcao(texto, "mcp_conferir_token")
    assert "SECURITY DEFINER" in cabecalho.upper()
    # pg_temp por ÚLTIMO: sem ele explícito, o pg_temp vem primeiro e um objeto
    # temporário de mesmo nome sequestraria a função.
    assert re.search(r"SET search_path = public, pg_temp\b", cabecalho)
    assert re.search(r"RETURNS TABLE \(token_id uuid, coordenador_id uuid, nome text, papel text\)", cabecalho)


def test_mcp_conferir_token_so_o_sas_mcp_executa():
    comandos = [c for c in _comandos_de(_arquivo("0072_")) if "mcp_conferir_token" in c]
    assert "REVOKE ALL ON FUNCTION mcp_conferir_token(text) FROM PUBLIC" in comandos
    assert "GRANT EXECUTE ON FUNCTION mcp_conferir_token(text) TO sas_mcp" in comandos
    concessoes = [c for c in comandos if c.upper().startswith("GRANT")]
    assert concessoes == ["GRANT EXECUTE ON FUNCTION mcp_conferir_token(text) TO sas_mcp"]


def test_toda_funcao_que_o_mcp_executa_e_segura():
    # Com um segundo papel no PostgREST, toda função de PUBLIC vira RPC do
    # MCP: a SECURITY DEFINER roda como o dono (o superusuário das
    # migrations), e a com SQL dinâmico é porta para SET ROLE sas_service.
    ups = [c for p in _ups() for c in _separar(p.read_text(encoding="utf-8"))]
    assert auditar_funcoes(ups) == []


def _funcoes(*sql: str) -> list[str]:
    return auditar_funcoes(c for s in sql for c in _separar(s))


def test_o_simulador_de_acl_segue_create_drop_alter_e_rename():
    definer = "CREATE FUNCTION f() RETURNS void LANGUAGE sql SECURITY DEFINER AS $$ SELECT 1 $$;"
    fechar = "REVOKE EXECUTE ON FUNCTION f() FROM PUBLIC;"
    assert _funcoes(definer) != []
    assert _funcoes(definer, fechar) == []
    # CREATE OR REPLACE mantém o ACL; DROP + CREATE o devolve a PUBLIC.
    assert _funcoes(definer, fechar, definer.replace("CREATE", "CREATE OR REPLACE")) == []
    assert _funcoes(definer, fechar, "DROP FUNCTION IF EXISTS f();", definer) != []
    # ALTER … SECURITY DEFINER muda uma INVOKER aberta sem recriá-la.
    invoker = "CREATE FUNCTION g(p int) RETURNS void LANGUAGE sql AS $$ SELECT 1 $$;"
    assert _funcoes(invoker) == []
    assert _funcoes(invoker, "ALTER FUNCTION g(int) SECURITY DEFINER;") != []
    # RENAME leva o ACL junto; GRANT direto ao sas_mcp reabre.
    assert _funcoes(definer, fechar, "ALTER FUNCTION f() RENAME TO h;") == []
    assert _funcoes(definer, fechar, "GRANT EXECUTE ON FUNCTION f() TO sas_mcp;") != []
    # A única definer que o sas_mcp pode executar é a dele.
    conferir = definer.replace(" f()", " mcp_conferir_token(p_hash text)")
    assert _funcoes(conferir, "REVOKE ALL ON FUNCTION mcp_conferir_token(text) FROM PUBLIC;",
                    "GRANT EXECUTE ON FUNCTION mcp_conferir_token(text) TO sas_mcp;") == []
    # Função de gatilho não é chamável por RPC.
    gatilho = "CREATE FUNCTION t() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER AS $$ BEGIN RETURN NEW; END $$;"
    assert _funcoes(gatilho) == []


# ─── O estreito de escrita do sas_mcp ────────────────────────────────────


def _concessoes_ao_sas_mcp() -> list[str]:
    return [
        c for c in _todos_os_comandos()
        if c.upper().startswith("GRANT") and re.search(r"\bTO\b[^;]*\bsas_mcp\b", c, flags=re.I)
    ]


def test_sas_mcp_so_insere_na_auditoria_sem_id_nem_data():
    insercoes = [c for c in _concessoes_ao_sas_mcp() if c.upper().startswith("GRANT INSERT")]
    assert len(insercoes) == 1
    m = re.fullmatch(r"GRANT INSERT \(([^)]*)\) ON evento_auditoria TO sas_mcp", insercoes[0])
    assert m, insercoes[0]
    colunas = {c.strip() for c in m.group(1).split(",")}
    # Sem `id` e sem `ocorrido_em`: os dois saem do default, e o MCP não data
    # evento no passado (0072).
    assert colunas == {"acao", "canal", "ator_tipo", "ator_id", "recurso", "ip", "detalhe", "request_id"}


def test_token_mcp_fechado_para_o_mcp():
    comandos = _comandos_de(_arquivo("0072_"))
    assert "REVOKE ALL ON token_mcp FROM PUBLIC, sas_leitura, sas_mcp" in comandos
    for comando in _todos_os_comandos():
        if comando.upper().startswith("GRANT") and " token_mcp " in f" {comando} ":
            raise AssertionError(f"ninguém além do dono e do sas_service lê token_mcp: {comando}")


def test_token_mcp_guarda_so_o_hash():
    texto = _arquivo("0072_").read_text(encoding="utf-8")
    assert re.search(r"hash_acesso\s+text NOT NULL UNIQUE", texto)
    assert re.search(r"CHECK \(hash_acesso ~ '\^\[0-9a-f\]\{64\}\$'\)", texto)
    assert re.search(r"CREATE INDEX idx_token_mcp_usuario ON token_mcp \(usuario_coordenacao_id\)", texto)


# ─── A 0073: o OAuth, o e-mail da conta de IA e o código por e-mail ──────

#: As tabelas da 0073: credencial de conexão e de aprovação. Nenhuma é do MCP.
_TABELAS_DA_0073 = (
    "oauth_cliente_mcp", "oauth_pedido_mcp", "oauth_codigo_mcp", "oauth_refresh_mcp",
    "email_conta_ia_mcp", "oauth_codigo_por_email_mcp",
)


def test_as_tabelas_da_0073_ficam_fechadas_para_o_mcp():
    comandos = _comandos_de(_arquivo("0073_"))
    for tabela in _TABELAS_DA_0073:
        assert f"REVOKE ALL ON {tabela} FROM PUBLIC, sas_leitura, sas_mcp" in comandos, tabela
        # E a régua do verificador ao vivo (42501 sob o sas_mcp) as conhece.
        assert tabela in TABELAS_PROIBIDAS and tabela.startswith(PREFIXOS_PROIBIDOS), tabela
    for comando in _todos_os_comandos():
        if comando.upper().startswith("GRANT"):
            alvo = f" {comando} "
            assert not any(f" {t} " in alvo for t in _TABELAS_DA_0073), comando


def test_o_codigo_por_email_guarda_so_o_hmac_com_o_teto_de_tentativas_do_dominio():
    """O código de 6 dígitos: só o HMAC (preso ao pedido e ao e-mail), e o 5 do
    CHECK é o mesmo de app/mcp/emails_ia.TENTATIVAS_POR_CODIGO."""
    from app.mcp.emails_ia import TENTATIVAS_POR_CODIGO

    texto = _arquivo("0073_").read_text(encoding="utf-8")
    for coluna in ("hash_codigo", "hash_email"):
        assert re.search(rf"CHECK \({coluna} ~ '\^\[0-9a-f\]\{{64\}}\$'\)", texto), coluna
    (teto,) = re.findall(r"CHECK \(tentativas BETWEEN 0 AND (\d+)\)", texto)
    assert int(teto) == TENTATIVAS_POR_CODIGO
    # O único CASCADE da 0073: o código de um pedido que a faxina apaga vai junto.
    comandos = _comandos_de(_arquivo("0073_"))
    assert sum(c.count("ON DELETE CASCADE") for c in comandos) == 1
    assert re.search(r"pedido_id\s+text NOT NULL REFERENCES oauth_pedido_mcp \(id\) ON DELETE CASCADE", texto)


def test_o_email_da_ia_e_um_por_dono_entre_os_confirmados_e_vai_normalizado():
    """Único entre os CONFIRMADOS ativos — o que aguarda não tranca o dono da
    caixa — e único na conta entre os ativos (routes/mcp_emails_ia.py, regra 1)."""
    from app.routes.mcp_emails_ia import _INDICE_DO_EMAIL_CONFIRMADO, _INDICE_DO_EMAIL_NA_CONTA

    comandos = _comandos_de(_arquivo("0073_"))
    # É pelo NOME do índice que a rota reconhece a recusa e a traduz em 409.
    assert (
        f"CREATE UNIQUE INDEX {_INDICE_DO_EMAIL_CONFIRMADO} ON email_conta_ia_mcp (email) "
        "WHERE removido_em IS NULL AND confirmado_em IS NOT NULL"
    ) in comandos
    assert (
        f"CREATE UNIQUE INDEX {_INDICE_DO_EMAIL_NA_CONTA} ON email_conta_ia_mcp (usuario_coordenacao_id, email) "
        "WHERE removido_em IS NULL"
    ) in comandos
    texto = _arquivo("0073_").read_text(encoding="utf-8")
    assert re.search(r"CHECK \(email = lower\(btrim\(email\)\)", texto)


def test_a_confirmacao_do_email_guarda_so_o_hmac_com_o_teto_de_tentativas_do_dominio():
    """A prova de posse do cadastro (revisão de segurança de 26/10): o código
    de confirmar fica só como HMAC, com as MESMAS 5 tentativas do de aprovar, e
    o confirmado não guarda código nenhum."""
    from app.mcp.emails_ia import TENTATIVAS_POR_CODIGO

    texto = " ".join(_arquivo("0073_").read_text(encoding="utf-8").split())
    assert "CHECK (hash_codigo_de_confirmacao IS NULL OR hash_codigo_de_confirmacao ~ '^[0-9a-f]{64}$')" in texto
    (teto,) = re.findall(r"CHECK \(tentativas_de_confirmacao BETWEEN 0 AND (\d+)\)", texto)
    assert int(teto) == TENTATIVAS_POR_CODIGO
    assert (
        "CHECK ((confirmado_em IS NULL) = (hash_codigo_de_confirmacao IS NOT NULL) "
        "AND (hash_codigo_de_confirmacao IS NULL) = (confirmacao_expira_em IS NULL))"
    ) in texto
    assert "CHECK (ultimo_uso_em IS NULL OR confirmado_em IS NOT NULL)" in texto


def test_a_aprovacao_tem_autor_e_a_recusa_nao():
    """Desde 26/10 recusar não pede sessão nem código: o pedido recusado fica
    sem `decidido_por`, e o aprovado sempre o tem — o dono do e-mail."""
    texto = " ".join(_arquivo("0073_").read_text(encoding="utf-8").split())
    assert "(decidido_em IS NULL) = (aprovado IS NULL) AND (decidido_por IS NOT NULL) = (aprovado IS TRUE)" in texto


def test_o_down_da_0073_tira_as_tabelas_na_ordem_das_fks():
    down = _arquivo("0073_").with_name(_arquivo("0073_").name.replace(".sql", ".down.sql"))
    quedas = [c for c in _comandos_de(down) if c.startswith("DROP TABLE")]
    assert quedas == [f"DROP TABLE IF EXISTS {t}" for t in (
        "oauth_codigo_por_email_mcp", "oauth_refresh_mcp", "oauth_codigo_mcp", "oauth_pedido_mcp",
        "oauth_cliente_mcp", "email_conta_ia_mcp",
    )]


# ─── O gatilho que confina o MCP à própria trilha ────────────────────────


def _gatilho_da_trilha() -> tuple[str, str]:
    """(cabeçalho, corpo) da função do gatilho da 0072."""
    for comando in _separar(_arquivo("0072_").read_text(encoding="utf-8")):
        if comando.texto.startswith("CREATE FUNCTION evento_auditoria_so_do_mcp()"):
            return comando.texto, comando.corpos[0]
    raise AssertionError("o gatilho da trilha sumiu da 0072")


def test_trilha_tem_gatilho_que_so_aceita_evento_do_mcp():
    comandos = _comandos_de(_arquivo("0072_"))
    assert (
        "CREATE TRIGGER trg_evento_auditoria_so_do_mcp BEFORE INSERT ON evento_auditoria "
        "FOR EACH ROW EXECUTE FUNCTION evento_auditoria_so_do_mcp()"
    ) in comandos
    cabecalho, corpo = _gatilho_da_trilha()
    # INVOKER: `current_user` tem de ser o papel de quem insere, não o dono.
    assert "SECURITY DEFINER" not in cabecalho.upper()
    assert "IF current_user <> 'sas_mcp' THEN" in corpo
    # Ação EXATA: com o prefixo `mcp_` (a primeira versão), o sas_mcp forjava
    # as ações que só a API grava — revisão final de 26/10.
    assert "LIKE" not in corpo.upper()
    for regra in (
        "NEW.canal IS DISTINCT FROM 'mcp'",
        "(NEW.acao IS DISTINCT FROM 'mcp_ferramenta_chamada'\n"
        "           AND (NEW.acao IS DISTINCT FROM 'mcp_verificacao_papeis' OR NEW.ator_id IS NOT NULL))",
        "NEW.ator_tipo IS DISTINCT FROM 'coordenador'",
        "char_length(coalesce(NEW.ator_id, '')) > 64",
        "char_length(coalesce(NEW.recurso, '')) > 200",
        "char_length(coalesce(NEW.ip, '')) > 64",
        "char_length(coalesce(NEW.request_id, '')) > 128",
        "octet_length(coalesce(NEW.detalhe::text, '')) > 4096",
    ):
        assert regra in corpo, regra
    # 42501, como o resto do que o sas_mcp não pode: o PostgREST responde
    # igual a uma permissão negada.
    assert "ERRCODE = 'insufficient_privilege'" in corpo
    down = _comandos_de(_arquivo("0072_").with_name(_arquivo("0072_").name.replace(".sql", ".down.sql")))
    assert "DROP TRIGGER IF EXISTS trg_evento_auditoria_so_do_mcp ON evento_auditoria" in down
    assert "DROP FUNCTION IF EXISTS evento_auditoria_so_do_mcp()" in down


#: A regra do gatilho da 0072 em Python mora com a outra emulação da 0072, a
#: da RPC (tests/test_mcp_tokens.py): é ela que o banco falso do MCP aplica.
#: O teste acima confere o SQL; os de baixo, os dois lados contra ela.
_passa_no_gatilho = gatilho_da_0072_aceita


def test_a_emulacao_do_gatilho_le_os_tetos_do_sql():
    """Os números da emulação e do app são os do SQL: um teto mudado só de um
    lado deixaria a trilha sumir de novo sem teste nenhum perceber."""
    from app.mcp.auditoria_mcp import TETO_DO_IP

    _, corpo = _gatilho_da_trilha()
    tetos = dict(re.findall(r"char_length\(coalesce\(NEW\.(\w+), ''\)\) > (\d+)", corpo))
    assert tetos == {"ator_id": "64", "recurso": "200", "ip": "64", "request_id": "128"}
    assert int(tetos["ip"]) == TETO_DO_IP
    # O maior id de fora que o middleware herda cabe no teto do SQL.
    from app.observabilidade import request_id_aceito

    maior = max(n for n in range(1, 300) if request_id_aceito("a" * n))
    assert maior <= int(tetos["request_id"])
    evento = {"canal": "mcp", "acao": "mcp_ferramenta_chamada", "ator_tipo": "coordenador"}
    for coluna, teto in tetos.items():
        assert _passa_no_gatilho({**evento, coluna: "x" * int(teto)}), coluna
        assert not _passa_no_gatilho({**evento, coluna: "x" * (int(teto) + 1)}), coluna


def test_o_sas_mcp_nao_grava_acao_que_so_a_api_grava():
    """O gatilho aceitava qualquer `mcp_*`: um MCP comprometido gravava "a
    administradora X revogou a conexão Y", que a linha do tempo PADRÃO mostra
    igual à real, com a conexão viva (revisão final de 26/10)."""
    from app.mcp.auditoria_mcp import ACAO_CHAMADA, ACAO_CONEXAO_EMITIDA, ACAO_CONEXAO_REVOGADA
    from app.routes.mcp_emails_ia import (
        ACAO_EMAIL_CADASTRADO,
        ACAO_EMAIL_CONFIRMADO,
        ACAO_EMAIL_REMOVIDO,
    )
    from app.routes.oauth_mcp import ACAO_PEDIDO_APROVADO, ACAO_PEDIDO_RECUSADO
    from scripts.verificar_papeis_do_mcp import _ACOES_SO_DA_API

    base = {"canal": "mcp", "ator_tipo": "coordenador", "recurso": "mcp_token/x"}
    admin = "ad000000-0000-4000-8000-000000000001"
    da_api = (
        ACAO_CONEXAO_EMITIDA, ACAO_CONEXAO_REVOGADA, ACAO_PEDIDO_APROVADO, ACAO_PEDIDO_RECUSADO,
        # As do e-mail da conta de IA (26/10): dizem quem pode aprovar conexão —
        # a confirmação, mais que todas, porque é ela que dá o poder de aprovar.
        ACAO_EMAIL_CADASTRADO, ACAO_EMAIL_CONFIRMADO, ACAO_EMAIL_REMOVIDO,
    )
    # A sonda do verificador ao vivo tenta forjar cada uma delas.
    assert set(_ACOES_SO_DA_API) == set(da_api)
    for acao in da_api:
        assert not _passa_no_gatilho({**base, "acao": acao, "ator_id": admin}), acao
        assert not _passa_no_gatilho({**base, "acao": acao}), acao
    assert _passa_no_gatilho({**base, "acao": ACAO_CHAMADA, "ator_id": admin})
    # A verificação só sem ator: com ator, seria "a conta X verificou".
    assert _passa_no_gatilho({**base, "acao": "mcp_verificacao_papeis"})
    assert not _passa_no_gatilho({**base, "acao": "mcp_verificacao_papeis", "ator_id": admin})
    assert ACOES_DO_SAS_MCP == (ACAO_CHAMADA, "mcp_verificacao_papeis")


def test_o_evento_que_o_mcp_grava_passa_no_gatilho():
    # O outro lado da regra: se app/mcp/auditoria_mcp mudar canal, ação ou
    # ator, o INSERT passa a voltar 42501 — e `registrar_chamada` engole o erro,
    # então a trilha do MCP sumiria calada. Este teste é o que avisa.
    from app.mcp import auditoria_mcp
    from app.mcp.tokens import Identidade

    gravados: list[dict] = []

    class _Tabela:
        def insert(self, evento: dict, **_: object) -> _Tabela:
            gravados.append(evento)
            return self

        def execute(self) -> None:
            return None

    class _Cliente:
        def table(self, nome: str) -> _Tabela:
            assert nome == "evento_auditoria"
            return _Tabela()

    identidade = Identidade(
        token_id="7da997c3-7160-4321-9a35-7da2978b5702",
        coordenador_id="34881b72-41ad-4c58-8e90-c5ceee70fb5a",
        nome="Coordenadora",
        papel="administrador",
    )
    auditoria_mcp.registrar_chamada(
        _Cliente(), identidade=identidade, ferramenta="relatorio_ciclo", desfecho="teto_de_linhas",
        duracao_ms=10**7, linhas=10**6, ip="2001:0db8:85a3:0000:0000:8a2e:0370:7334",
        request_id="0f8fad5b-d9cb-469f-a165-70867728950e",
    )
    assert len(gravados) == 1
    assert _passa_no_gatilho(gravados[0]), gravados[0]


def test_o_evento_do_verificador_passa_no_gatilho_e_o_da_api_nao_precisa():
    # O verificador grava pelo sas_mcp (tem de passar) e pelo sas_service com
    # ator `sistema` — que o gatilho recusaria do sas_mcp: é a prova, no banco,
    # de que ele só confina o MCP.
    assert _passa_no_gatilho(_evento("sas_mcp"))
    assert not _passa_no_gatilho(_evento("sas_service", ator_tipo="sistema"))
    assert set(_evento("sas_mcp")) <= COLUNAS_DA_TRILHA


# ─── O leitor das migrations ─────────────────────────────────────────────


def test_separador_le_como_o_psql():
    sql = (
        "-- it's: o apóstrofo do comentário não abre literal\n"
        "GRANT SELECT (a) ON t TO sas_leitura;\n"
        "COMMENT ON TABLE t IS 'texto com ; e com '' dentro';\n"
        "CREATE FUNCTION f() RETURNS void AS $corpo$ BEGIN PERFORM ';'; END; $corpo$ LANGUAGE plpgsql;\n"
        '/* bloco /* aninhado */ ainda comentário; */ GRANT SELECT (b) ON "t" TO "sas_leitura";\n'
        "SELECT $1, E'a\\'b;c';\n"
    )
    comandos = _separar(sql)
    assert [c.texto for c in comandos] == [
        "GRANT SELECT (a) ON t TO sas_leitura",
        "COMMENT ON TABLE t IS ''",
        "CREATE FUNCTION f() RETURNS void AS $$ LANGUAGE plpgsql",
        "GRANT SELECT (b) ON t TO sas_leitura",
        "SELECT $1, E''",
    ]
    assert comandos[2].corpos == (" BEGIN PERFORM ';'; END; ",)


def test_leitor_aplica_grant_e_revoke_em_ordem(tmp_path):
    (tmp_path / "0001_a.sql").write_text(
        "-- GRANT SELECT (x) ON t TO sas_leitura; (comentário, não conta)\n"
        "CREATE FUNCTION f() RETURNS void AS $$ BEGIN PERFORM 1; END; $$ LANGUAGE plpgsql;\n"
        "COMMENT ON TABLE t IS 'texto com ; dentro';\n"
        "GRANT SELECT (a, b) ON t TO sas_leitura;\n"
        "GRANT SELECT ON u TO sas_leitura;\n"
        "GRANT SELECT (z) ON w TO sas_service;\n",
        encoding="utf-8",
    )
    (tmp_path / "0002_b.sql").write_text(
        "REVOKE SELECT (b) ON t FROM sas_leitura;\n", encoding="utf-8"
    )
    assert lista_branca(tmp_path) == {"t": frozenset({"a"}), "u": None}
    (tmp_path / "0003_c.sql").write_text(
        "REVOKE ALL ON ALL TABLES IN SCHEMA public FROM sas_leitura, sas_mcp;\n"
        "GRANT SELECT (c) ON t TO sas_leitura;\n",
        encoding="utf-8",
    )
    assert lista_branca(tmp_path) == {"t": frozenset({"c"})}


def test_lista_branca_cobre_as_tabelas_das_tools_expostas():
    # As tabelas que as tools expostas leem (0071, 0074, 0075 e 0076), inclusive
    # as do banco de questões e `alerta`, de listar_alertas — exposta em 26/10,
    # quando o dono liberou o nome do aluno no MCP. Tirar uma daqui quebra uma
    # tool no MCP com 42501.
    esperadas = {
        "alerta",
        "aluno", "ano_letivo", "ciclo", "classificacao_aluno", "criterio_classificacao",
        "predicado_criterio", "insight_ciclo", "materia", "matricula_turma",
        "metrica_simulado", "nota", "questao", "questao_resposta_aluno", "sede",
        "simulado", "turma", "vestibular_alvo_aluno", "questao_vestibular",
        "questao_vestibular_alternativa", "questao_vestibular_topico",
        "topico_taxonomia", "topico_taxonomia_assunto", "parametro_importancia",
        # A régua, as rotinas e a trilha (0074), as três últimas por view.
        "canvas_sync_execucao", "curso_monitorado_gravacao", "disparo", "evento_agenda",
        "regra_lembrete", "trilha_de_alteracoes", "nome_da_coordenacao", "aula_gravacao_para_ia",
        # A cantina (0075, decisão de 30/10): tudo o que as sete tools leem.
        "cantina", "cardapio", "cardapio_bloco", "cardapio_opcao",
        "direito_refeicao_aluno", "pedido_refeicao", "pedido_refeicao_item",
        "prova_externa", "candidato_externo", "conquista_externa",
        "v_candidato_externo_por_nome", "v_prova_externa_resumo",
        # 0077 (30/10): as listas da coordenação, de minhas_listas_do_banco. São as
        # VIEWS, e não as tabelas: lá está o lado do aluno também.
        "lista_questoes_da_coordenacao", "lista_questoes_item_da_coordenacao",
    }
    assert set(lista_branca(DIR_MIGRATIONS)) == esperadas


# ─── Os compose ──────────────────────────────────────────────────────────
#
# O de dev tem o MCP desde já; o de produção (infra/vps) só o terá depois do
# portão de LGPD (docs/43 §5.4). Os testes valem para os dois: no dia em que o
# postgrest_mcp entrar em produção, ele entra com as mesmas travas.

_COMPOSES = {"dev": RAIZ / "docker-compose.yml", "producao": RAIZ / "infra" / "vps" / "docker-compose.yml"}

#: O env do PostgREST do MCP é uma lista FECHADA: chave nova (PGRST_JWT_SECRET,
#: PGRST_DB_PRE_REQUEST, PGRST_ROLE_CLAIM_KEY…) pede revisão antes de entrar.
_ENV_DO_POSTGREST_DO_MCP = frozenset(
    {"PGRST_DB_URI", "PGRST_DB_SCHEMAS", "PGRST_DB_ANON_ROLE", "PGRST_DB_CONFIG", "PGRST_DB_POOL",
     "PGRST_SERVER_PORT", "TZ"}
)


def _servicos(compose: str) -> dict:
    yaml = pytest.importorskip("yaml")
    caminho = _COMPOSES[compose]
    if not caminho.exists():
        pytest.skip(f"{caminho.name} fora deste checkout (container da API)")
    return yaml.safe_load(caminho.read_text(encoding="utf-8"))["services"]


def _servico(servicos: dict, nome: str, compose: str) -> dict:
    if nome not in servicos:
        if compose == "dev":
            pytest.fail(f"o compose de dev perdeu o serviço {nome}")
        pytest.skip("produção ainda sem MCP: entra depois do portão de LGPD (docs/43 §5.4)")
    return servicos[nome]


def _env(servico: dict) -> dict[str, str]:
    env = servico.get("environment") or {}
    if isinstance(env, list):
        env = dict(item.split("=", 1) if "=" in item else (item, "") for item in env)
    return {str(chave): str(valor) for chave, valor in env.items()}


@pytest.mark.parametrize("compose", sorted(_COMPOSES))
def test_postgrest_do_mcp_cai_no_sas_mcp_sem_segredo_e_sem_config_do_banco(compose):
    servicos = _servicos(compose)
    servico = _servico(servicos, "postgrest_mcp", compose)
    env = _env(servico)
    assert env["PGRST_DB_ANON_ROLE"] == "sas_mcp"
    # Sem PGRST_JWT_SECRET (todo Bearer vira PGRST300) nem nada que não tenha
    # passado por revisão.
    assert set(env) <= _ENV_DO_POSTGREST_DO_MCP, sorted(set(env) - _ENV_DO_POSTGREST_DO_MCP)
    # Com a config do banco ligada (o padrão), um `pgrst.db_anon_role` ou
    # `pgrst.jwt_secret` gravado no papel de login valeria por cima do env
    # (revisão de 24/10). O login próprio já não alcança o sas_service; esta é
    # a segunda camada.
    assert env["PGRST_DB_CONFIG"].lower() == "false"
    # A config inteira está no env acima: nada de env_file, arquivo de config
    # montado ou comando que a troque.
    for chave in ("env_file", "command", "entrypoint", "volumes"):
        assert chave not in servico, chave
    assert servico["image"] == servicos["postgrest"]["image"]
    if compose == "dev":
        assert all(str(p).startswith("127.0.0.1:") for p in servico["ports"])
    else:
        # Só o `web` publica porta em produção: o Docker escreve no iptables
        # por cima do ufw (CLAUDE.md, armadilha 4).
        assert "ports" not in servico


#: `postgres://login:senha@resto`, com a senha vinda do ambiente.
_RE_URI = re.compile(r"postgres://(?P<login>[^:@/]+):(?P<senha>[^@]*)@(?P<resto>.+)")


@pytest.mark.parametrize("compose", sorted(_COMPOSES))
def test_postgrest_do_mcp_entra_com_o_login_proprio(compose):
    servicos = _servicos(compose)
    do_mcp = _RE_URI.fullmatch(_env(_servico(servicos, "postgrest_mcp", compose))["PGRST_DB_URI"])
    da_api = _RE_URI.fullmatch(_env(servicos["postgrest"])["PGRST_DB_URI"])
    assert do_mcp and da_api
    # O autenticador_mcp (0071), membro só do sas_mcp — e não o login da API,
    # que é membro do sas_service: com ele, um SET ROLE dentro de uma
    # requisição do MCP, ou um `pgrst.*` no papel de login, levava ao acesso
    # total (revisão de 24/10).
    assert do_mcp["login"] == LOGIN_DO_MCP
    assert da_api["login"] != LOGIN_DO_MCP
    assert do_mcp["resto"] == da_api["resto"], "o mesmo banco"
    # A senha vem do ambiente, e de uma variável SÓ dele: nunca escrita aqui, e
    # nunca a do authenticator.
    senha = re.fullmatch(r"\$\{POSTGREST_MCP_PASSWORD(?P<padrao>[^}]*)\}", do_mcp["senha"])
    assert senha, do_mcp["senha"]
    if compose == "producao":
        # Sem senha CONHECIDA: faltou no .env, o postgrest_mcp não entra — em
        # vez de subir com a senha de desenvolvimento. Até 27/10 a trava era
        # `:?` (o compose parava). Mudou quando o MCP entrou em produção
        # DESLIGADO, no profile `mcp` (docs/43 §10): o compose interpola o
        # arquivo inteiro antes de aplicar os profiles, e com `:?` a senha
        # fora do .env quebrava todo `docker compose` da stack — deploy, cron,
        # `ps` — com o MCP desligado (provado no Compose v5.2.0). O padrão
        # VAZIO guarda a mesma intenção: a URI vai sem senha, o login (que a
        # 0071 cria com PASSWORD NULL) a recusa, e com o MCP ligado o
        # deploy.sh avisa e o smoke reprova. `:?` segue aceito, se um dia o
        # MCP de produção deixar de ser opcional.
        assert senha["padrao"] == ":-" or senha["padrao"].startswith(":?"), senha["padrao"]


@pytest.mark.parametrize("compose", sorted(_COMPOSES))
def test_o_pool_do_postgrest_do_mcp_cabe_no_teto_de_conexoes_do_login(compose):
    env = _env(_servico(_servicos(compose), "postgrest_mcp", compose))
    (teto,) = [
        int(m[1])
        for c in _comandos_de(_arquivo("0071_"))
        if (m := re.fullmatch(rf"ALTER ROLE {LOGIN_DO_MCP} LOGIN .* CONNECTION LIMIT (\d+) .*", c))
    ]
    # O PostgREST abre o pool e mais uma conexão, a do LISTEN (db-channel,
    # ligado por padrão). Passou do teto, as conexões a mais são recusadas.
    assert int(env["PGRST_DB_POOL"]) + 1 <= teto


@pytest.mark.parametrize("compose", sorted(_COMPOSES))
def test_mcp_fica_fora_da_rede_da_api(compose):
    servico = _servico(_servicos(compose), "mcp", compose)
    # Fora da rede default: do mcp não se alcança o db, o postgrest da API
    # (anônimo = sas_service) nem a api. Um bug de URL vira erro, em vez de
    # acesso total calado.
    assert "default" not in (servico.get("networks") or ["default"])
    assert _env(servico)["POSTGREST_URL"] == "http://postgrest_mcp:3000"
    arquivos = servico.get("env_file") or []
    arquivos = [arquivos] if isinstance(arquivos, (str, dict)) else arquivos
    caminhos = [Path(str(a["path"] if isinstance(a, dict) else a)).name for a in arquivos]
    # O .env da API tem JWT_SECRET_KEY, chave da OpenAI e token do Canvas.
    assert ".env" not in caminhos
    if compose == "producao":
        assert "ports" not in servico


def test_mcp_de_dev_nao_herda_os_segredos_da_api():
    mcp = _servicos("dev")["mcp"]
    assert "env_file" not in mcp
    # SÓ o código: montar ./api inteiro poria api/.env em /app/.env.
    assert mcp["volumes"] == ["./api/app:/app/app"]
    assert _env(mcp)["APP_ENV"] == "dev"
    assert all(str(p).startswith("127.0.0.1:") for p in mcp["ports"])
