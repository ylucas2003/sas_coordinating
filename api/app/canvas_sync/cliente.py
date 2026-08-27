"""Cliente HTTP para a REST API do Canvas.

Wrapper fino e sem regra de negócio — mapeamento e orquestração vivem em
mapeador.py / sincronizar.py. Trata as duas mecânicas chatas da API:

  - Paginação via header `Link` (rel="next") — ver docs/canvas-api/guides/pagination.md.
  - Rate limit: o Canvas devolve 403 com X-Rate-Limit-Remaining zerado quando
    há requisições demais em paralelo; limitamos com um semáforo + retry.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

import httpx

_PADRAO_LINK_NEXT = re.compile(r'<([^>]+)>;\s*rel="next"')

_TENTATIVAS = 3


class ClienteCanvas:
    def __init__(
        self,
        *,
        base_url: str,
        token: str,
        timeout: float = 60.0,
        concorrencia_maxima: int = 8,
    ) -> None:
        if not base_url or not token:
            raise ValueError("CANVAS_BASE_URL e CANVAS_API_TOKEN precisam estar configurados.")
        self._http = httpx.AsyncClient(
            base_url=f"{base_url.rstrip('/')}/api/v1",
            headers={"Authorization": f"Bearer {token}"},
            timeout=timeout,
            # Download de Course File redireciona (302) pro host de CDN
            # (canvas-user-content.com) com auth via verifier na própria URL —
            # sem seguir redirect, baixar_bytes() nunca chega no arquivo.
            follow_redirects=True,
        )
        self._semaforo = asyncio.Semaphore(concorrencia_maxima)

    async def fechar(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> ClienteCanvas:
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.fechar()

    # ─── Núcleo: GET com retry + paginação ───────────────────────────────

    async def _get(self, url: str, *, params: dict[str, Any] | None = None) -> httpx.Response:
        async with self._semaforo:
            ultima_excecao: Exception | None = None
            resposta: httpx.Response | None = None
            for tentativa in range(_TENTATIVAS):
                try:
                    resposta = await self._http.get(url, params=params)
                except (httpx.TimeoutException, httpx.TransportError) as exc:
                    # Página lenta em paginação profunda / rede instável —
                    # tão retryável quanto um 5xx.
                    ultima_excecao = exc
                    await asyncio.sleep(2**tentativa)
                    continue
                if resposta.status_code in (403, 429) or resposta.status_code >= 500:
                    await asyncio.sleep(2**tentativa)
                    continue
                resposta.raise_for_status()
                return resposta
            if resposta is None:
                raise ultima_excecao or RuntimeError("GET ao Canvas falhou sem resposta")
            resposta.raise_for_status()
            return resposta

    # ─── Escrita: POST sem retry, PUT/DELETE com ─────────────────────────
    #
    # POST não repete DE PROPÓSITO: (a) não há chave de idempotência na API
    # do Canvas — repetir um POST que talvez tenha chegado cria objeto
    # duplicado; (b) a política do _get trata 403 como rate limit, mas 403
    # num POST é "sem permissão" e repetir só atrasa o erro. Falha de POST
    # vira estado no banco (canvas_estado='falhou') e o reprocessamento do
    # sync resolve — ver agendamento.py.

    async def _post(self, caminho: str, *, json: dict[str, Any]) -> httpx.Response:
        async with self._semaforo:
            resposta = await self._http.post(caminho, json=json)
            resposta.raise_for_status()
            return resposta

    async def _put(self, caminho: str, *, json: dict[str, Any]) -> httpx.Response:
        """PUT é idempotente — repetir é seguro, mesma política de retry do _get."""
        async with self._semaforo:
            ultima_excecao: Exception | None = None
            resposta: httpx.Response | None = None
            for tentativa in range(_TENTATIVAS):
                try:
                    resposta = await self._http.put(caminho, json=json)
                except (httpx.TimeoutException, httpx.TransportError) as exc:
                    ultima_excecao = exc
                    await asyncio.sleep(2**tentativa)
                    continue
                if resposta.status_code == 429 or resposta.status_code >= 500:
                    await asyncio.sleep(2**tentativa)
                    continue
                resposta.raise_for_status()
                return resposta
            if resposta is None:
                raise ultima_excecao or RuntimeError("PUT ao Canvas falhou sem resposta")
            resposta.raise_for_status()
            return resposta

    async def _delete(self, caminho: str) -> httpx.Response:
        """DELETE é idempotente; 404 conta como sucesso (o objeto já não existe)."""
        async with self._semaforo:
            resposta = await self._http.delete(caminho)
            if resposta.status_code != 404:
                resposta.raise_for_status()
            return resposta

    async def _get_paginado(
        self,
        caminho: str,
        *,
        params: dict[str, Any] | None = None,
        per_page: int = 100,
    ) -> list[dict[str, Any]]:
        """Segue rel="next" do header Link até esgotar as páginas."""
        resultados: list[dict[str, Any]] = []
        resposta = await self._get(caminho, params={**(params or {}), "per_page": per_page})
        while True:
            resultados.extend(resposta.json())
            link = resposta.headers.get("link", "")
            m = _PADRAO_LINK_NEXT.search(link)
            if not m:
                return resultados
            # A URL de next já vem absoluta e com todos os params embutidos.
            resposta = await self._get(m.group(1))

    # ─── Endpoints usados pelo sync ──────────────────────────────────────

    async def listar_cursos_da_conta(
        self, account_id: str, *, search_term: str | None = None
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"state[]": ["available"]}
        if search_term:
            params["search_term"] = search_term
        return await self._get_paginado(f"/accounts/{account_id}/courses", params=params)

    async def listar_sections(self, course_id: str) -> list[dict[str, Any]]:
        return await self._get_paginado(f"/courses/{course_id}/sections")

    async def listar_matriculas_de_alunos(self, course_id: str) -> list[dict[str, Any]]:
        return await self._get_paginado(
            f"/courses/{course_id}/enrollments",
            params={
                "type[]": ["StudentEnrollment"],
                "state[]": ["active", "completed"],
                "include[]": ["avatar_url"],
            },
        )

    async def listar_grupos_de_avaliacao(self, course_id: str) -> list[dict[str, Any]]:
        return await self._get_paginado(f"/courses/{course_id}/assignment_groups")

    async def listar_assignments(self, course_id: str) -> list[dict[str, Any]]:
        return await self._get_paginado(f"/courses/{course_id}/assignments")

    async def listar_submissions(
        self, course_id: str, *, graded_since: str | None = None
    ) -> list[dict[str, Any]]:
        """Todas as submissions de todos os alunos do curso, todos os assignments.

        `graded_since` (ISO 8601) restringe a notas corrigidas desde então —
        é o que torna o sync incremental de 5 min barato.
        """
        params: dict[str, Any] = {"student_ids[]": ["all"]}
        if graded_since:
            params["graded_since"] = graded_since
        return await self._get_paginado(
            f"/courses/{course_id}/students/submissions", params=params
        )

    async def listar_usuarios_do_curso(self, course_id: str) -> list[dict[str, Any]]:
        """Alunos do curso com e-mail incluído — UMA chamada paginada cobre o
        curso inteiro (barato o bastante para o incremental de 5 min).

        O campo `email` só vem se o token tiver permissão de ler perfis; para
        os que vierem sem, o fallback é Communication Channels."""
        return await self._get_paginado(
            f"/courses/{course_id}/users",
            params={
                "enrollment_type[]": ["student"],
                "include[]": ["email"],
            },
        )

    async def buscar_usuarios_da_conta(
        self, account_id: str, *, termo: str
    ) -> list[dict[str, Any]]:
        """Busca por nome, e-mail ou login. É como o SAS descobre o id interno
        de um coordenador a partir do e-mail — número que ninguém decora e que
        o login pelo Canvas devolve (docs/18 §4.2)."""
        return await self._get_paginado(
            f"/accounts/{account_id}/users", params={"search_term": termo}
        )

    async def obter_perfil(self, user_id: str) -> dict[str, Any]:
        """Perfil com `primary_email` — só o token de admin enxerga isso; o
        token do próprio usuário no SSO não tem esse escopo."""
        return (await self._get(f"/users/{user_id}/profile")).json()

    async def listar_canais_de_comunicacao(self, user_id: str) -> list[dict[str, Any]]:
        """Canais de contato do usuário (email/push). Uma chamada POR aluno —
        usar só no backfill ou em lotes pequenos no incremental."""
        return await self._get_paginado(f"/users/{user_id}/communication_channels")

    async def obter_estatisticas_quiz(self, course_id: str, quiz_id: str) -> dict[str, Any]:
        resposta = await self._get(f"/courses/{course_id}/quizzes/{quiz_id}/statistics")
        return resposta.json()

    async def listar_pastas(self, course_id: str) -> list[dict[str, Any]]:
        """Árvore inteira de pastas do curso, achatada (campo `full_name` dá o
        caminho). Anos antigos ficam em subpasta (`1° CICLO/2025`) — quem usa
        isso filtra pelo último segmento do `full_name` pra ignorá-las."""
        return await self._get_paginado(f"/courses/{course_id}/folders")

    async def listar_arquivos_da_pasta(self, folder_id: str) -> list[dict[str, Any]]:
        """Arquivos DIRETOS da pasta — não recursa em subpastas (é assim que
        as pastas de ano antigo dentro de uma pasta de ciclo ficam de fora)."""
        return await self._get_paginado(f"/folders/{folder_id}/files")

    async def listar_conferencias(self, course_id: str) -> list[dict[str, Any]]:
        """Conferências (BigBlueButton) do curso, com gravações se houver —
        usado por app/gravacoes_aula/ pra detectar aula nova e achar a URL de
        replay (`recordings[].playback_formats[0].url`).

        Resposta vem envelopada em {"conferences": [...]}, diferente dos
        demais endpoints deste cliente — por isso NÃO usa _get_paginado (que
        assume array puro). Um curso não passa de ~100 conferências/ano;
        per_page=100 já cobre isso numa página só."""
        resposta = await self._get(
            f"/courses/{course_id}/conferences", params={"per_page": 100}
        )
        return resposta.json().get("conferences", [])

    # ─── Endpoints usados pelo agendamento (P1 — escrita SAS → Canvas) ────

    async def criar_assignment_group(self, course_id: str, *, nome: str) -> dict[str, Any]:
        resposta = await self._post(
            f"/courses/{course_id}/assignment_groups", json={"name": nome}
        )
        return resposta.json()

    async def criar_assignment(
        self, course_id: str, *, assignment: dict[str, Any]
    ) -> dict[str, Any]:
        resposta = await self._post(
            f"/courses/{course_id}/assignments", json={"assignment": assignment}
        )
        return resposta.json()

    async def atualizar_assignment(
        self, course_id: str, assignment_id: str, *, assignment: dict[str, Any]
    ) -> dict[str, Any]:
        resposta = await self._put(
            f"/courses/{course_id}/assignments/{assignment_id}",
            json={"assignment": assignment},
        )
        return resposta.json()

    async def atualizar_nota_submission(
        self,
        course_id: str,
        assignment_id: str,
        user_id: str,
        *,
        posted_grade: float | str | None = None,
        marcar_ausente: bool | None = None,
    ) -> dict[str, Any]:
        """Grava a nota de um aluno num Assignment.

        `posted_grade` vai na escala de pontos do Assignment (a mesma que o SAS
        guarda em nota.pontuacao); string vazia apaga a nota.

        `marcar_ausente=True` seta late_policy_status='missing' — é o que o sync
        lê de volta em derivar_presente(). Preferido a `excused`, que no Canvas
        significa "dispensado, não conta", e não "faltou". False limpa a marca;
        None não mexe.

        Nota: marcar presente SEM enviar nota não gruda no round-trip — a
        submission continua 'unsubmitted', que derivar_presente() lê como
        ausente. Enviar nota move o workflow_state para 'graded' e resolve.
        """
        submission: dict[str, Any] = {}
        if posted_grade is not None:
            submission["posted_grade"] = posted_grade
        if marcar_ausente is not None:
            submission["late_policy_status"] = "missing" if marcar_ausente else "none"
        if not submission:
            raise ValueError("atualizar_nota_submission chamado sem nada para alterar")

        resposta = await self._put(
            f"/courses/{course_id}/assignments/{assignment_id}/submissions/{user_id}",
            json={"submission": submission},
        )
        return resposta.json()

    async def apagar_assignment(self, course_id: str, assignment_id: str) -> None:
        await self._delete(f"/courses/{course_id}/assignments/{assignment_id}")

    async def buscar_assignment_por_nome(
        self, course_id: str, nome: str
    ) -> dict[str, Any] | None:
        """Match EXATO de nome, ou None. Usado pelo reprocessamento antes de
        re-POSTar: um POST que deu timeout pode ter criado o Assignment mesmo
        assim, e recriar às cegas duplicaria a prova no Canvas."""
        candidatos = await self._get_paginado(
            f"/courses/{course_id}/assignments", params={"search_term": nome}
        )
        for candidato in candidatos:
            if (candidato.get("name") or "").strip() == nome:
                return candidato
        return None

    async def baixar_bytes(self, url: str) -> bytes:
        """Baixa o conteúdo bruto de uma download URL absoluta do Canvas —
        reaproveita o mesmo retry/semáforo de `_get` usado pro Link de paginação."""
        resposta = await self._get(url)
        return resposta.content
