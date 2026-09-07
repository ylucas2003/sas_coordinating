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
