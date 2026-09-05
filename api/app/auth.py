"""Utilitários de autenticação JWT.

Quem entra, e por onde (docs/35 §11):

- **Aluno**: só pelo Canvas (`routes/auth_canvas.py`). Não existe mais senha de
  aluno no SAS — saíram em 04/09 o ramo `tipo == "aluno"` de `/auth/login`, a
  rota `/auth/primeiro-acesso`, `/alunos/{id}/resetar-acesso` e `POST /me/senha`
  (docs/35 §11.5). `verificar_senha` e `hash_senha` continuam aqui porque a
  coordenação usa.
  ⚠️ `aluno.senha_hash` virou FÓSSIL: guarda os hashes que já existiam, nenhuma
  rota autentica por ela nem escreve nela — `/administracao/alunos-acesso` só a
  lê como histórico (`primeiroAcessoFeito`) —, e o único escritor que restou é
  o script de operação `scripts/criar_acesso.py --matricula`, que hoje grava
  uma senha que não abre porta nenhuma. Quem for mexer ali: o caminho de acesso do
  aluno é o `canvas_user_id`, não esta coluna. Ela fica porque apagar perde
  dado sem ganhar nada.
- **Coordenação**: e-mail + senha na tabela `usuario_coordenacao` (0021), com
  o `papel` da 0045 dizendo o que a conta pode a mais.
- **Cantina**: e-mail + senha na tabela `usuario_cantina` (0047), pela mesma
  rota `/auth/login` com `tipo: "cantina"`. É um TIPO, não um papel de
  coordenação: um papel novo em `usuario_coordenacao` passaria por
  `get_current_coordenador` — que aceita todo papel de propósito — e abriria as
  39 rotas de coordenação para quem trabalha na copa (docs/38 §1).
- **Scheduler** (hoje o cron do VPS; o nome EventBridge é resíduo da migração):
  segredo compartilhado no header X-Scheduler-Secret, não JWT.

⚠️ **`tipo` e `papel` são coisas diferentes, e confundir os dois derruba
acesso.** `tipo` diz QUE TIPO DE SESSÃO é — aluno, coordenação ou cantina — e é o que
`chat/rotas.py`, `routes/foto_perfil.py` e o casco do front leem para escolher
namespace, tabela e tela. `papel` diz o que uma sessão de COORDENAÇÃO pode a
mais. Por isso o administrador tem `tipo: "coordenador"` e `papel:
"administrador"`, e não um `tipo` próprio: um `tipo: "administrador"` faria o
admin cair no `else` de cada um daqueles três lugares e perder o chat, a foto e
as 39 rotas de coordenação de uma vez — o oposto do que foi pedido (docs/35
§11.3).
"""

import hashlib
import hmac
import logging
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from .config import get_settings
from .supabase_client import get_supabase

log = logging.getLogger("sas.auth")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8  # 8 horas

# Os únicos `tipo` que representam uma SESSÃO de gente. Existe porque a
# `jwt_secret_key` não assina só sessão: `app/storage.py` a usava para o token
# de download de arquivo, e um token de download reapresentado como Bearer
# passava por `get_current_user` — que só olhava assinatura e `exp` — e caía no
# `else` do chat, ganhando o perfil de COORDENAÇÃO com as tools que leem
# qualquer aluno. Assinatura válida não é identidade válida; o `tipo` é que diz
# para que o token serve.
#
# ⚠️ **Acrescentar um tipo aqui NÃO é uma linha.** Todo lugar que dividia o
# mundo em "aluno" e "todo o resto" passa a estar errado no instante em que um
# terceiro existe. Quando a cantina entrou (05/09, docs/38 §1.1) foram três, e
# os três foram consertados junto com esta linha:
#   * `routes/foto_perfil.py` — caía num `return` de coordenação por omissão, o
#     que daria à cantina acesso de ESCRITA a `usuario_coordenacao`;
#   * `web/src/App.tsx` — montava o casco da coordenação para o que não fosse aluno;
#   * `web/src/servicos/sessao.ts` — sem o tipo na lista, a sessão nasce morta.
# `chat/rotas.py` já era fail-closed e por isso não precisou de conserto: a
# cantina simplesmente não tem chat, que é o comportamento certo.
TIPOS_DE_SESSAO = frozenset({"aluno", "coordenador", "cantina"})

# Os papéis de uma sessão de COORDENAÇÃO (coluna `papel`, migration 0045).
# Administrador não é um `tipo` — ver o ⚠️ do docstring do módulo.
PAPEIS_DE_COORDENACAO = frozenset({"coordenador", "administrador"})

# Hash de senha: pbkdf2_sha256$<iteracoes>$<salt_hex>$<hash_hex>.
# O prefixo identifica algoritmo+parâmetros gravados no próprio hash, então
# mudar as constantes abaixo não invalida senhas existentes.
PBKDF2_ITERACOES = 600_000
_PREFIXO_HASH = "pbkdf2_sha256"

_bearer = HTTPBearer(auto_error=False)


def hash_senha(senha: str) -> str:
    salt = secrets.token_hex(16)
    derivado = hashlib.pbkdf2_hmac(
        "sha256", senha.encode(), bytes.fromhex(salt), PBKDF2_ITERACOES
    )
    return f"{_PREFIXO_HASH}${PBKDF2_ITERACOES}${salt}${derivado.hex()}"


def verificar_senha(senha: str, senha_hash: str | None) -> bool:
    """Confere a senha contra o hash armazenado.

    NULL ou formato desconhecido (ex.: md5 legado zerado pela migration 0012)
    nunca autenticam.
    """
    if not senha_hash:
        return False
    partes = senha_hash.split("$")
    if len(partes) != 4 or partes[0] != _PREFIXO_HASH:
        return False
    _, iteracoes_str, salt, esperado = partes
    try:
        iteracoes = int(iteracoes_str)
        derivado = hashlib.pbkdf2_hmac(
            "sha256", senha.encode(), bytes.fromhex(salt), iteracoes
        )
    except ValueError:
        return False
    return hmac.compare_digest(derivado.hex(), esperado)


def criar_token(data: dict, expires_delta: timedelta | None = None) -> str:
    settings = get_settings()
    payload = data.copy()
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload["exp"] = expire
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=ALGORITHM)


def _decodificar(token: str) -> dict:
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[ALGORITHM])


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autenticado"
        )
    try:
        payload = _decodificar(credentials.credentials)
    except JWTError:
        # `from None`: o motivo exato (assinatura, algoritmo, expiração) é
        # informação para o log, não para quem apresentou o token.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado",
        ) from None

    # Fail-closed: tipo desconhecido, ausente ou de capacidade (download) não
    # abre sessão. É aqui, e não em cada consumidor, porque a garantia tem que
    # valer para toda rota que dependa desta função — inclusive as que ainda
    # não existem.
    if payload.get("tipo") not in TIPOS_DE_SESSAO:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado",
        )

    return payload


async def get_current_aluno(user: dict = Depends(get_current_user)) -> dict:
    if user.get("tipo") != "aluno":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a alunos autenticados",
        )
    return user


def papel_da_sessao(user: dict) -> str | None:
    """O papel de uma sessão de coordenação, ou None se não for uma.

    Um token de coordenação SEM `papel` vale como coordenador. Não é
    tolerância a dado ruim: os tokens valem 8 horas, então na virada da chave
    há sessões em circulação emitidas antes da 0045 — e a alternativa
    (recusar) deslogaria a coordenação inteira no meio do expediente. Cair
    para o papel MENOS poderoso é o lado seguro: um token velho não vira
    administrador, só continua coordenador.
    """
    if user.get("tipo") != "coordenador":
        return None
    papel = user.get("papel")
    return papel if papel in PAPEIS_DE_COORDENACAO else "coordenador"


async def get_current_coordenador(user: dict = Depends(get_current_user)) -> dict:
    """Guard de TODA tela de coordenação — 39 usos em 10 arquivos de rota.

    Aceita os DOIS papéis de propósito: administrador é coordenador com mais
    poderes, não outro cargo. Exigir `papel == "coordenador"` aqui trancaria o
    administrador fora de tudo que ele já usa todo dia (docs/35 §11.3).
    """
    if papel_da_sessao(user) is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito à coordenação",
        )
    return user


def conta_ainda_e_administradora(usuario_id: str | None) -> bool:
    """Reconfere o papel na TABELA, e não só no claim do token.

    Existe porque o `papel` viaja num token de 8 horas. Sem esta releitura,
    rebaixar um administrador (`PATCH /administracao/coordenadores/{id}/papel`)
    não tiraria poder nenhum até o token dele vencer — e, dentro dessa janela,
    o rebaixado ainda poderia criar OUTRA conta de administrador e desfazer a
    decisão. Rebaixamento que só vale daqui a 8 horas não é rebaixamento.

    Só as rotas de ADMINISTRADOR pagam esta leitura. As de coordenação
    continuam decidindo pelo token sozinho, de propósito: quem foi rebaixado
    **continua coordenador**, e derrubar a sessão dele por inteiro seria punir
    um trabalho que ele segue tendo direito de fazer.

    `ativo` entra na mesma pergunta pelo mesmo motivo: desativar a conta de um
    administrador tem que fechar a porta agora, não no fim do expediente.

    Fail-closed em tudo — linha ausente, conta desativada, papel trocado ou
    erro de leitura recusam. Numa base sem a migration 0045 ninguém chega até
    aqui: sem a coluna, `/auth/login` não emite token de administrador
    (`routes/auth.py:_buscar_conta`).
    """
    if not usuario_id:
        return False
    try:
        linhas = (
            get_supabase()
            .table("usuario_coordenacao")
            .select("papel, ativo")
            .eq("id", usuario_id)
            .limit(1)
            .execute()
            .data
        ) or []
    except Exception:
        log.warning("nao consegui reconferir o papel da conta", exc_info=True)
        return False
    if not linhas:
        return False
    return linhas[0].get("ativo") is True and linhas[0].get("papel") == "administrador"


async def get_current_administrador(
    user: dict = Depends(get_current_coordenador),
) -> dict:
    """O que só o administrador pode: criar/editar conta de login, mudar o
    papel de outra conta e alterar nota pelo painel (docs/35 §11.7).

    Depende de `get_current_coordenador` para a recusa vir na ordem certa —
    quem não é da coordenação leva o 403 genérico, e não uma mensagem que
    revela a existência de um papel de administrador.

    São DUAS perguntas, e as duas precisam ser feitas: o token diz que a
    sessão foi aberta como administrador, e a tabela diz se ela ainda é —
    ver `conta_ainda_e_administradora`.
    """
    if papel_da_sessao(user) != "administrador":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Esta ação é restrita ao administrador do SAS.",
        )
    if not conta_ainda_e_administradora(user.get("sub")):
        # Mensagem diferente da de cima de propósito: quem lê esta já era
        # administrador quando entrou, e precisa saber que a sessão é que
        # está velha — senão fica achando que a tela quebrou.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Sua conta não é mais administradora do SAS. "
                "Saia e entre de novo para atualizar o acesso."
            ),
        )
    return user


async def get_current_cantina(user: dict = Depends(get_current_user)) -> dict:
    """Guard de toda rota da cantina.

    Não aceita coordenação: a coordenação LÊ o cardápio por rotas próprias
    (`get_current_coordenador`), e deixar um coordenador publicar cardápio em
    nome da cantina apagaria a autoria de `cardapio.criado_por`.

    O `cantina_id` vem do token, e é por isso que ele existe como claim: toda
    consulta filtra por ele, nunca por parâmetro de URL — senão uma cantina lê
    o cardápio da outra trocando um id (docs/38 §3.3).
    """
    if user.get("tipo") != "cantina":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito à cantina",
        )
    if not user.get("cantina_id"):
        # Fail-closed: token de cantina sem estabelecimento não filtra nada, e
        # "não filtra nada" numa rota que lista cardápio é vazamento entre
        # cantinas. Só acontece com token emitido por uma versão anterior.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token sem identidade de cantina",
        )
    return user


async def exigir_scheduler_secret(
    x_scheduler_secret: str | None = Header(default=None, alias="X-Scheduler-Secret"),
) -> None:
    """Autentica chamadas máquina-a-máquina do scheduler (AWS EventBridge).

    O mesmo valor vive em SCHEDULER_SECRET (backend) e no parâmetro SSM
    /sas/scheduler/secret (AWS) — ver infra/README.md. Sem o secret
    configurado no ambiente, as rotas agendadas ficam indisponíveis (503)
    em vez de abertas.
    """
    settings = get_settings()
    if not settings.scheduler_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SCHEDULER_SECRET não configurado no servidor",
        )
    if not x_scheduler_secret or not hmac.compare_digest(
        x_scheduler_secret, settings.scheduler_secret
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="scheduler secret inválido",
        )
