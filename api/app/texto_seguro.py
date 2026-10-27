"""Texto de erro de rotina que pode ser mostrado a um modelo (docs/43 §3.2, invariante 6).

Mensagem de exceção é escrita para quem depura, não para quem lê a resposta. A
do httpx carrega a URL inteira da requisição — host interno do PostgREST,
caminho e query, ou o endereço da API do Canvas do colégio —, e o `str()` de
um erro do postgrest-py é o dicionário cru que o servidor devolveu. A regra da
casa já existia em dois lugares, e nos dois a saída é NÃO mostrar a exceção: o
handler de 500 (`observabilidade.py`) e o despacho das tools
(`chat/ferramentas.py`), ambos por causa do docs/14 §5.

Este módulo é para o caso em que o erro É o dado: o `canvas_erro` do simulado
que não subiu, o `erro_mensagem` de uma rodada do sync, o `erro_detalhe` de uma
gravação. São `str(exc)` gravados no banco (canvas_sync/escrita.py,
canvas_sync/rotas.py, gravacoes_aula/rotas.py), e o assistente precisa dizer o
que aconteceu sem repetir endereço nem credencial.

⚠️ Não é defesa contra injeção de prompt: o que sai daqui continua sendo texto
de terceiro (o nome de um assignment digitado no Canvas, por exemplo), e quem o
põe no contexto do modelo continua tratando-o como dado, não como instrução.
"""

from __future__ import annotations

import re

#: Curto de propósito: é uma linha de diagnóstico dentro de uma resposta, não o
#: log. O texto inteiro continua no banco e no log para quem depura.
LIMITE_PADRAO = 200

_ENDERECO = "[endereço]"
_CREDENCIAL = "[credencial]"

# Qualquer `esquema://`, e não só http(s): `postgresql://usuario:senha@db/sas`
# é URL com a senha dentro, e `s3://` é onde mora o vídeo de aula com aluno
# menor de idade (gravacoes_aula). Para no espaço e nas aspas porque é assim
# que o httpx cita a URL ("for url '…'"); a query já vem percent-encoded.
_URL = re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s'\"`<>]+", re.IGNORECASE)

# Na ordem em que são aplicados. Os específicos vêm antes do genérico de três
# partes para o marcador ficar no lugar certo, não por correção: os dois tiram.
_CREDENCIAIS = (
    # `Authorization: Bearer …`. O token do Canvas é de ADMINISTRADOR do
    # colégio (docs/18 §7, risco 4). O mínimo de 16 caracteres poupa frase
    # comum como "Basic authentication failed".
    re.compile(r"\b(?:Bearer|Basic)\s+[A-Za-z0-9._~+/=-]{16,}", re.IGNORECASE),
    # JWT: o cabeçalho é JSON em base64url, e `{"` codifica sempre como `eyJ`.
    # É o formato da sessão do SAS (auth.py) e o do token do MCP (docs/43 §5.3).
    re.compile(r"\beyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*"),
    # Qualquer outro token de três partes compridas separadas por ponto. Os 16
    # caracteres por parte deixam passar `api.openai.com` e `public.ciclo`.
    re.compile(r"\b[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}"),
    # Chave da OpenAI (`sk-…`, `sk-proj-…`). O `*` entra porque a própria
    # OpenAI devolve a chave meio mascarada na mensagem de erro de autenticação.
    re.compile(r"\bsk-[A-Za-z0-9_*-]{16,}"),
    # O token pessoal do MCP da coordenação (docs/43 §5.3).
    re.compile(r"\bsas_mcp_[A-Za-z0-9_-]+"),
    # Token de API do Canvas: `<id>~<64 caracteres>`.
    re.compile(r"\b\d+~[A-Za-z0-9]{20,}"),
    # Chave de acesso da AWS (SES dos lembretes, S3 das gravações).
    re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    # Token de acesso do Google, o da publicação no YouTube.
    re.compile(r"\bya29\.[A-Za-z0-9._-]+"),
)

# O VALOR de qualquer par cujo nome é de segredo — `senha=…`, `"token": "…"`,
# `api_key: …`. O nome fica, porque é ele que diz ao leitor o que faltou.
_PAR_SECRETO = re.compile(
    r"\b(senha|password|passwd|pwd|secret|segredo|token|api[_-]?key|access[_-]?key"
    r"|client[_-]?secret|authorization)(['\"]?\s*[=:]\s*['\"]?)[^\s'\",;&]+",
    re.IGNORECASE,
)

_ESPACO = re.compile(r"\s+")


def texto_seguro(texto: object, limite: int = LIMITE_PADRAO) -> str:
    """O texto sem URL nem credencial, numa linha só, com até `limite` caracteres.

    A limpeza vem ANTES do corte: cortar primeiro deixaria meio token no fim do
    texto, curto demais para os padrões reconhecerem — e meio token do Canvas
    ainda é meio token.

    Aceita a própria exceção. Uma exceção sem mensagem (`TimeoutError()`, o
    `ReadTimeout` do httpx) vira o nome da classe, que é o que o /health/ready
    já mostra no lugar dela (main.py), em vez de uma string vazia.
    """
    if texto is None or limite <= 0:
        return ""
    bruto = str(texto)
    if isinstance(texto, BaseException) and not bruto.strip():
        bruto = type(texto).__name__

    limpo = _URL.sub(_ENDERECO, bruto)
    for padrao in _CREDENCIAIS:
        limpo = padrao.sub(_CREDENCIAL, limpo)
    limpo = _PAR_SECRETO.sub(lambda m: f"{m.group(1)}{m.group(2)}{_CREDENCIAL}", limpo)
    limpo = _ESPACO.sub(" ", limpo).strip()

    if len(limpo) > limite:
        limpo = limpo[: limite - 1].rstrip() + "…"
    return limpo
