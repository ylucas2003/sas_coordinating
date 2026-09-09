"""O código do QR da retirada presencial — assinar e ler (docs/40 §4).

O QR carrega um **token assinado**, e não o `aluno_id` cru. A diferença é o
produto inteiro: um print de tela com o uuid do aluno viraria crachá
reutilizável por qualquer pessoa e sobreviveria ao dia; um token de dois
minutos não vale nem para a fila seguinte.

⚠️ **`uso: "retirada"` é a razão de este módulo existir separado.** A chave é a
mesma que assina sessão (`auth.py`), então sem um claim de propósito um token
daqui seria um JWT válido para `get_current_user` — e um token de sessão seria
aceito no balcão. É exatamente a forma da vulnerabilidade do token de download
que virou sessão de coordenação (PR #7, docs/38 §1.1): **assinatura válida não é
identidade válida**. As duas pontas ficam fechadas porque cada lado exige o seu
claim — `get_current_user` exige `tipo` em `TIPOS_DE_SESSAO`, e `ler_retirada`
exige `uso` igual a `USO_DA_RETIRADA`.

Não há tabela de tokens nem rotina de limpeza, e isso é desenho: quem invalida
o código velho é a condição da própria leitura — o UPDATE condicional em
`retirado_em IS NULL` (docs/40 §4). Guardar tokens só acrescentaria uma segunda
verdade para envelhecer.
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt

from .auth import ALGORITHM
from .config import get_settings

#: Validade do código, em segundos. Curta de propósito: o QR fica na tela do
#: aluno, é fotografável, e a tela dele renova sozinha enquanto estiver visível
#: (docs/40 §6). Dois minutos cobrem a fila do balcão e não sobrevivem a um
#: print mandado no grupo.
SEGUNDOS_DE_VALIDADE = 120

#: O propósito do token. Ver o ⚠️ do docstring: é o que separa este código de
#: uma credencial de sessão assinada com a mesma chave.
USO_DA_RETIRADA = "retirada"

#: O que a confirmação precisa saber para achar a linha e conferir a cantina.
#: `aluno_id` viaja mesmo sendo derivável do pedido: é o recorte do evento de
#: tempo real, e relê-lo do banco só para publicar o aviso seria uma consulta a
#: mais no caminho mais apressado do produto (docs/40 §5).
CAMPOS = ("pedido_id", "cardapio_id", "aluno_id")


class RetiradaIlegivel(Exception):
    """Código adulterado, vencido, incompleto ou de outro propósito.

    Um tipo só para os quatro casos, e a rota devolve a MESMA frase para todos:
    dizer qual dos quatro falhou ajuda quem está tentando forjar, e não ajuda em
    nada quem está com o celular na mão. O `motivo` fica aqui para o log.
    """

    def __init__(self, motivo: str) -> None:
        super().__init__(motivo)
        self.motivo = motivo


def assinar_retirada(
    *,
    pedido_id: str,
    cardapio_id: str,
    aluno_id: str,
    agora: datetime | None = None,
) -> tuple[str, datetime]:
    """Devolve `(código, instante em que ele vence)`.

    O instante volta junto porque a tela do aluno precisa dele para renovar
    ANTES de vencer — recalcular a validade no cliente exigiria repetir a
    constante daqui em TypeScript, e as duas divergiriam na primeira mudança.
    """
    expira_em = (agora or datetime.now(UTC)) + timedelta(seconds=SEGUNDOS_DE_VALIDADE)
    conteudo = {
        "uso": USO_DA_RETIRADA,
        "pedido_id": pedido_id,
        "cardapio_id": cardapio_id,
        "aluno_id": aluno_id,
        "exp": expira_em,
    }
    return jwt.encode(conteudo, get_settings().jwt_secret_key, algorithm=ALGORITHM), expira_em


def ler_retirada(codigo: str) -> dict[str, str]:
    """Verifica assinatura, validade e propósito. Levanta `RetiradaIlegivel`.

    Fail-closed nas quatro portas, e a terceira não é zelo: o `jwt.decode` só
    confere `exp` se `exp` existir, então um token SEM validade passaria pela
    assinatura e valeria para sempre. Quem constrói o token é `assinar_retirada`,
    mas o verificador não pode depender de quem o chamou.
    """
    try:
        conteudo = jwt.decode(codigo, get_settings().jwt_secret_key, algorithms=[ALGORITHM])
    except JWTError as erro:
        raise RetiradaIlegivel("assinatura inválida ou código vencido") from erro

    if conteudo.get("uso") != USO_DA_RETIRADA:
        raise RetiradaIlegivel("token de outro propósito")
    if not conteudo.get("exp"):
        raise RetiradaIlegivel("código sem validade")

    faltando = [campo for campo in CAMPOS if not conteudo.get(campo)]
    if faltando:
        raise RetiradaIlegivel(f"código sem {', '.join(faltando)}")

    return {campo: str(conteudo[campo]) for campo in CAMPOS}


# ─── O código que gira a cada 10 segundos (docs/40 §12.9) ────────────────
#
# ⚠️ **O QR deixa de carregar o token, e passa a carregar um código derivado.**
#
# O token de 120 s resolve o print mandado no grupo DEPOIS do almoço; não
# resolve o print mandado agora, para quem está na fila ao lado. A resposta é
# um código que muda a cada 10 segundos — e o caminho direto para isso, baixar
# `SEGUNDOS_DE_VALIDADE` para 10, foi recusado por dois motivos medidos:
#
#   1. **não sobra folga para uma falha de rede.** O comentário do hook do
#      front descreve o caso real: com o wi-fi associado e sem rota (o handoff
#      de AP no corredor), o POST PENDURA em vez de rejeitar. Com 120 s dá
#      tempo de o erro aparecer enquanto o código velho ainda vale; com 10 s o
#      aluno fica sem QR na frente da fila;
#   2. **cada renovação é uma escrita.** Seis por minuto, por aluno com a tela
#      aberta, numa API de uma thread só (docs/40 §12.1.1).
#
# O desenho: o servidor entrega uma SEMENTE (que nunca entra no QR) e o
# aparelho deriva o código da janela de 10 s a partir dela, **sem rede**. O
# balcão lê `pedido.janela.codigo`; o servidor recalcula e compara.
#
# ⚠️ **A semente não vai no QR, e é isso que faz a rotação valer alguma coisa.**
# Se ela fosse, um print carregaria o material para derivar as janelas
# seguintes, e os 10 segundos seriam decoração. O print carrega só o código de
# UMA janela, que morre em 10 s.
#
# ⚠️ **O relógio do aparelho não entra na conta.** A resposta traz a janela
# inicial, e o cliente conta o tempo DECORRIDO a partir dela — não a hora do
# mundo. Um celular adiantado em três minutos gera o código certo, e some a
# tentação de aceitar também a janela seguinte, que é onde este tipo de desenho
# costuma abrir a fresta que queria fechar.

#: O tamanho da janela. Dez segundos: curto o bastante para um print não chegar
#: a outro aluno na fila, longo o bastante para a câmera do balcão focar.
SEGUNDOS_DA_JANELA = 10

#: Quantas janelas ATRÁS ainda são aceitas.
#:
#: ⚠️ Uma, e ela não é folga — é requisito. Entre o aluno mostrar e a câmera
#: focar passam segundos, e um código que morre no instante exato transformaria
#: a fila em repetição. Aceitar a janela ANTERIOR dá de 10 a 20 segundos de vida
#: real ao código; aceitar duas dobraria a janela de um print sem resolver nada
#: que a primeira já não resolva.
JANELAS_ACEITAS_ATRAS = 1

#: Caracteres do código no QR. Dez de um HMAC são ~52 bits: adivinhar um dentro
#: de uma janela de 10 s não é caminho — e o custo de errar é uma leitura
#: falhada, não um acesso.
TAMANHO_DO_CODIGO = 10


def semente_da_retirada(pedido_id: str) -> str:
    """O segredo que o APARELHO recebe, e que o QR nunca carrega.

    Derivada da chave do servidor, então não há nada para guardar: o servidor
    recalcula quando o balcão lê. E é presa ao `pedido_id` — a semente de um
    aluno não gera código para o pedido de outro.
    """
    return hmac.new(
        get_settings().jwt_secret_key.encode(),
        f"{USO_DA_RETIRADA}:{pedido_id}".encode(),
        hashlib.sha256,
    ).hexdigest()


def janela_de(agora: datetime | None = None) -> int:
    """O número da janela de 10 s em que este instante cai."""
    instante = agora or datetime.now(UTC)
    return int(instante.timestamp()) // SEGUNDOS_DA_JANELA


def codigo_da_janela(semente: str, janela: int) -> str:
    """O que aparece no QR, para uma janela. Cliente e servidor calculam igual."""
    bruto = hmac.new(semente.encode(), str(janela).encode(), hashlib.sha256).hexdigest()
    return bruto[:TAMANHO_DO_CODIGO]


def montar_qr(pedido_id: str, janela: int, codigo: str) -> str:
    """O conteúdo do QR: `pedido.janela.codigo`, e nada mais."""
    return f"{pedido_id}.{janela}.{codigo}"


def ler_qr_rotativo(conteudo: str, agora: datetime | None = None) -> str:
    """Devolve o `pedido_id` se o código serve; levanta `RetiradaIlegivel`.

    ⚠️ A ordem das checagens importa: a JANELA é conferida antes do código.
    Comparar o HMAC de uma janela de três horas atrás daria "código inválido" —
    verdade, e a frase errada para quem está no balcão com a tela velha.
    """
    partes = conteudo.strip().split(".")
    if len(partes) != 3:
        raise RetiradaIlegivel("código fora do formato")

    pedido_id, janela_bruta, codigo = partes
    if not pedido_id or not codigo:
        raise RetiradaIlegivel("código incompleto")

    try:
        janela = int(janela_bruta)
    except ValueError as erro:
        raise RetiradaIlegivel("janela ilegível") from erro

    atual = janela_de(agora)
    if not (atual - JANELAS_ACEITAS_ATRAS <= janela <= atual):
        raise RetiradaIlegivel("código de outra janela")

    esperado = codigo_da_janela(semente_da_retirada(pedido_id), janela)
    # `compare_digest` e não `==`: a comparação byte a byte de string vaza o
    # número de acertos pelo tempo. Aqui o ganho prático é pequeno, e o hábito
    # é o que importa — este é o único lugar do produto que compara segredo.
    if not hmac.compare_digest(esperado, codigo):
        raise RetiradaIlegivel("código não confere")

    return pedido_id
