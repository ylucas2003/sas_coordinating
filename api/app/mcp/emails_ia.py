"""O e-mail da conta de IA e o código que aprova a conexão OAuth (decisão do dono, 26/10).

O claude.ai e o ChatGPT não dizem ao SAS qual é a conta de quem conecta, e a
tela de consentimento abre no browser em que a IA está — que nem sempre tem
sessão do SAS. Por isso a prova de quem aprova deixou de ser a sessão e passou
a ser a POSSE de um e-mail: o coordenador cadastra, no card "Conexões de IA",
o e-mail da conta de IA dele, que pode não ser o do SAS e pode ser mais de um
(routes/mcp_emails_ia.py); o pedido de conexão só é aprovado com um código de
6 dígitos enviado a esse e-mail (routes/oauth_mcp.py), e a conexão nasce em
nome do coordenador DONO do e-mail. O cadastro também prova a posse: o e-mail
só vale depois de confirmado com outro código desses, digitado no card por
quem o cadastrou (revisão de segurança de 26/10).

Este módulo é a parte PURA disso — sem I/O, testável sem banco: a forma do
e-mail, o código, os hashes, a máscara que vai para a trilha e o texto da
mensagem. Mora em app/mcp/ porque é do MCP, mas só a API o usa: a chave dos
hashes deriva da JWT_SECRET_KEY, que o processo do MCP não pode ter
(configuracao.segredos_da_api_no_ambiente). Nada aqui importa o SDK.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from datetime import timedelta

#: Seis dígitos: cabem de cabeça entre a caixa de entrada e a tela. Com 5
#: tentativas por código, quem chuta acerta 5 em um milhão — e o teto de
#: códigos por e-mail (ConfiguracaoMcp.oauth_codigos_por_email_por_dia) é o
#: que segura a soma.
TAMANHO_DO_CODIGO = 6
#: O mesmo prazo do pedido e do código do OAuth (RFC 6749 §4.1.2): mais que
#: isso, o pedido já venceu de qualquer jeito.
VALIDADE_DO_CODIGO = timedelta(minutes=10)
#: Depois disto o código não vale mais, nem o certo — o CHECK da 0073
#: (`tentativas BETWEEN 0 AND 5`) diz o mesmo número.
TENTATIVAS_POR_CODIGO = 5

#: O teto do RFC 5321 para um caminho de e-mail, e o do CHECK da 0073.
MAXIMO_DO_EMAIL = 254
_MAXIMO_DA_PARTE_LOCAL = 64

#: O "valid e-mail address" do HTML (WHATWG) — o mesmo que o `<input
#: type="email">` da tela aceita —, com UMA diferença: o domínio precisa de um
#: ponto. "ana@gmail" é válido para o browser e não chega a caixa nenhuma pelo
#: SES. Só ASCII: um e-mail com letra parecida de outro alfabeto seria outro
#: e-mail que a tela mostra igual.
_EMAIL = re.compile(
    r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+"
    r"@[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+"
)
#: O que se tira do código digitado antes de conferir: quem copia "123 456" ou
#: "123-456" de um e-mail digitou o código certo.
_SEPARADORES_DO_CODIGO = re.compile(r"[\s.-]+")

#: Separa os papéis da chave: o HMAC do e-mail nunca é comparável ao do
#: código, nem a outro uso da JWT_SECRET_KEY. "v1" deixa trocar o esquema sem
#: confundir linha velha com nova.
_RAIZ_DA_CHAVE = b"sas/mcp/codigo-por-email/v1"


def normalizar_email(texto: str) -> str:
    """Sem espaço nas pontas e em minúsculas: "Ana@Gmail.com " é a mesma
    caixa que "ana@gmail.com" para quem a lê, e o cadastro guarda um só."""
    return texto.strip().lower()


def email_valido(email: str) -> bool:
    """Se o e-mail JÁ normalizado tem a forma de um endereço que o SES entrega."""
    if not email or len(email) > MAXIMO_DO_EMAIL or _EMAIL.fullmatch(email) is None:
        return False
    local = email.split("@", 1)[0]
    return len(local) <= _MAXIMO_DA_PARTE_LOCAL


def mascarar_email(email: str) -> str:
    """O e-mail como vai para a trilha e para o log: a primeira letra e o
    domínio ("a***@gmail.com"). A trilha guarda quem e quando, não contato
    (app/auditoria.py); com o id do cadastro ao lado, quem administra acha o
    resto no SAS."""
    local, arroba, dominio = email.partition("@")
    if not arroba or not local:
        return "***"
    return f"{local[0]}***@{dominio}"


def gerar_codigo() -> str:
    """Seis dígitos de `secrets`, com zero à esquerda: "004217" é um código."""
    return f"{secrets.randbelow(10**TAMANHO_DO_CODIGO):0{TAMANHO_DO_CODIGO}d}"


def codigo_no_formato(texto: str) -> str | None:
    """O código digitado sem os separadores, se for de seis dígitos; senão None."""
    limpo = _SEPARADORES_DO_CODIGO.sub("", texto or "")
    if len(limpo) == TAMANHO_DO_CODIGO and limpo.isascii() and limpo.isdigit():
        return limpo
    return None


def chave_dos_hashes(segredo: str) -> bytes:
    """A chave do HMAC dos e-mails e dos códigos, derivada do segredo da API.

    HMAC com chave, e não sha256 puro como o resto do OAuth: o código tem só um
    milhão de valores, e quem lesse o banco acharia o sha256 dele num segundo.
    Sem a chave, que mora no ambiente da API e não no banco, o hash não diz
    nada. O que sai desta chave nunca vai a lugar nenhum além do banco — o
    e-mail leva o código, que é aleatório —, então ela não vira oráculo do
    segredo de sessão (o cuidado de main.py com o LEMBRETE_TOKEN_SECRET).
    """
    return hmac.new(segredo.encode(), _RAIZ_DA_CHAVE, hashlib.sha256).digest()


def hash_do_email(chave: bytes, email: str) -> str:
    """O e-mail DIGITADO, como a 0073 o guarda: o /codigo grava uma linha para
    qualquer e-mail, cadastrado ou não, e o que alguém digitou não fica em claro."""
    return hmac.new(chave, b"email\x00" + email.encode(), hashlib.sha256).hexdigest()


def hash_do_codigo(chave: bytes, pedido_id: str, hash_email: str, codigo: str) -> str:
    """O código preso ao pedido E ao e-mail: o mesmo código noutro pedido, ou
    com outro e-mail, dá outro hash — e não aprova nada."""
    mensagem = f"codigo\x00{pedido_id}\x00{hash_email}\x00{codigo}".encode()
    return hmac.new(chave, mensagem, hashlib.sha256).hexdigest()


# ─── A confirmação do cadastro (revisão de segurança de 26/10) ───────────
#
# O cadastro no card também prova a posse: o e-mail nasce aguardando, recebe
# um código, e só vale depois que quem o cadastrou o digita no card, logado
# (routes/mcp_emails_ia.py, regra 0). É o MESMO mecanismo do código de
# aprovar — seis dígitos, o prazo e as tentativas daqui —, preso ao cadastro em
# vez de a um pedido.


def hash_da_confirmacao(chave: bytes, email_id: str, email: str, codigo: str) -> str:
    """O código de confirmação preso ao CADASTRO e ao e-mail dele: o mesmo
    código noutro cadastro — de outra conta, ou o mesmo endereço cadastrado de
    novo — dá outro hash, e não confirma nada. O prefixo separa este HMAC do
    código de aprovar (`hash_do_codigo`), que usa a mesma chave."""
    mensagem = f"confirmacao\x00{email_id}\x00{email}\x00{codigo}".encode()
    return hmac.new(chave, mensagem, hashlib.sha256).hexdigest()


def mensagem_de_confirmacao(codigo: str) -> tuple[str, str]:
    """(assunto, corpo) do e-mail que confirma o cadastro, em texto puro.

    O código vai no CORPO, como no de aprovar. O corpo diz o que confirmar
    significa — quem lê esta caixa passa a conectar IA com o acesso da conta —,
    porque é essa a frase que faz o dono de uma caixa que recebeu o código por
    engano (o e-mail digitado errado) não repassá-lo. O nome de quem cadastrou
    fica de fora: no engano, ele iria para um estranho.
    """
    minutos = int(VALIDADE_DO_CODIGO.total_seconds() // 60)
    assunto = "Código para confirmar o e-mail da sua IA no SAS"
    corpo = (
        "Este é o código para confirmar este endereço como e-mail de conta de IA no SAS:\n\n"
        f"    {codigo}\n\n"
        f"Ele vale por {minutos} minutos. Digite-o no SAS, em Administração › Conexões de IA, "
        "na linha deste e-mail.\n\n"
        "Confirmado, este e-mail passa a aprovar conexões de apps de IA (como o claude.ai e o "
        "ChatGPT) com o acesso da conta da coordenação que o cadastrou: quem lê esta caixa "
        "conecta uma IA aos dados do SAS.\n\n"
        "Se não foi você quem cadastrou este e-mail agora, não digite nem repasse o código — sem "
        "ele, o cadastro não vale — e avise quem administra o SAS.\n"
    )
    return assunto, corpo


def mensagem_do_codigo(codigo: str, host_de_volta: str) -> tuple[str, str]:
    """(assunto, corpo) do e-mail, em texto puro.

    O código vai no CORPO, não no assunto: o assunto aparece na tela bloqueada
    do celular. O nome que o app declarou fica de fora — é texto livre de quem
    se cadastrou, e o e-mail sai em nome da escola; o host de volta vai, porque
    é ele que a pessoa compara com a tela antes de aprovar (oauth_mcp._host_de_volta).

    Leva o "nunca compartilhe nem repasse" de todo OTP (revisão de segurança de
    26/10): como aprovar não pede sessão do SAS e quem chama o /aprovar recebe o
    código do RFC, o único obstáculo entre um phishing e o acesso aos dados dos
    alunos é a pessoa não entregar os seis dígitos a quem pediu — e o aviso é o
    que a prepara para não entregar.
    """
    minutos = int(VALIDADE_DO_CODIGO.total_seconds() // 60)
    assunto = "Código para conectar uma IA ao SAS"
    corpo = (
        "Este é o código para aprovar a conexão de um app de IA ao SAS:\n\n"
        f"    {codigo}\n\n"
        f"Ele vale por {minutos} minutos, só para o pedido aberto agora na tela "
        "\"Conectar uma IA ao SAS\".\n"
        f"O app que pediu volta para: {host_de_volta}\n\n"
        "Ao aprovar, esse app passa a ler os dados do SAS com o acesso da sua conta da "
        "coordenação, até a conexão ser revogada em Conexões de IA.\n\n"
        "Nunca compartilhe nem repasse este código com ninguém. Quem digita o código aprova a "
        "conexão: o SAS nunca pede que você diga ou encaminhe estes dígitos.\n\n"
        "Se não foi você quem pediu, ignore este e-mail — sem o código ninguém aprova — "
        "e avise quem administra o SAS.\n"
    )
    return assunto, corpo
