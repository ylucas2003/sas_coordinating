"""Os dois papéis da coordenação: quem passa por qual guard (docs/35 §11.3, §11.7).

A mudança de 04/09 partiu o acesso da coordenação em dois — `coordenador` e
`administrador` — e entrou sem teste nenhum de papel. O risco número 1 do
próprio plano é "trancar coordenador fora" (docs/35 §13), e há três jeitos
conhecidos de fazer isso sem que nada quebre:

  1. **A armadilha central.** Trocar `papel_da_sessao(user) is None` por
     `papel_da_sessao(user) == "coordenador"` em `get_current_coordenador`
     parece o conserto óbvio de quem lê o nome da função — e tranca o
     ADMINISTRADOR fora de TODA rota de coordenação (49 no app de 04/09),
     porque administrador é coordenador com mais poderes, não outro cargo.
  2. **Token legado.** Os tokens valem 8 h; na virada da chave havia sessões em
     circulação emitidas antes da 0045, sem o claim `papel`. Recusá-las
     deslogaria a coordenação inteira no meio do expediente.
  3. **Piso errado numa rota nova.** `/administracao` é DIVIDIDO: o router
     exige coordenação e só as rotas de CONTA exigem administrador. O
     `PISO_ESPERADO` daqui é a régua — rota nova quebra o teste até alguém
     declarar de que lado ela fica.

E há um quarto, que não é de papel mas cai no mesmo lugar: `/auth/login`
morrendo quando a coluna `papel` não existe na base (G7). Os três últimos
testes cobrem isso.

Desde 05/09 o papel também MUDA pela tela (`PATCH .../coordenadores/{id}/papel`),
e isso trouxe um risco novo, na direção contrária: rebaixar sem efeito. O
`papel` viaja num token de 8 h, então um ex-administrador com sessão aberta
poderia criar outra conta de administrador e desfazer a própria queda. Por
isso o guard passou a reler a tabela, e por isso todo teste daqui roda contra
um `FakeCliente` — o guard deixou de ser função pura sobre o payload.

Chamamos as dependências direto, com um dict de sessão, e o handler da rota de
papel do mesmo jeito: passar por HTTP só acrescentaria ruído. A cadeia
real (`get_current_administrador` depende de `get_current_coordenador`) é
reproduzida à mão em `_pela_cadeia_de_administrador`, e há um teste separado
garantindo que ela continua sendo essa.

Rodar:  cd api && ./.venv/bin/python -m pytest tests/test_papeis.py -q
"""

import asyncio
import inspect

import pytest
from fastapi import HTTPException
from postgrest.exceptions import APIError
from pydantic import ValidationError

from app import auth
from app.routes import administracao, notas
from app.routes import auth as rotas_auth
from tests.fake_postgrest import FakeCliente

SEGREDO = "segredo-de-teste-com-mais-de-32-caracteres"

# Sessões como elas chegam no payload do JWT.
ADMINISTRADOR = {"sub": "u-1", "tipo": "coordenador", "papel": "administrador"}
COORDENADOR = {"sub": "u-2", "tipo": "coordenador", "papel": "coordenador"}
COORDENADOR_LEGADO = {"sub": "u-3", "tipo": "coordenador"}  # token emitido antes da 0045
ALUNO = {"sub": "a-1", "tipo": "aluno", "aluno_id": "a-1"}


def _contas() -> dict:
    """As mesmas quatro sessões acima, agora como linhas da tabela.

    O guard de administrador deixou de decidir só pelo token: ele reconfere o
    papel em `usuario_coordenacao` (`auth.conta_ainda_e_administradora`), para
    que rebaixar valha na hora e não quando o token vencer.
    """
    return {
        "usuario_coordenacao": {
            "u-1": {"id": "u-1", "nome": "Admin", "email": "admin@ari.com.br",
                    "papel": "administrador", "ativo": True},
            "u-2": {"id": "u-2", "nome": "Coord", "email": "coord@ari.com.br",
                    "papel": "coordenador", "ativo": True},
            "u-3": {"id": "u-3", "nome": "Legado", "email": "legado@ari.com.br",
                    "papel": "coordenador", "ativo": True},
        },
        "evento_auditoria": {},
    }


@pytest.fixture(autouse=True)
def banco(monkeypatch) -> dict:
    """O banco falso de TODO teste deste arquivo — autouse, e pedível por nome.

    Autouse porque nenhum teste daqui pode falar com Postgres de verdade: o
    guard de administrador tentaria abrir conexão, cairia no fail-closed do
    `except` e o teste passaria (ou falharia) pelo motivo errado — que é
    justamente o tipo de coisa que este arquivo existe para não deixar passar.

    `auth` E `administracao` recebem o MESMO cliente: é o que permite chamar a
    rota de rebaixamento e, na sequência, o guard, e ver o segundo enxergar o
    que a primeira escreveu.
    """
    db = _contas()
    monkeypatch.setattr(auth, "get_supabase", lambda: FakeCliente(db))
    monkeypatch.setattr(administracao, "get_supabase", lambda: FakeCliente(db))
    return db


def _como_coordenador(sessao: dict) -> dict:
    return asyncio.run(auth.get_current_coordenador(user=sessao))


def _pela_cadeia_de_administrador(sessao: dict) -> dict:
    """O que o FastAPI faz: resolve o guard de coordenação e só então o de admin.

    Chamar `get_current_administrador` sozinho pularia o primeiro — e é o
    primeiro que decide a MENSAGEM que quem não é da coordenação recebe.
    """

    async def cadeia() -> dict:
        return await auth.get_current_administrador(
            user=await auth.get_current_coordenador(user=sessao)
        )

    return asyncio.run(cadeia())


# ─── Os guards ────────────────────────────────────────────────────────────


def test_administrador_passa_pelo_guard_de_coordenacao():
    """A armadilha 1. Se este teste cair, o administrador perde as 50 rotas de
    coordenação — as 45 do piso comum E as 5 que são só dele, porque
    `get_current_administrador` passa por este guard primeiro."""
    assert _como_coordenador(ADMINISTRADOR) is ADMINISTRADOR
    assert auth.papel_da_sessao(ADMINISTRADOR) == "administrador"


def test_administrador_passa_pelo_guard_de_administrador():
    assert _pela_cadeia_de_administrador(ADMINISTRADOR) is ADMINISTRADOR


def test_coordenador_puro_leva_403_no_guard_de_administrador():
    _como_coordenador(COORDENADOR)  # o piso ele tem
    with pytest.raises(HTTPException) as erro:
        _pela_cadeia_de_administrador(COORDENADOR)
    assert erro.value.status_code == 403
    assert "administrador" in erro.value.detail.lower()


def test_token_legado_sem_papel_vale_como_coordenador():
    """Armadilha 2: token de 8 h emitido antes da 0045 continua entrando —
    como coordenador, nunca como administrador."""
    assert auth.papel_da_sessao(COORDENADOR_LEGADO) == "coordenador"
    assert _como_coordenador(COORDENADOR_LEGADO) is COORDENADOR_LEGADO
    with pytest.raises(HTTPException) as erro:
        _pela_cadeia_de_administrador(COORDENADOR_LEGADO)
    assert erro.value.status_code == 403


def test_papel_desconhecido_no_token_cai_para_coordenador():
    """Fail-closed: `papel` que o guard não reconhece não vira administrador."""
    inventado = {"sub": "u-4", "tipo": "coordenador", "papel": "superadmin"}
    assert auth.papel_da_sessao(inventado) == "coordenador"
    with pytest.raises(HTTPException):
        _pela_cadeia_de_administrador(inventado)


def test_aluno_nao_passa_por_nenhum_dos_dois_guards():
    for chamada in (_como_coordenador, _pela_cadeia_de_administrador):
        with pytest.raises(HTTPException) as erro:
            chamada(ALUNO)
        assert erro.value.status_code == 403
        assert erro.value.detail == "Acesso restrito à coordenação"
    assert auth.papel_da_sessao(ALUNO) is None


def test_administrador_nao_e_um_tipo_de_sessao():
    """O ⚠️ de `app/auth.py`: se alguém trocar o `tipo` do token por
    "administrador", o admin deixa de ser coordenação para TODO guard."""
    assert "administrador" not in auth.TIPOS_DE_SESSAO
    sessao_torta = {"sub": "u-5", "tipo": "administrador", "papel": "administrador"}
    assert auth.papel_da_sessao(sessao_torta) is None
    with pytest.raises(HTTPException):
        _como_coordenador(sessao_torta)


def test_guard_de_administrador_continua_pendurado_no_de_coordenacao():
    """A ordem da recusa depende disso: quem não é da coordenação tem que levar
    o 403 genérico, e não uma mensagem que revela a existência do papel."""
    parametro = inspect.signature(auth.get_current_administrador).parameters["user"]
    assert parametro.default.dependency is auth.get_current_coordenador


# ─── A porta de ENTRADA do papel ──────────────────────────────────────────


def test_conta_nasce_coordenador_quando_o_papel_nao_e_dito():
    """O outro lado do fail-closed: quem esquece o campo cria a conta MENOS
    poderosa (`CriarCoordenadorBody`, administracao.py)."""
    corpo = administracao.CriarCoordenadorBody(email="novo@ari.com.br", nome="Novo")
    assert corpo.papel == "coordenador"
    assert (
        administracao.CriarCoordenadorBody(
            email="chefe@ari.com.br", nome="Chefe", papel="ADMINISTRADOR "
        ).papel
        == "administrador"
    )


def test_papel_inventado_nao_entra_pela_rota_de_criar_conta():
    """Barrado aqui E no banco (CHECK da 0045): sem as duas barreiras, um
    `papel: "admin"` entraria calado e a conta ficaria sem poder nenhum,
    porque o guard compara string exata."""
    with pytest.raises(ValidationError):
        administracao.CriarCoordenadorBody(
            email="x@ari.com.br", nome="X", papel="superadmin"
        )


# ─── A matriz das rotas ───────────────────────────────────────────────────

# Piso de cada rota de `/administracao` — o que o docstring do módulo chama de
# "DIVIDIDO, não promovido inteiro". Listar quem é de conta E quem não é é o
# ponto: uma rota nova cai neste teste até alguém dizer de que lado ela fica.
PISO_ESPERADO = {
    ("GET", "/administracao/coordenadores"): "coordenador",
    ("POST", "/administracao/coordenadores"): "administrador",
    ("PATCH", "/administracao/coordenadores/{usuario_id}"): "administrador",
    ("PATCH", "/administracao/coordenadores/{usuario_id}/papel"): "administrador",
    ("POST", "/administracao/coordenadores/{usuario_id}/redefinir-senha"): "administrador",
    ("GET", "/administracao/alunos-acesso"): "coordenador",
    ("GET", "/administracao/coordenadores/{usuario_id}/foto"): "coordenador",
}


def _piso(rota) -> str:
    """O guard mais alto que a rota realmente atravessa.

    Anda a árvore de dependências já montada pelo FastAPI — e não a lista do
    decorador — porque é lá que a dependência declarada no `APIRouter` aparece
    junto com as da rota. Ler só o decorador diria que `GET /coordenadores` não
    tem guard nenhum.
    """
    nomes, pilha = set(), [rota.dependant]
    while pilha:
        dependencia = pilha.pop()
        if dependencia.call is not None:
            nomes.add(getattr(dependencia.call, "__name__", ""))
        pilha.extend(dependencia.dependencies)
    if "get_current_administrador" in nomes:
        return "administrador"
    if "get_current_coordenador" in nomes:
        return "coordenador"
    return "SEM GUARD"


def _matriz(router) -> dict:
    return {
        (sorted(rota.methods)[0], rota.path): _piso(rota)
        for rota in router.routes
    }


def test_matriz_de_administracao():
    assert _matriz(administracao.router) == PISO_ESPERADO


def test_nenhuma_rota_de_administracao_fica_sem_guard():
    """O router inteiro tem piso de coordenação — nada aqui é público, e nada
    aqui é de aluno."""
    assert "SEM GUARD" not in set(_matriz(administracao.router).values())


# ─── Promover e rebaixar (docs/35 §11.7, 05/09) ───────────────────────────
#
# A decisão original era que papel só mudava por `scripts/criar_coordenador.py
# --papel`, na linha de comando do VPS. Na prática isso queria dizer que
# REBAIXAR não acontecia — e rebaixar é a metade que tem hora marcada. A troca
# passou a existir pela tela, com quatro travas, e são elas que estes testes
# guardam: rota separada, papel validado, ninguém mexe no próprio papel, e o
# token do rebaixado deixa de valer na hora.


class _Pedido:
    """Só o que o handler lê de `Request`."""

    def __init__(self, ip: str | None = "203.0.113.7"):
        self.client = type("C", (), {"host": ip})()


def _mudar_papel(usuario_id: str, papel: str, sessao: dict = ADMINISTRADOR) -> dict:
    return asyncio.run(
        administracao.alterar_papel_do_coordenador(
            usuario_id=usuario_id,
            body=administracao.PapelDoCoordenadorBody(papel=papel),
            request=_Pedido(),
            administrador=sessao,
        )
    )


def test_promover_coordenador_a_administrador(banco):
    resposta = _mudar_papel("u-2", "administrador")
    assert resposta["papel"] == "administrador"
    assert banco["usuario_coordenacao"]["u-2"]["papel"] == "administrador"


def test_rebaixar_administrador_a_coordenador(banco):
    banco["usuario_coordenacao"]["u-2"]["papel"] = "administrador"
    assert _mudar_papel("u-2", "coordenador")["papel"] == "coordenador"
    assert banco["usuario_coordenacao"]["u-2"]["papel"] == "coordenador"


def test_a_troca_de_papel_vira_evento_proprio_na_auditoria(banco):
    _mudar_papel("u-2", "administrador")
    eventos = list(banco["evento_auditoria"].values())
    assert [e["acao"] for e in eventos] == ["papel_alterado"]
    evento = eventos[0]
    # O par que a tela de auditoria já desenha como "antes → depois". Sem ele,
    # promover e rebaixar viram duas linhas idênticas na trilha.
    assert evento["detalhe"]["valor_antes"] == "coordenador"
    assert evento["detalhe"]["valor_depois"] == "administrador"
    assert evento["ator_id"] == "u-1"
    assert evento["recurso"] == "coordenador/u-2"


def test_ninguem_muda_o_proprio_papel(banco):
    """A trava que garante que sempre reste um administrador: quem chama já é
    um, e sai daqui continuando um. Sem ela o último administrador se rebaixa e
    a casa fica sem quem cria login — nem para desfazer."""
    with pytest.raises(HTTPException) as erro:
        _mudar_papel("u-1", "coordenador")
    assert erro.value.status_code == 422
    assert banco["usuario_coordenacao"]["u-1"]["papel"] == "administrador"


def test_trocar_para_o_papel_que_a_conta_ja_tem_e_recusado():
    with pytest.raises(HTTPException) as erro:
        _mudar_papel("u-2", "coordenador")
    assert erro.value.status_code == 422


def test_conta_inexistente_da_404():
    with pytest.raises(HTTPException) as erro:
        _mudar_papel("u-404", "administrador")
    assert erro.value.status_code == 404


def test_papel_inventado_nao_entra_pela_rota_de_papel():
    """Barrado aqui, como em `CriarCoordenadorBody`, E no CHECK da 0045."""
    with pytest.raises(ValidationError):
        administracao.PapelDoCoordenadorBody(papel="superadmin")
    assert administracao.PapelDoCoordenadorBody(papel=" ADMINISTRADOR ").papel == "administrador"


def test_papel_nao_entra_de_carona_pelo_corpo_de_editar():
    """Rota separada não é preciosismo: é o que impede um `{nome, papel}` mal
    montado de promover alguém enquanto renomeia."""
    assert "papel" not in administracao.EditarCoordenadorBody.model_fields


# ─── O token do rebaixado para de valer NA HORA ───────────────────────────


def test_rebaixado_perde_o_guard_de_administrador_sem_esperar_o_token_vencer(banco):
    """O ponto todo do rebaixamento. Sem a releitura na tabela, o rebaixado
    continuaria administrador por até 8 h — e poderia, nessa janela, criar
    OUTRA conta de administrador e desfazer a decisão."""
    banco["usuario_coordenacao"]["u-2"]["papel"] = "administrador"
    sessao_do_rebaixado = {"sub": "u-2", "tipo": "coordenador", "papel": "administrador"}
    assert _pela_cadeia_de_administrador(sessao_do_rebaixado) is sessao_do_rebaixado

    _mudar_papel("u-2", "coordenador")

    with pytest.raises(HTTPException) as erro:
        _pela_cadeia_de_administrador(sessao_do_rebaixado)
    assert erro.value.status_code == 403
    # Mas continua coordenador: rebaixar tira poder, não tira o trabalho.
    assert _como_coordenador(sessao_do_rebaixado) is sessao_do_rebaixado


def test_conta_desativada_perde_o_guard_de_administrador_na_hora(banco):
    """Mesma releitura, mesma razão: desativar a conta de um administrador tem
    que fechar a porta agora, não no fim do expediente."""
    banco["usuario_coordenacao"]["u-1"]["ativo"] = False
    with pytest.raises(HTTPException):
        _pela_cadeia_de_administrador(ADMINISTRADOR)


def test_conta_que_sumiu_da_tabela_nao_e_administradora():
    assert auth.conta_ainda_e_administradora("u-999") is False
    assert auth.conta_ainda_e_administradora(None) is False


def test_erro_de_leitura_recusa_em_vez_de_liberar(monkeypatch):
    """Fail-closed: banco fora do ar não promove ninguém a administrador."""

    class _Explode:
        def table(self, _nome):
            raise RuntimeError("sem banco")

    monkeypatch.setattr(auth, "get_supabase", lambda: _Explode())
    assert auth.conta_ainda_e_administradora("u-1") is False


def test_editar_nota_exige_administrador():
    """A outra rota promovida em 04/09, fora de `/administracao` (docs/35 §11.7)."""
    assert _matriz(notas.router) == {
        ("PATCH", "/notas/{aluno_id}/{simulado_id}"): "administrador"
    }


# ─── O login contra uma base sem a coluna `papel` ─────────────────────────


class _Resp:
    def __init__(self, data: list):
        self.data = data


class _Consulta:
    def __init__(self, cliente: "_ClienteFake"):
        self.cliente = cliente
        self.colunas = ""

    def select(self, colunas: str) -> "_Consulta":
        self.colunas = colunas
        self.cliente.selects.append(colunas)
        return self

    def update(self, _dados: dict) -> "_Consulta":
        return self

    def eq(self, *_args) -> "_Consulta":
        return self

    def limit(self, _n: int) -> "_Consulta":
        return self

    def execute(self) -> _Resp:
        if self.cliente.erro_fixo is not None:
            raise self.cliente.erro_fixo
        if "papel" in self.colunas and not self.cliente.tem_coluna_papel:
            # A resposta literal do PostgREST v12.2.3 quando a coluna não
            # existe: 400, e o postgrest-py transforma em APIError.
            raise APIError(
                {
                    "code": "42703",
                    "message": "column usuario_coordenacao.papel does not exist",
                    "details": None,
                    "hint": None,
                }
            )
        linha = dict(self.cliente.linha)
        if not self.cliente.tem_coluna_papel:
            linha.pop("papel", None)
        return _Resp([linha])


class _ClienteFake:
    """PostgREST de uma base COM ou SEM a 0045 aplicada."""

    def __init__(
        self,
        linha: dict,
        *,
        tem_coluna_papel: bool,
        erro_fixo: Exception | None = None,
    ):
        self.linha = linha
        self.tem_coluna_papel = tem_coluna_papel
        self.erro_fixo = erro_fixo
        self.selects: list[str] = []

    def table(self, _nome: str) -> _Consulta:
        return _Consulta(self)


class _RequisicaoFake:
    class _Cliente:
        host = "127.0.0.1"

    client = _Cliente()


SENHA = "senha-de-teste"
# Um PBKDF2 de 600.000 iterações, reaproveitado pelos testes de login.
HASH_DA_SENHA = auth.hash_senha(SENHA)


@pytest.fixture(autouse=True)
def _ambiente(monkeypatch):
    """APP_ENV=dev para `criar_token` achar a chave; auditoria desligada porque
    quem se testa aqui é o papel, não a trilha."""
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("JWT_SECRET_KEY", SEGREDO)
    monkeypatch.setattr(rotas_auth, "auditar", lambda *a, **k: None)
    # O limitador de tentativas é um dict de módulo: sem limpar, testes de
    # login que compartilham e-mail contaminariam uns aos outros.
    rotas_auth._tentativas_por_chave.clear()
    yield
    rotas_auth._tentativas_por_chave.clear()
    get_settings.cache_clear()


def _linha_de_conta(papel: str) -> dict:
    return {
        "id": "u-9",
        "nome": "Coordenação",
        "senha_hash": HASH_DA_SENHA,
        "ativo": True,
        "papel": papel,
        "foto_perfil_storage": None,
    }


def _logar(monkeypatch, cliente: _ClienteFake, email: str) -> dict:
    monkeypatch.setattr(rotas_auth, "get_supabase", lambda: cliente)
    corpo = rotas_auth.LoginBody(tipo="coordenador", usuario=email, senha=SENHA)
    return asyncio.run(rotas_auth.login(corpo, _RequisicaoFake()))


# O que `_buscar_conta` pede em cada tentativa, na ordem.
SELECT_COM_PAPEL = "id, nome, senha_hash, ativo, foto_perfil_storage, papel"
SELECT_SEM_PAPEL = "id, nome, senha_hash, ativo, foto_perfil_storage"


def test_login_le_o_papel_quando_a_coluna_existe(monkeypatch):
    cliente = _ClienteFake(_linha_de_conta("administrador"), tem_coluna_papel=True)
    resposta = _logar(monkeypatch, cliente, "chefe@ari.com")
    assert resposta["papel"] == "administrador"
    # Só o SELECT normal: o fallback não pode virar o caminho de todo dia.
    assert cliente.selects == [SELECT_COM_PAPEL]


def test_login_sobrevive_a_base_sem_a_coluna_papel(monkeypatch):
    """G7: descer a 0045 — ou subir esta API contra uma base que ainda não a
    aplicou — não pode virar 500 no login. A coordenação não tem segunda porta:
    o aluno entra pelo Canvas, ela não."""
    cliente = _ClienteFake(_linha_de_conta("administrador"), tem_coluna_papel=False)
    resposta = _logar(monkeypatch, cliente, "chefe@ari.com")
    assert resposta["access_token"]
    # Entra, e entra no papel MENOS poderoso — sem a coluna ninguém é admin.
    assert resposta["papel"] == "coordenador"
    # Tentou com `papel`, levou 42703, refez sem.
    assert cliente.selects == [SELECT_COM_PAPEL, SELECT_SEM_PAPEL]


def test_erro_do_postgrest_que_nao_e_coluna_ausente_continua_subindo(monkeypatch):
    """A tolerância é estreita de propósito: só 42703. Um statement timeout não
    pode virar login silencioso como coordenador."""
    cliente = _ClienteFake(
        _linha_de_conta("administrador"),
        tem_coluna_papel=True,
        erro_fixo=APIError({"code": "57014", "message": "statement timeout"}),
    )
    with pytest.raises(APIError):
        _logar(monkeypatch, cliente, "chefe@ari.com")
    assert cliente.selects == [SELECT_COM_PAPEL]
