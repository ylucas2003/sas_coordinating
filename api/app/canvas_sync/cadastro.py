"""Cadastro de aluno no Canvas pelo SAS — um por vez e em lote (docs/46).

Até aqui o SAS só LIA quem é aluno: o sync traz do Canvas quem está
matriculado nos cursos de provas (`sincronizar.py`). Quem criava a conta e
matriculava era o administrador do Canvas, à mão — em 2026, a conta pessoal do
Leo (289), por SIS Import de CSV, em 04/08, 25/08, 08/09, 28/09 e 06/11. Este
módulo faz o mesmo pelo SAS, e só o administrador do SAS chega até ele.

O que não se deduz lendo o código (levantamento de 25/11/2026, só GETs):

* **Um aluno do 3º está em 19 cursos**, não em um: Física 1–5, Matemática
  1–5, Química 1–4, Português 1–2, Inglês, Redação e Simulados. A sede só
  existe como section no curso de Simulados; os outros têm só a section
  padrão. O 1º e o 2º ano têm um curso cada (Avaliações). Isso é o "pacote da
  série", e ele é descoberto no Canvas PELO NOME a cada chamada, nunca
  guardado: a escola cria os cursos do ano novo, e uma lista gravada aqui
  envelheceria em silêncio.
* **O login é a matrícula.** 1.048 dos 1.104 alunos de 2026 entram com o
  `sis_user_id` como login, e o `sis_user_id` é a matrícula de 8 dígitos — a
  mesma chave do SAS (`aluno.matricula`, `mapeador.mapear_aluno`).
* **A senha nunca passa pelo SAS.** O Canvas manda ao aluno o e-mail de
  terminar o cadastro, e é ali que ele cria a senha. Por isso o e-mail é
  obrigatório para conta nova, e só para ela.
* **Conta que já existe não é tocada** — nem nome, nem e-mail, nem senha: só
  ganha as matrículas que faltam. É o caso mais comum na virada do ano (o
  aluno do 2º que vai para o 3º).
* **O SAS não grava o aluno no próprio banco.** O sync de 5 minutos lê as
  matrículas dos cursos de provas e o traz sozinho.
"""

from __future__ import annotations

import asyncio
import csv
import io
import re
import unicodedata
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from ..config import get_settings
from . import mapeador
from .cliente import ClienteCanvas
from .escrita import CanvasIndisponivel

#: Todas as 1.097 matrículas reais do 3º de 2026 têm 8 dígitos; as sete que
#: não têm são contas de teste. Um dígito a menos é quase sempre o Excel
#: comendo o zero à esquerda de uma coluna numérica — e criaria um login
#: errado que ninguém acharia depois.
DIGITOS_DA_MATRICULA = 8

#: O colégio inteiro tem ~1.100 alunos ITA/IME. Um arquivo maior que isto é
#: planilha errada, não lote grande.
MAXIMO_DE_LINHAS_NO_LOTE = 1500

#: "2026 3o ITA/IME Física 1" → (2026, 3). Todo curso da série no ano entra no
#: pacote — inclusive os que a escola criar depois, sem mexer aqui.
PADRAO_CURSO_DA_SERIE = re.compile(
    r"^(?P<ano>\d{4})\s+(?P<serie>[123])o\s+ITA/IME\s+\S", re.IGNORECASE
)

ROTULO_DA_SERIE = {1: "1º ano", 2: "2º ano", 3: "3º ano"}

#: Estados do SIS Import que ainda vão mudar.
_IMPORT_EM_ANDAMENTO = frozenset(
    {"initializing", "created", "importing", "cleanup_batch", "restoring"}
)


# ─── O pacote da série ────────────────────────────────────────────────────


@dataclass(frozen=True)
class Curso:
    id: str
    nome: str
    sis_id: str | None


@dataclass(frozen=True)
class Sede:
    """Uma section do curso de provas — "3o ITA AD", "MF Online"…"""

    id: str
    nome: str
    sis_id: str | None


@dataclass(frozen=True)
class Pacote:
    ano: int
    serie: int
    cursos: tuple[Curso, ...]
    #: O curso de provas da série (Simulados no 3º, Avaliações no 1º e 2º): é
    #: o que o sync lê, e o único onde a section quer dizer sede.
    curso_de_provas: Curso | None
    sedes: tuple[Sede, ...]

    @property
    def exige_sede(self) -> bool:
        return self.curso_de_provas is not None and bool(self.sedes)


def _eh_curso_de_provas(nome: str, serie: int) -> bool:
    if serie == 3:
        return mapeador.parsear_ano_curso_simulados(nome) is not None
    return mapeador.parsear_curso_avaliacoes(nome) is not None


def anos_dos_cursos(cursos: list[dict[str, Any]]) -> list[int]:
    """Os anos que têm algum curso de série, do mais novo ao mais velho."""
    anos = {
        int(m.group("ano"))
        for c in cursos
        if (m := PADRAO_CURSO_DA_SERIE.match((c.get("name") or "").strip()))
    }
    return sorted(anos, reverse=True)


def anos_oferecidos(anos: list[int], *, ano_atual: int) -> list[int]:
    """Do ano corrente em diante — e, se nenhum, só o mais novo.

    O Canvas ainda tem cursos "disponíveis" de 2021 a 2025 (25/11/2026), e
    oferecer esses anos na tela seria um jeito de matricular alguém num curso
    morto. O "se nenhum" é janeiro, antes de a escola criar os cursos do ano."""
    correntes = [a for a in anos if a >= ano_atual]
    return correntes or anos[:1]


def ano_padrao(anos: list[int], configurado: str) -> int | None:
    """`CANVAS_ANO_VIGENTE` quando ele existe no Canvas; senão o mais novo.

    O mais novo, e não o do sync, porque matricular é coisa de virada de ano:
    em dezembro os cursos de 2027 já existem fechados, e é neles que o aluno
    novo entra. A tela mostra o ano e deixa trocar quando há mais de um."""
    if configurado.strip().isdigit() and int(configurado) in anos:
        return int(configurado)
    return anos[0] if anos else None


def montar_pacotes(
    cursos: list[dict[str, Any]],
    sections_por_curso: dict[str, list[dict[str, Any]]],
    *,
    ano: int,
) -> dict[int, Pacote]:
    """{série: Pacote} do ano, a partir do que o Canvas listou."""
    por_serie: dict[int, list[Curso]] = {}
    de_provas: dict[int, Curso] = {}
    for bruto in cursos:
        nome = (bruto.get("name") or "").strip()
        m = PADRAO_CURSO_DA_SERIE.match(nome)
        if not m or int(m.group("ano")) != ano:
            continue
        serie = int(m.group("serie"))
        curso = Curso(id=str(bruto["id"]), nome=nome, sis_id=bruto.get("sis_course_id") or None)
        por_serie.setdefault(serie, []).append(curso)
        if _eh_curso_de_provas(nome, serie):
            de_provas[serie] = curso

    pacotes: dict[int, Pacote] = {}
    for serie, lista in sorted(por_serie.items()):
        provas = de_provas.get(serie)
        sedes: list[Sede] = []
        if provas is not None:
            for s in sections_por_curso.get(provas.id, []):
                nome_sec = (s.get("name") or "").strip()
                # A section padrão leva o nome do curso. No 3º ela é a "sede
                # fantasma": quem cai nela vira "Sem section no Canvas" no SAS
                # e gerou 46 alertas falsos de diferença entre sedes em 06/11.
                if _chave(nome_sec) == _chave(provas.nome):
                    continue
                sedes.append(
                    Sede(id=str(s["id"]), nome=nome_sec, sis_id=s.get("sis_section_id") or None)
                )
        pacotes[serie] = Pacote(
            ano=ano,
            serie=serie,
            cursos=tuple(sorted(lista, key=lambda c: c.nome)),
            curso_de_provas=provas,
            sedes=tuple(sorted(sedes, key=lambda s: s.nome)),
        )
    return pacotes


def problemas_do_pacote_no_lote(pacote: Pacote) -> list[str]:
    """O SIS Import só fala em SIS ID. Curso ou sede sem ela não entra no lote
    — o cadastro de um por vez, que fala em id do Canvas, ainda serve."""
    sem_sis = [c.nome for c in pacote.cursos if not c.sis_id]
    problemas = [f"o curso {nome} não tem SIS ID no Canvas" for nome in sem_sis]
    problemas += [f"a sede {s.nome} não tem SIS ID no Canvas" for s in pacote.sedes if not s.sis_id]
    return problemas


def pacote_para_json(pacote: Pacote) -> dict[str, Any]:
    return {
        "serie": pacote.serie,
        "rotulo": ROTULO_DA_SERIE.get(pacote.serie, f"{pacote.serie}º ano"),
        "cursos": [{"id": c.id, "nome": c.nome} for c in pacote.cursos],
        "curso_de_provas": pacote.curso_de_provas.nome if pacote.curso_de_provas else None,
        "exige_sede": pacote.exige_sede,
        "sedes": [{"id": s.id, "nome": s.nome} for s in pacote.sedes],
        "problemas_no_lote": problemas_do_pacote_no_lote(pacote),
    }


# ─── Texto: nomes, sedes, séries ──────────────────────────────────────────


def _chave(texto: str) -> str:
    """Minúsculas, sem acento e com um espaço só — para comparar o que uma
    pessoa digitou com o que o Canvas guarda."""
    sem_acento = unicodedata.normalize("NFKD", texto or "")
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return " ".join(sem_acento.lower().split())


def achar_sede(valor: str | None, sedes: tuple[Sede, ...]) -> tuple[Sede | None, str | None]:
    """(sede, erro). Aceita o id da section, a SIS ID ou o nome.

    Nome exato primeiro; depois, palavra inteira — mas só se uma sede só
    casar. "Proposito" acha "Proposito (Objetivo)"; "AD" casa com "3o ITA AD"
    e com "AD Online", e por isso é erro, não chute."""
    if not valor or not valor.strip():
        return None, "falta a sede"
    alvo = _chave(valor)
    for s in sedes:
        if alvo in (s.id, _chave(s.sis_id or ""), _chave(s.nome)):
            return s, None
    padrao = re.compile(rf"(?<!\w){re.escape(alvo)}(?!\w)")
    candidatas = [s for s in sedes if padrao.search(_chave(s.nome))]
    if len(candidatas) == 1:
        return candidatas[0], None
    nomes = ", ".join(s.nome for s in (candidatas or list(sedes)))
    if candidatas:
        return None, f"sede “{valor.strip()}” é ambígua: {nomes}"
    return None, f"sede “{valor.strip()}” não existe no Canvas; as sedes são: {nomes}"


_PADRAO_SERIE = re.compile(r"^([123])\s*(?:[oa°])?\s*(?:serie|ano)?$")


def normalizar_serie(valor: Any) -> int | None:
    """"3", "3º", "3o", "3ª série", "3º ano" → 3. O resto, None."""
    # O NFKD de `_chave` já faz de "º" um "o" e de "ª" um "a"; "°" (grau) fica.
    texto = _chave(str(valor if valor is not None else ""))
    m = _PADRAO_SERIE.match(texto)
    return int(m.group(1)) if m else None


def normalizar_nome(nome: str | None) -> str:
    return " ".join((nome or "").split())


def nomes_batem(digitado: str, no_canvas: str) -> bool:
    """O nome da planilha é da mesma pessoa que a conta do Canvas?

    Primeiro e último nome iguais (sem acento), ou um nome contido no outro.
    É a trava contra o erro mais caro do cadastro: uma matrícula digitada
    errado que é de OUTRO aluno, que seria matriculado em 19 cursos que não são
    dele. Nome do meio abreviado ou faltando continua batendo."""
    a, b = _chave(digitado).split(), _chave(no_canvas).split()
    if not a or not b:
        return False
    if a[0] == b[0] and a[-1] == b[-1]:
        return True
    return set(a) <= set(b) or set(b) <= set(a)


def validar_email(email: str | None) -> tuple[str | None, str | None]:
    """(e-mail normalizado, erro). Vazio não é erro aqui — só conta NOVA exige."""
    texto = (email or "").strip().lower()
    if not texto:
        return None, None
    usuario, _, dominio = texto.partition("@")
    if not usuario or "." not in dominio or " " in texto:
        return None, f"e-mail inválido: {email}"
    return texto, None


def validar_matricula(matricula: Any) -> tuple[str | None, str | None]:
    texto = str(matricula if matricula is not None else "").strip()
    if not texto:
        return None, "falta a matrícula"
    if not texto.isdigit():
        return None, f"matrícula “{texto}” tem caractere que não é dígito"
    if len(texto) != DIGITOS_DA_MATRICULA:
        dica = (
            " — se veio de planilha, o Excel pode ter comido um zero à esquerda: "
            "formate a coluna como texto"
            if len(texto) < DIGITOS_DA_MATRICULA
            else ""
        )
        return None, f"matrícula “{texto}” tem {len(texto)} dígitos, e não {DIGITOS_DA_MATRICULA}{dica}"
    return texto, None


# ─── A planilha do lote ───────────────────────────────────────────────────

#: Cabeçalho aceito → campo. Comparado sem acento e em minúsculas.
_SINONIMOS = {
    "matricula": "matricula", "ra": "matricula", "sis_user_id": "matricula",
    "user_id": "matricula", "login": "matricula",
    "nome": "nome", "nome completo": "nome", "aluno": "nome", "full_name": "nome",
    "email": "email", "e-mail": "email", "e mail": "email",
    "serie": "serie", "série": "serie",
    "sede": "sede", "turma": "sede", "section": "sede", "unidade": "sede",
}

CAMPOS_DO_LOTE = ("matricula", "nome", "email", "serie", "sede")


def _celula(valor: Any) -> str:
    """O Excel guarda matrícula como número: 12345678.0 precisa voltar a ser
    "12345678", e não "12345678.0"."""
    if valor is None:
        return ""
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor).strip()


def _linhas_do_xlsx(conteudo: bytes) -> list[list[str]]:
    from openpyxl import load_workbook

    try:
        livro = load_workbook(io.BytesIO(conteudo), read_only=True, data_only=True)
    except Exception as exc:  # zip corrompido, formato errado
        raise ValueError("Não consegui abrir a planilha. Salve como .xlsx ou .csv.") from exc
    folha = livro.worksheets[0]
    return [[_celula(v) for v in linha] for linha in folha.iter_rows(values_only=True)]


def _linhas_do_csv(conteudo: bytes) -> list[list[str]]:
    for codificacao in ("utf-8-sig", "cp1252"):
        try:
            texto = conteudo.decode(codificacao)
            break
        except UnicodeDecodeError:
            continue
    else:  # pragma: no cover — cp1252 decodifica quase tudo
        raise ValueError("Não consegui ler o texto do arquivo.")
    # Excel em português salva CSV com ";". Sniffer só entre os três que
    # aparecem de verdade, senão ele elege a letra mais comum do nome.
    try:
        dialeto = csv.Sniffer().sniff(texto[:4096], delimiters=";,\t")
    except csv.Error:
        dialeto = csv.excel
    return [[c.strip() for c in linha] for linha in csv.reader(io.StringIO(texto), dialeto)]


def ler_planilha(conteudo: bytes, nome_arquivo: str) -> list[dict[str, Any]]:
    """[{linha, matricula, nome, email, serie, sede}], na ordem do arquivo.

    `linha` é o número da linha NA PLANILHA (cabeçalho incluído), para a
    pessoa achar o erro no arquivo dela. Levanta ValueError com a mensagem
    que vai para a tela."""
    if nome_arquivo.lower().endswith((".xlsx", ".xlsm")):
        brutas = _linhas_do_xlsx(conteudo)
    else:
        brutas = _linhas_do_csv(conteudo)

    # O cabeçalho é a primeira linha não vazia.
    inicio = next((i for i, linha in enumerate(brutas) if any(linha)), None)
    if inicio is None:
        raise ValueError("A planilha está vazia.")
    cabecalho = [_SINONIMOS.get(_chave(c)) for c in brutas[inicio]]
    faltando = [c for c in ("matricula", "nome", "serie") if c not in cabecalho]
    if faltando:
        raise ValueError(
            "Faltam colunas na primeira linha: " + ", ".join(faltando)
            + ". As colunas são: matricula, nome, email, serie, sede."
        )

    linhas: list[dict[str, Any]] = []
    for i, bruta in enumerate(brutas[inicio + 1 :], start=inicio + 2):
        if not any(bruta):
            continue
        registro: dict[str, Any] = {"linha": i}
        for campo, valor in zip(cabecalho, bruta, strict=False):
            if campo and not registro.get(campo):
                registro[campo] = valor
        linhas.append(registro)
    if not linhas:
        raise ValueError("A planilha só tem o cabeçalho.")
    if len(linhas) > MAXIMO_DE_LINHAS_NO_LOTE:
        raise ValueError(
            f"São {len(linhas)} linhas; o máximo é {MAXIMO_DE_LINHAS_NO_LOTE}. "
            "Divida o arquivo."
        )
    return linhas


# ─── Uma linha do lote ────────────────────────────────────────────────────


@dataclass
class LinhaDoLote:
    linha: int
    matricula: str
    nome: str
    email: str | None
    serie: int | None
    sede: Sede | None
    #: nova | existente | erro
    situacao: str = "nova"
    erros: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    nome_no_canvas: str | None = None

    def para_json(self) -> dict[str, Any]:
        return {
            "linha": self.linha,
            "matricula": self.matricula,
            "nome": self.nome,
            "email": self.email,
            "serie": self.serie,
            "sede_id": self.sede.id if self.sede else None,
            "sede_nome": self.sede.nome if self.sede else None,
            "situacao": self.situacao,
            "erros": self.erros,
            "avisos": self.avisos,
            "nome_no_canvas": self.nome_no_canvas,
        }


def validar_linha(bruta: dict[str, Any], pacotes: dict[int, Pacote], *, ano: int) -> LinhaDoLote:
    """Tudo o que dá para conferir sem perguntar ao Canvas se a conta existe."""
    erros: list[str] = []
    matricula, erro = validar_matricula(bruta.get("matricula"))
    if erro:
        erros.append(erro)
    nome = normalizar_nome(bruta.get("nome"))
    if not nome:
        erros.append("falta o nome")
    email, erro = validar_email(bruta.get("email"))
    if erro:
        erros.append(erro)

    serie = normalizar_serie(bruta.get("serie"))
    sede: Sede | None = None
    avisos: list[str] = []
    if serie is None:
        erros.append(f"série “{bruta.get('serie') or ''}” não reconhecida — use 1, 2 ou 3")
    elif serie not in pacotes:
        erros.append(f"não há curso do {ROTULO_DA_SERIE[serie]} de {ano} no Canvas")
    else:
        pacote = pacotes[serie]
        if pacote.exige_sede:
            sede, erro = achar_sede(bruta.get("sede"), pacote.sedes)
            if erro:
                erros.append(erro)
        elif str(bruta.get("sede") or "").strip():
            avisos.append(f"sede ignorada: o {ROTULO_DA_SERIE[serie]} tem uma turma só no Canvas")

    return LinhaDoLote(
        linha=int(bruta.get("linha") or 0),
        matricula=matricula or str(bruta.get("matricula") or "").strip(),
        nome=nome,
        email=email,
        serie=serie,
        sede=sede,
        situacao="erro" if erros else "nova",
        erros=erros,
        avisos=avisos,
    )


def marcar_repetidas(linhas: list[LinhaDoLote]) -> None:
    """A mesma matrícula duas vezes no arquivo é erro nas DUAS linhas: não há
    como saber qual delas está certa."""
    vistas: dict[str, list[LinhaDoLote]] = {}
    for linha in linhas:
        if linha.matricula:
            vistas.setdefault(linha.matricula, []).append(linha)
    for repetidas in vistas.values():
        if len(repetidas) < 2:
            continue
        numeros = ", ".join(str(r.linha) for r in repetidas)
        for r in repetidas:
            r.erros.append(f"matrícula repetida no arquivo (linhas {numeros})")
            r.situacao = "erro"


@dataclass(frozen=True)
class ContaExistente:
    canvas_user_id: str
    nome: str


def aplicar_existentes(linhas: list[LinhaDoLote], existentes: dict[str, ContaExistente]) -> None:
    """Separa conta nova de conta que já existe — e cobra o e-mail só da nova."""
    for linha in linhas:
        if linha.situacao == "erro":
            continue
        conta = existentes.get(linha.matricula)
        if conta is None:
            if not linha.email:
                linha.erros.append("conta nova precisa de e-mail: é por ele que o aluno cria a senha")
                linha.situacao = "erro"
            continue
        linha.situacao = "existente"
        linha.nome_no_canvas = conta.nome
        if not nomes_batem(linha.nome, conta.nome):
            linha.avisos.append(
                f"no Canvas, a matrícula {linha.matricula} é de “{conta.nome}” — confira antes de enviar"
            )


# ─── O lote como SIS Import ───────────────────────────────────────────────


def montar_csv_usuarios(novas: list[LinhaDoLote]) -> str:
    """`users.csv` só com as contas NOVAS: mandar uma conta existente aqui
    reescreveria nome e e-mail dela — e a regra é não tocar no que existe."""
    saida = io.StringIO()
    escritor = csv.writer(saida, lineterminator="\n")
    escritor.writerow([
        "user_id", "login_id", "full_name", "email", "status",
        "authentication_provider_id", "canvas_password_notification",
    ])
    for linha in novas:
        escritor.writerow([
            linha.matricula, linha.matricula, linha.nome, linha.email or "", "active",
            # O e-mail de criar senha só sai com o provedor "canvas" explícito
            # (sis_csv.md, `canvas_password_notification`).
            "canvas", "true",
        ])
    return saida.getvalue()


def montar_csv_matriculas(linhas: list[LinhaDoLote], pacotes: dict[int, Pacote]) -> str:
    """`enrollments.csv` de todas as linhas válidas, novas e existentes.

    A section só vai no curso de provas, onde ela é a sede; nos outros fica
    vazia e o Canvas usa a padrão — que é a única que eles têm."""
    saida = io.StringIO()
    escritor = csv.writer(saida, lineterminator="\n")
    escritor.writerow(["course_id", "user_id", "role", "section_id", "status"])
    for linha in linhas:
        if linha.situacao == "erro" or linha.serie is None:
            continue
        pacote = pacotes[linha.serie]
        for curso in pacote.cursos:
            secao = ""
            if linha.sede is not None and curso == pacote.curso_de_provas:
                secao = linha.sede.sis_id or ""
            escritor.writerow([curso.sis_id or "", linha.matricula, "student", secao, "active"])
    return saida.getvalue()


def montar_zip_do_lote(linhas: list[LinhaDoLote], pacotes: dict[int, Pacote]) -> bytes:
    novas = [linha for linha in linhas if linha.situacao == "nova"]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as arquivo:
        if novas:
            arquivo.writestr("users.csv", montar_csv_usuarios(novas))
        arquivo.writestr("enrollments.csv", montar_csv_matriculas(linhas, pacotes))
    return buffer.getvalue()


def resumir_sis_import(importacao: dict[str, Any]) -> dict[str, Any]:
    """O SIS Import do Canvas no vocabulário da tela."""
    estado_canvas = importacao.get("workflow_state") or ""
    if estado_canvas in _IMPORT_EM_ANDAMENTO:
        estado = "processando"
    elif estado_canvas == "imported":
        estado = "concluido"
    elif estado_canvas == "imported_with_messages":
        estado = "concluido_com_avisos"
    else:
        estado = "falhou"
    contagem = (importacao.get("data") or {}).get("counts") or {}
    erros = [str(m[-1]) for m in importacao.get("processing_errors") or [] if m]
    avisos = [str(m[-1]) for m in importacao.get("processing_warnings") or [] if m]
    return {
        "id": str(importacao.get("id")),
        "estado": estado,
        "estado_canvas": estado_canvas,
        "progresso": importacao.get("progress"),
        "criado_em": importacao.get("created_at"),
        "terminado_em": importacao.get("ended_at"),
        "contas": contagem.get("users"),
        "matriculas": contagem.get("enrollments"),
        # A tela mostra as primeiras; o total diz se há mais.
        "erros": erros[:50],
        "avisos": avisos[:50],
        "total_erros": len(erros),
        "total_avisos": len(avisos),
    }


# ─── Conversa com o Canvas ────────────────────────────────────────────────


def abrir_canvas() -> ClienteCanvas:
    settings = get_settings()
    if not settings.canvas_base_url or not settings.canvas_api_token:
        raise CanvasIndisponivel("Canvas não configurado no servidor")
    return ClienteCanvas(base_url=settings.canvas_base_url, token=settings.canvas_api_token)


@dataclass(frozen=True)
class Catalogo:
    ano: int
    anos: list[int]
    pacotes: dict[int, Pacote]


async def carregar_catalogo(
    canvas: ClienteCanvas,
    *,
    account_id: str,
    ano: int | None,
    ano_configurado: str,
    ano_atual: int | None = None,
) -> Catalogo:
    """Os pacotes do ano pedido (ou do padrão), lidos agora do Canvas.

    Uma listagem de cursos e uma de sections por curso de provas do ano (três,
    hoje). Levanta LookupError se o ano pedido não tem curso nenhum."""
    cursos = await canvas.listar_cursos_para_cadastro(account_id)
    if ano_atual is None:
        ano_atual = datetime.now(ZoneInfo("America/Sao_Paulo")).year
    anos = anos_oferecidos(anos_dos_cursos(cursos), ano_atual=ano_atual)
    escolhido = ano if ano is not None else ano_padrao(anos, ano_configurado)
    if escolhido is None or escolhido not in anos:
        raise LookupError(
            f"Não há curso ITA/IME de {escolhido} no Canvas." if escolhido
            else "Não há curso ITA/IME de série nenhuma no Canvas."
        )
    de_provas = [
        str(c["id"])
        for c in cursos
        if (m := PADRAO_CURSO_DA_SERIE.match((c.get("name") or "").strip()))
        and int(m.group("ano")) == escolhido
        and _eh_curso_de_provas(c["name"].strip(), int(m.group("serie")))
    ]
    listas = await asyncio.gather(*(canvas.listar_sections(cid) for cid in de_provas))
    sections = dict(zip(de_provas, listas, strict=True))
    return Catalogo(
        ano=escolhido, anos=anos, pacotes=montar_pacotes(cursos, sections, ano=escolhido)
    )


async def descobrir_existentes(
    canvas: ClienteCanvas, matriculas: list[str], *, conhecidas: dict[str, ContaExistente]
) -> dict[str, ContaExistente]:
    """Quais destas matrículas já têm conta no Canvas.

    `conhecidas` vem do banco do SAS (`aluno` com `canvas_user_id`): quem o
    sync já trouxe certamente tem conta, e não custa chamada. Só o resto vai
    ao Canvas, uma chamada por matrícula — que, num lote de virada de ano, é
    só quem é aluno novo de verdade."""
    existentes = {m: conhecidas[m] for m in matriculas if m in conhecidas}
    perguntar = [m for m in matriculas if m not in existentes]
    respostas = await asyncio.gather(*(canvas.obter_usuario_por_sis(m) for m in perguntar))
    for matricula, usuario in zip(perguntar, respostas, strict=True):
        if usuario:
            existentes[matricula] = ContaExistente(
                canvas_user_id=str(usuario["id"]), nome=usuario.get("name") or ""
            )
    return existentes


class NomeNaoBate(Exception):
    """A matrícula já é de uma conta com outro nome. Nada foi escrito."""

    def __init__(self, nome_no_canvas: str) -> None:
        super().__init__(nome_no_canvas)
        self.nome_no_canvas = nome_no_canvas


class EmailObrigatorio(Exception):
    """Conta nova sem e-mail: o aluno não teria por onde criar a senha."""


class CanvasRecusou(Exception):
    """O Canvas recusou criar a conta; a mensagem é para a tela."""


def _mensagem_do_canvas(exc: httpx.HTTPStatusError) -> str:
    """A primeira mensagem legível do corpo de erro do Canvas."""
    try:
        corpo = exc.response.json()
    except ValueError:
        return f"HTTP {exc.response.status_code}"
    mensagens: list[str] = []

    def coletar(no: Any) -> None:
        if isinstance(no, dict):
            if isinstance(no.get("message"), str):
                mensagens.append(no["message"])
            for valor in no.values():
                coletar(valor)
        elif isinstance(no, list):
            for item in no:
                coletar(item)

    coletar(corpo)
    return mensagens[0] if mensagens else f"HTTP {exc.response.status_code}"


async def cadastrar_aluno(
    canvas: ClienteCanvas,
    *,
    account_id: str,
    pacote: Pacote,
    sede: Sede | None,
    matricula: str,
    nome: str,
    email: str | None,
    confirmar_nome: bool,
) -> dict[str, Any]:
    """Cria a conta (se não existe) e matricula no pacote. Repetível.

    Repetir depois de uma falha no meio é o conserto: a conta já existe, as
    matrículas que entraram são reconhecidas e só as que faltam são feitas."""
    conta = await canvas.obter_usuario_por_sis(matricula)
    ja_tinha: list[dict[str, Any]] = []
    if conta is not None:
        if not confirmar_nome and not nomes_batem(nome, conta.get("name") or ""):
            raise NomeNaoBate(conta.get("name") or "")
        criada = False
        ja_tinha = await canvas.listar_matriculas_ativas_do_usuario(str(conta["id"]))
    else:
        if not email:
            raise EmailObrigatorio()
        try:
            conta = await canvas.criar_usuario_aluno(
                account_id, nome=nome, matricula=matricula, email=email
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (400, 409, 422):
                raise CanvasRecusou(_mensagem_do_canvas(exc)) from exc
            raise
        criada = True
    user_id = str(conta["id"])

    # (curso, section já ocupada nele)
    ocupado: dict[str, str] = {
        str(m.get("course_id")): str(m.get("course_section_id")) for m in ja_tinha
    }

    async def um_curso(curso: Curso) -> dict[str, Any]:
        resultado: dict[str, Any] = {"id": curso.id, "nome": curso.nome}
        alvo_secao = sede.id if (sede is not None and curso == pacote.curso_de_provas) else None
        if curso.id in ocupado:
            if alvo_secao is None or ocupado[curso.id] == alvo_secao:
                return {**resultado, "estado": "ja_estava"}
            # Mudar de sede não é feito por aqui: acrescentar a section nova
            # deixaria o aluno em DUAS sedes, e o SAS o contaria nas duas.
            return {
                **resultado,
                "estado": "outra_sede",
                "detalhe": "já está neste curso em outra sede — mudança de sede se faz no Canvas",
            }
        try:
            await canvas.matricular_aluno(curso.id, user_id, section_id=alvo_secao)
        except httpx.HTTPStatusError as exc:
            return {**resultado, "estado": "falhou", "detalhe": _mensagem_do_canvas(exc)}
        except (httpx.TimeoutException, httpx.TransportError):
            return {**resultado, "estado": "falhou", "detalhe": "Canvas fora de alcance"}
        return {**resultado, "estado": "matriculado"}

    cursos = await asyncio.gather(*(um_curso(c) for c in pacote.cursos))
    return {
        "matricula": matricula,
        "nome": nome,
        "canvas_user_id": user_id,
        "conta": "criada" if criada else "existente",
        "nome_no_canvas": None if criada else (conta.get("name") or None),
        "email_enviado": criada,
        "ano": pacote.ano,
        "serie": pacote.serie,
        "sede": sede.nome if sede else None,
        "cursos": list(cursos),
        "completo": all(c["estado"] in ("matriculado", "ja_estava") for c in cursos),
    }
