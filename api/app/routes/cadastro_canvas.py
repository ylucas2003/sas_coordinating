"""Cadastrar aluno no Canvas pela tela — um por vez e em lote (docs/46).

Todas as rotas são de ADMINISTRADOR, no router inteiro e não rota a rota:
aqui não há nada de leitura que a coordenação use no dia a dia, e o que se
faz é criar login na conta do colégio com um token que é administrador pleno
dela (`manage_user_logins`, `import_sis`…, conferido em 25/11/2026). É o
mesmo motivo de criar conta de coordenação ser só do administrador
(docs/35 §11.7), com o alcance maior.

Os dois caminhos são o que a API do Canvas oferece:

  * **um por vez** — REST: cria a conta e faz uma matrícula por curso do
    pacote. Resposta na hora, curso a curso, e repetível;
  * **em lote** — SIS Import de CSV, o mesmo que o administrador do Canvas já
    sobe à mão. Assíncrono: a rota devolve o id, e a tela acompanha.

A regra de "nada sobe ao Canvas sem alguém clicar" (docs/18 §2.3) vale
inteira: as duas escritas são sempre o clique final de uma tela que mostrou,
antes, exatamente o que seria feito.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, field_validator

from ..auditoria import registrar as auditar
from ..auth import get_current_administrador
from ..canvas_sync import cadastro
from ..canvas_sync.escrita import CanvasIndisponivel
from ..config import get_settings
from ..supabase_client import get_supabase

log = logging.getLogger("sas.canvas.cadastro")

router = APIRouter(
    prefix="/administracao/cadastro-canvas",
    tags=["cadastro-canvas"],
    dependencies=[Depends(get_current_administrador)],
)

#: Planilha de 1.500 linhas em .xlsx tem ~100 KB. Mais que isto não é a
#: planilha certa — e o arquivo inteiro fica em memória.
_TAMANHO_MAXIMO_DA_PLANILHA = 5 * 1024 * 1024

#: Trechos do `.in_()` ao banco: 1.500 matrículas numa URL só passariam de
#: 13 KB de query string.
_TRECHO_DO_IN = 200


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _erro_de_canvas(exc: Exception) -> HTTPException:
    """Falha de conversa com o Canvas → HTTP com frase para a tela."""
    if isinstance(exc, CanvasIndisponivel):
        return HTTPException(status_code=503, detail="O Canvas não está configurado neste servidor.")
    if isinstance(exc, httpx.HTTPStatusError):
        return HTTPException(
            status_code=502,
            detail=f"O Canvas recusou a operação (HTTP {exc.response.status_code}).",
        )
    return HTTPException(status_code=504, detail="O Canvas não respondeu. Tente de novo em instantes.")


_FALHAS_DE_CANVAS = (CanvasIndisponivel, httpx.HTTPStatusError, httpx.TimeoutException, httpx.TransportError)


async def _catalogo(canvas: Any, ano: int | None) -> cadastro.Catalogo:
    settings = get_settings()
    try:
        return await cadastro.carregar_catalogo(
            canvas,
            account_id=settings.canvas_account_id,
            ano=ano,
            ano_configurado=settings.canvas_ano_vigente,
        )
    except LookupError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _contas_que_o_sas_conhece(cliente: Any, matriculas: list[str]) -> dict[str, cadastro.ContaExistente]:
    """Quem o sync já trouxe do Canvas tem conta lá — sem perguntar a ele."""
    conhecidas: dict[str, cadastro.ContaExistente] = {}
    for i in range(0, len(matriculas), _TRECHO_DO_IN):
        linhas = (
            cliente.table("aluno")
            .select("matricula, nome, canvas_user_id")
            .in_("matricula", matriculas[i : i + _TRECHO_DO_IN])
            .not_.is_("canvas_user_id", "null")
            .execute()
            .data
            or []
        )
        for linha in linhas:
            conhecidas[linha["matricula"]] = cadastro.ContaExistente(
                canvas_user_id=str(linha["canvas_user_id"]), nome=linha.get("nome") or ""
            )
    return conhecidas


async def _validar_lote(
    canvas: Any, brutas: list[dict[str, Any]], catalogo: cadastro.Catalogo
) -> list[cadastro.LinhaDoLote]:
    """A mesma conferência na prévia e no envio — o envio não confia na prévia."""
    linhas = [cadastro.validar_linha(b, catalogo.pacotes, ano=catalogo.ano) for b in brutas]
    cadastro.marcar_repetidas(linhas)
    # O SIS Import só fala em SIS ID: série cujo pacote tem curso sem ela não
    # entra no lote (o cadastro de um por vez continua servindo).
    for linha in linhas:
        if linha.situacao != "erro" and linha.serie is not None:
            problemas = cadastro.problemas_do_pacote_no_lote(catalogo.pacotes[linha.serie])
            if problemas:
                linha.erros.append("; ".join(problemas) + " — cadastre esta pelo formulário de um aluno")
                linha.situacao = "erro"
    validas = sorted({l.matricula for l in linhas if l.situacao != "erro"})
    conhecidas = _contas_que_o_sas_conhece(get_supabase(), validas)
    existentes = await cadastro.descobrir_existentes(canvas, validas, conhecidas=conhecidas)
    cadastro.aplicar_existentes(linhas, existentes)
    return linhas


def _resumo(linhas: list[cadastro.LinhaDoLote]) -> dict[str, int]:
    return {
        "total": len(linhas),
        "novas": sum(1 for l in linhas if l.situacao == "nova"),
        "existentes": sum(1 for l in linhas if l.situacao == "existente"),
        "com_erro": sum(1 for l in linhas if l.situacao == "erro"),
        "com_aviso": sum(1 for l in linhas if l.avisos and l.situacao != "erro"),
    }


# ─── O pacote ─────────────────────────────────────────────────────────────


@router.get("/pacotes")
async def listar_pacotes(ano: int | None = None) -> dict[str, Any]:
    """Os cursos em que cada série é matriculada, e as sedes — lidos agora."""
    try:
        async with cadastro.abrir_canvas() as canvas:
            catalogo = await _catalogo(canvas, ano)
    except _FALHAS_DE_CANVAS as exc:
        raise _erro_de_canvas(exc) from exc
    return {
        "ano": catalogo.ano,
        "anos": catalogo.anos,
        "pacotes": [cadastro.pacote_para_json(p) for p in catalogo.pacotes.values()],
    }


# ─── Um por vez ───────────────────────────────────────────────────────────


class CadastroDeAlunoBody(BaseModel):
    matricula: str
    nome: str
    email: str | None = None
    serie: int
    sede_id: str | None = None
    ano: int | None = None
    #: A matrícula já é de uma conta com nome diferente, e quem cadastra
    #: confirmou que é a mesma pessoa.
    confirmar_nome_existente: bool = False

    @field_validator("matricula")
    @classmethod
    def _matricula(cls, v: str) -> str:
        texto, erro = cadastro.validar_matricula(v)
        if erro:
            raise ValueError(erro)
        return texto or ""

    @field_validator("nome")
    @classmethod
    def _nome(cls, v: str) -> str:
        nome = cadastro.normalizar_nome(v)
        if not nome:
            raise ValueError("nome é obrigatório")
        return nome

    @field_validator("email")
    @classmethod
    def _email(cls, v: str | None) -> str | None:
        texto, erro = cadastro.validar_email(v)
        if erro:
            raise ValueError(erro)
        return texto


@router.post("/aluno")
async def cadastrar_um_aluno(
    body: CadastroDeAlunoBody,
    request: Request,
    administrador: dict = Depends(get_current_administrador),
) -> dict[str, Any]:
    """Cria a conta (ou acha a que existe) e matricula no pacote da série.

    Devolve curso a curso. `completo: false` não é erro HTTP: parte das
    matrículas entrou, e repetir a mesma chamada faz só as que faltam."""
    settings = get_settings()
    try:
        async with cadastro.abrir_canvas() as canvas:
            catalogo = await _catalogo(canvas, body.ano)
            pacote = catalogo.pacotes.get(body.serie)
            if pacote is None:
                raise HTTPException(
                    status_code=422,
                    detail=f"Não há curso do {cadastro.ROTULO_DA_SERIE.get(body.serie, body.serie)} "
                    f"de {catalogo.ano} no Canvas.",
                )
            sede = None
            if pacote.exige_sede:
                sede, erro = cadastro.achar_sede(body.sede_id, pacote.sedes)
                if erro:
                    raise HTTPException(status_code=422, detail=f"Escolha a sede: {erro}.")
            resultado = await cadastro.cadastrar_aluno(
                canvas,
                account_id=settings.canvas_account_id,
                pacote=pacote,
                sede=sede,
                matricula=body.matricula,
                nome=body.nome,
                email=body.email,
                confirmar_nome=body.confirmar_nome_existente,
            )
    except cadastro.NomeNaoBate as exc:
        # 409 com o nome na frase: é o que a tela mostra ao pedir confirmação.
        # Quem lê é o administrador, que já enxerga todos os alunos.
        raise HTTPException(
            status_code=409,
            detail=(
                f"A matrícula {body.matricula} já é de “{exc.nome_no_canvas}” no Canvas. "
                "Confira a matrícula; se for a mesma pessoa, confirme para matricular."
            ),
        ) from exc
    except cadastro.EmailObrigatorio as exc:
        raise HTTPException(
            status_code=422,
            detail="Este aluno ainda não tem conta no Canvas: informe o e-mail, "
            "que é por onde ele vai criar a senha.",
        ) from exc
    except cadastro.CanvasRecusou as exc:
        # 422, e não 409: o 409 desta rota é SÓ o "confirme que é a mesma
        # pessoa", e a tela responde a ele com um botão de confirmar. Confirmar
        # não resolve um login que o Canvas recusou.
        raise HTTPException(status_code=422, detail=f"O Canvas recusou criar a conta: {exc}") from exc
    except _FALHAS_DE_CANVAS as exc:
        raise _erro_de_canvas(exc) from exc

    estados = [c["estado"] for c in resultado["cursos"]]
    auditar(
        get_supabase(), "aluno_cadastrado_no_canvas", canal="acesso",
        ator_tipo="coordenador", ator_id=administrador.get("sub"),
        recurso=f"canvas_usuario/{resultado['canvas_user_id']}", ip=_ip(request),
        # Sem nome nem e-mail: são de aluno menor, e a matrícula basta para
        # achar quem foi (auditoria.py: "quem" e "quando", não conteúdo).
        detalhe={
            "matricula": body.matricula, "ano": resultado["ano"], "serie": resultado["serie"],
            "sede": resultado["sede"], "conta": resultado["conta"],
            "matriculado": estados.count("matriculado"), "ja_estava": estados.count("ja_estava"),
            "falhou": estados.count("falhou"), "outra_sede": estados.count("outra_sede"),
        },
    )
    return resultado


# ─── Em lote ──────────────────────────────────────────────────────────────


@router.post("/lote/previa")
async def previa_do_lote(
    arquivo: UploadFile = File(...),
    ano: int | None = Form(None),
) -> dict[str, Any]:
    """Lê a planilha e diz, linha a linha, o que aconteceria. Não escreve nada."""
    conteudo = await arquivo.read(_TAMANHO_MAXIMO_DA_PLANILHA + 1)
    if len(conteudo) > _TAMANHO_MAXIMO_DA_PLANILHA:
        raise HTTPException(status_code=413, detail="A planilha passa de 5 MB — não é a planilha certa?")
    try:
        brutas = cadastro.ler_planilha(conteudo, arquivo.filename or "")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        async with cadastro.abrir_canvas() as canvas:
            catalogo = await _catalogo(canvas, ano)
            linhas = await _validar_lote(canvas, brutas, catalogo)
    except _FALHAS_DE_CANVAS as exc:
        raise _erro_de_canvas(exc) from exc
    return {
        "ano": catalogo.ano,
        "linhas": [l.para_json() for l in linhas],
        "resumo": _resumo(linhas),
    }


class LinhaDoLoteBody(BaseModel):
    linha: int = 0
    matricula: str
    nome: str
    email: str | None = None
    serie: int | str
    #: O id da section que a prévia resolveu; o nome também é aceito.
    sede_id: str | None = None


class EnvioDoLoteBody(BaseModel):
    ano: int
    linhas: list[LinhaDoLoteBody]

    @field_validator("linhas")
    @classmethod
    def _tamanho(cls, v: list[LinhaDoLoteBody]) -> list[LinhaDoLoteBody]:
        if not v:
            raise ValueError("lote vazio")
        if len(v) > cadastro.MAXIMO_DE_LINHAS_NO_LOTE:
            raise ValueError(f"no máximo {cadastro.MAXIMO_DE_LINHAS_NO_LOTE} linhas")
        return v


@router.post("/lote", status_code=202)
async def enviar_lote(
    body: EnvioDoLoteBody,
    request: Request,
    administrador: dict = Depends(get_current_administrador),
) -> dict[str, Any]:
    """Confere tudo de novo e sobe UM SIS Import. 202: o Canvas processa depois.

    Recusa o lote inteiro se uma linha tiver erro, em vez de mandar as boas:
    uma planilha que mudou entre a prévia e o envio precisa de outra prévia,
    não de um envio pela metade que ninguém sabe qual metade foi."""
    settings = get_settings()
    brutas = [
        {"linha": l.linha, "matricula": l.matricula, "nome": l.nome, "email": l.email,
         "serie": l.serie, "sede": l.sede_id}
        for l in body.linhas
    ]
    try:
        async with cadastro.abrir_canvas() as canvas:
            catalogo = await _catalogo(canvas, body.ano)
            linhas = await _validar_lote(canvas, brutas, catalogo)
            com_erro = [l for l in linhas if l.situacao == "erro"]
            if com_erro:
                primeira = com_erro[0]
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"{len(com_erro)} linha(s) com erro — a primeira é a {primeira.linha} "
                        f"({'; '.join(primeira.erros)}). Refaça a prévia."
                    ),
                )
            arquivo_zip = cadastro.montar_zip_do_lote(linhas, catalogo.pacotes)
            importacao = await canvas.enviar_sis_import(
                settings.canvas_account_id, arquivo_zip=arquivo_zip
            )
    except _FALHAS_DE_CANVAS as exc:
        raise _erro_de_canvas(exc) from exc

    resumo = _resumo(linhas)
    auditar(
        get_supabase(), "lote_enviado_ao_canvas", canal="acesso",
        ator_tipo="coordenador", ator_id=administrador.get("sub"),
        recurso=f"sis_import/{importacao.get('id')}", ip=_ip(request),
        detalhe={
            "sis_import_id": importacao.get("id"), "ano": catalogo.ano,
            "linhas": resumo["total"], "contas_novas": resumo["novas"],
            "contas_existentes": resumo["existentes"],
        },
    )
    return {**cadastro.resumir_sis_import(importacao), "linhas": resumo}


@router.get("/lote")
async def lotes_recentes() -> list[dict[str, Any]]:
    """Os SIS Imports que o SAS subiu, dos mais novos.

    Não há tabela: o Canvas guarda o import, e o que é do SAS se separa pelo
    autor — o dono do token. O que o administrador sobe à mão pela tela do
    Canvas sai com a conta pessoal dele e não aparece aqui."""
    settings = get_settings()
    try:
        async with cadastro.abrir_canvas() as canvas:
            eu = await canvas.quem_sou()
            recentes = await canvas.listar_sis_imports_recentes(settings.canvas_account_id)
    except _FALHAS_DE_CANVAS as exc:
        raise _erro_de_canvas(exc) from exc
    meus = [i for i in recentes if str((i.get("user") or {}).get("id")) == str(eu.get("id"))]
    return [cadastro.resumir_sis_import(i) for i in meus[:10]]


@router.get("/lote/{import_id}")
async def situacao_do_lote(import_id: str) -> dict[str, Any]:
    if not import_id.isdigit():
        raise HTTPException(status_code=422, detail="id de lote inválido")
    settings = get_settings()
    try:
        async with cadastro.abrir_canvas() as canvas:
            importacao = await canvas.obter_sis_import(settings.canvas_account_id, import_id)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise HTTPException(status_code=404, detail="lote não encontrado no Canvas") from exc
        raise _erro_de_canvas(exc) from exc
    except _FALHAS_DE_CANVAS as exc:
        raise _erro_de_canvas(exc) from exc
    return cadastro.resumir_sis_import(importacao)
