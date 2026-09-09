"""A senha que o administrador escolhe, em vez da sorteada (docs/40 §12.7).

O pedido foi "ver as senhas da cantina e poder trocá-las". **Ver não é
possível** e não vai passar a ser: `usuario_cantina.senha_hash` e
`usuario_coordenacao.senha_hash` são PBKDF2 de mão única, e guardar texto
legível exporia contas que alcançam nome, turma e restrição alimentar de
menores.

O que resolve a necessidade sem guardar nada é o outro lado do pedido: deixar o
administrador **definir** a senha. Quem define, sabe — e a vontade de "ver"
era, na prática, a de conseguir dizer a senha para a cantina.

⚠️ **A régua vive aqui, e não em cada rota.** São duas telas de conta (a da
cantina e a da coordenação) e quatro rotas — criar e redefinir de cada uma. Uma
cópia da regra em cada uma é o desenho que garante que, no dia em que o mínimo
mudar, três lugares fiquem para trás.

⚠️ **A validação é do SERVIDOR.** O campo do front vai ter as mesmas regras,
mas campo de formulário é conveniência: quem manda `curl` não passa por ele. É
a mesma severidade de `_validar_configuracao` (main.py), que recusa o processo
subir com senha demo.
"""

import secrets
import unicodedata

from fastapi import HTTPException

#: Comprimento da senha SORTEADA. `token_urlsafe(12)` dá ~16 caracteres.
_BYTES_SORTEADOS = 12

#: O piso da senha DIGITADA.
#:
#: Doze, e não oito: estas contas não têm segundo fator, não têm bloqueio por
#: tentativa no nível da conta, e valem por oito horas de token. O número não é
#: recomendação de cartilha — é o que sobra depois de tirar as defesas que este
#: produto não tem.
MINIMO_DE_CARACTERES = 12

#: Senhas que alguém digita quando quer "só passar pela validação". A lista é
#: curta de propósito: ela não existe para ser exaustiva — isso é trabalho de
#: uma base de vazamentos —, mas para pegar o caso real de quem repete o nome
#: do produto ou aperta a mesma tecla.
_OBVIAS = frozenset({
    "123456789012", "senha12345678", "cantinacantina", "portalsasonline",
    "aridesaaridesa", "administrador", "coordenacao12",
})


def _normalizar(texto: str) -> str:
    """Sem acento e em minúsculas, para comparar com o e-mail e com a lista.

    `Cantina@2026` e `cantina2026` são a mesma ideia para quem ataca, e
    comparar byte a byte deixaria a segunda passar por ser diferente da
    primeira.
    """
    sem_acento = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in sem_acento if not unicodedata.combining(c))


def validar(senha: str, *, email: str) -> str:
    """Devolve a senha se ela serve; levanta 422 com o motivo se não serve.

    ⚠️ A mensagem diz **qual** regra falhou. Uma recusa genérica ("senha
    inválida") faz a pessoa tentar de novo às cegas, e quem tenta às cegas três
    vezes escolhe a quarta pior que a primeira.
    """
    senha = senha.strip()

    if len(senha) < MINIMO_DE_CARACTERES:
        raise HTTPException(
            status_code=422,
            detail=f"A senha precisa de pelo menos {MINIMO_DE_CARACTERES} caracteres.",
        )

    normalizada = _normalizar(senha)

    if normalizada in _OBVIAS:
        raise HTTPException(
            status_code=422,
            detail="Esta senha é fácil demais de adivinhar. Escolha outra.",
        )

    # O local do e-mail (`cantina` em `cantina@aridesa.com.br`) é a primeira
    # coisa que se tenta, e é justamente o que vem à cabeça de quem está
    # cadastrando a conta com o e-mail na tela ao lado.
    local = _normalizar(email.split("@")[0]) if "@" in email else _normalizar(email)
    if local and len(local) >= 4 and local in normalizada:
        raise HTTPException(
            status_code=422,
            detail="A senha não pode conter o e-mail da conta.",
        )

    if len(set(senha)) < 5:
        raise HTTPException(
            status_code=422,
            detail="A senha repete poucos caracteres diferentes. Escolha outra.",
        )

    return senha


def sortear() -> str:
    """A senha de quem não quer escolher. É o comportamento de sempre."""
    return secrets.token_urlsafe(_BYTES_SORTEADOS)


def resolver(senha: str | None, *, email: str) -> str:
    """A senha desta conta: a digitada, validada, ou uma sorteada.

    É a função que as quatro rotas chamam. `None` — o corpo não trouxe o campo,
    ou trouxe vazio — cai no sorteio, que é o contrato que já existia: nenhum
    cliente antigo precisa mudar para continuar funcionando.
    """
    if senha is None or not senha.strip():
        return sortear()
    return validar(senha, email=email)
