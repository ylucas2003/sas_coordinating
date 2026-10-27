"""`texto_seguro`: o erro de rotina que pode chegar ao modelo (docs/43 §3.2, invariante 6).

Os casos vêm de mensagens REAIS sempre que dá: o httpx e o postgrest-py montam
a mensagem aqui mesmo, a partir de requisição e resposta de verdade, em vez de
o teste digitar o formato que ele acha que elas têm. O que se trava:

  1. endereço nenhum sobra — nem o host interno do PostgREST, nem a API do
     Canvas do colégio, nem um DSN com senha;
  2. credencial nenhuma sobra, venha ela como Bearer, JWT, chave da OpenAI,
     token do Canvas, token do MCP ou par `senha=…`;
  3. o que NÃO é segredo sobrevive: código de erro, status, nome de tabela,
     UUID, artigo de edital — senão a mensagem deixa de dizer o que houve;
  4. uma linha só, cortada no limite com reticências.
"""

from __future__ import annotations

import httpx
import pytest
from jose import jwt
from postgrest.exceptions import APIError

from app.texto_seguro import LIMITE_PADRAO, texto_seguro

TOKEN_CANVAS = "7~" + "Ab3dEf9h" * 8


def _erro_http(metodo: str, url: str, status: int, **kwargs) -> httpx.HTTPStatusError:
    requisicao = httpx.Request(metodo, url, **kwargs)
    with pytest.raises(httpx.HTTPStatusError) as exc:
        httpx.Response(status, request=requisicao).raise_for_status()
    return exc.value


# ─── 1 · Endereço ────────────────────────────────────────────────────────


def test_postgrest_fora_do_ar_nao_entrega_o_host_nem_a_query():
    """É o caso do docs/14 §5: o `str()` do httpx cita a URL inteira."""
    exc = _erro_http(
        "GET",
        "http://postgrest:3000/canvas_sync_execucao",
        503,
        params={"select": "finalizado_em,status", "status": "eq.sucesso"},
    )
    bruto = str(exc)
    assert "postgrest:3000" in bruto, "o httpx mudou o formato; o teste perdeu o sentido"

    limpo = texto_seguro(exc)

    assert "postgrest" not in limpo
    assert "canvas_sync_execucao" not in limpo
    assert "developer.mozilla.org" not in limpo
    assert limpo.startswith("Server error '503 Service Unavailable' for url '[endereço]'")


def test_canvas_recusando_nao_entrega_o_endereco_da_api():
    exc = _erro_http(
        "POST",
        "https://aridesa.instructure.com/api/v1/courses/1234/assignment_groups",
        401,
        headers={"Authorization": f"Bearer {TOKEN_CANVAS}"},
    )

    limpo = texto_seguro(exc)

    assert "instructure" not in limpo
    assert "401 Unauthorized" in limpo
    assert TOKEN_CANVAS not in limpo


def test_dsn_com_senha_sai_inteiro():
    limpo = texto_seguro(
        "connection failed: postgresql://sas_service:senha-forte@db:5432/sas (timeout)"
    )
    assert "senha-forte" not in limpo
    assert "db:5432" not in limpo
    assert limpo == "connection failed: [endereço] (timeout)"


# ─── 2 · Credencial ──────────────────────────────────────────────────────


def test_jwt_de_sessao_some():
    token = jwt.encode({"sub": "coord-1", "tipo": "coordenador"}, "x" * 40, algorithm="HS256")
    limpo = texto_seguro(f"token recusado ({token}) na rota /alunos")
    assert token not in limpo
    assert "eyJ" not in limpo
    assert "na rota /alunos" in limpo


def test_bearer_num_dump_de_cabecalho_some():
    """Biblioteca que loga o cabeçalho da requisição junto do erro."""
    limpo = texto_seguro(f"headers={{'Authorization': 'Bearer {TOKEN_CANVAS}'}} status=403")
    assert TOKEN_CANVAS not in limpo
    assert "Ab3dEf9h" not in limpo
    assert "status=403" in limpo


def test_token_do_canvas_solto_some():
    limpo = texto_seguro(f"falha com o token {TOKEN_CANVAS} na conta 694")
    assert TOKEN_CANVAS not in limpo
    assert "na conta 694" in limpo


def test_chave_da_openai_mascarada_ainda_sai():
    """O formato do `AuthenticationError` do SDK: a chave vem meio mascarada,
    com o link da conta junto."""
    bruto = (
        "Error code: 401 - {'error': {'message': 'Incorrect API key provided: "
        "sk-proj-AbCdEf**************************************WXyz. You can find your "
        "API key at https://platform.openai.com/account/api-keys.', 'type': "
        "'invalid_request_error', 'param': None, 'code': 'invalid_api_key'}}"
    )
    limpo = texto_seguro(bruto, limite=400)
    assert "sk-proj" not in limpo
    assert "WXyz" not in limpo
    assert "platform.openai.com" not in limpo
    assert "invalid_api_key" in limpo


def test_token_do_mcp_some():
    limpo = texto_seguro("token sas_mcp_9f8e7d6c5b4a3210fedcba recusado")
    assert "9f8e7d6c" not in limpo


def test_par_com_nome_de_segredo_perde_o_valor_e_guarda_o_nome():
    limpo = texto_seguro('senha=hunter2&usuario=leo, "api_key": "abc123", password: xyz')
    assert "hunter2" not in limpo
    assert "abc123" not in limpo
    assert "xyz" not in limpo
    # O nome fica: é ele que diz ao leitor o que foi omitido.
    assert "senha=[credencial]" in limpo
    assert "usuario=leo" in limpo


def test_chave_da_aws_some():
    limpo = texto_seguro("SignatureDoesNotMatch para AKIAABCDEFGHIJKLMNOP")
    assert "AKIAABCDEFGHIJKLMNOP" not in limpo
    assert "SignatureDoesNotMatch" in limpo


# ─── 3 · O que não é segredo sobrevive ───────────────────────────────────


def test_erro_do_postgrest_py_continua_dizendo_o_que_houve():
    """O `str()` do APIError é o dicionário cru — e o código PGRST205 é o que
    diz "reinicie o PostgREST" (armadilha 1 do CLAUDE.md). Ele tem de ficar."""
    exc = APIError(
        {
            "code": "PGRST205",
            "details": None,
            "hint": "Perhaps you meant the table 'public.ciclo'",
            "message": "Could not find the table 'public.cicloo' in the schema cache",
        }
    )
    limpo = texto_seguro(exc)
    assert "PGRST205" in limpo
    assert "schema cache" in limpo
    assert "public.ciclo" in limpo


def test_uuid_data_e_artigo_de_edital_passam_intactos():
    texto = (
        "nota 3f2c1a9e-8b7d-4c6e-9f10-2a3b4c5d6e7f do P22 em 2026-10-24T12:00:00+00:00 "
        "cortada pela régua (ITA §4.6.2.1)"
    )
    assert texto_seguro(texto) == texto


def test_frase_comum_com_palavra_de_credencial_nao_vira_marcador():
    """`Token`/`Basic` seguidos de palavra curta são português, não segredo."""
    for frase in ("Token de aluno sem identidade", "Basic authentication failed"):
        assert texto_seguro(frase) == frase


# ─── 4 · Forma ───────────────────────────────────────────────────────────


def test_colapsa_quebra_de_linha_e_espaco():
    assert texto_seguro("linha 1\n\n   linha 2\t\tfim  ") == "linha 1 linha 2 fim"


def test_corta_no_limite_com_reticencias():
    limpo = texto_seguro("a" * 500, limite=50)
    assert len(limpo) == 50
    assert limpo.endswith("…")


def test_o_padrao_e_duzentos_caracteres():
    assert len(texto_seguro("b" * 1000)) == LIMITE_PADRAO == 200


def test_limpa_antes_de_cortar():
    """Cortar primeiro deixaria meio token no fim, curto demais para os padrões
    reconhecerem."""
    limpo = texto_seguro("x" * 40 + f" {TOKEN_CANVAS}", limite=60)
    assert "Ab3dEf9h" not in limpo


def test_vazio_nulo_e_excecao_sem_mensagem():
    assert texto_seguro(None) == ""
    assert texto_seguro("   ") == ""
    assert texto_seguro("qualquer", limite=0) == ""
    # Sem mensagem, sobra o nome da classe — o que o /health/ready já mostra.
    assert texto_seguro(httpx.ReadTimeout("")) == "ReadTimeout"
    assert texto_seguro(TimeoutError()) == "TimeoutError"
