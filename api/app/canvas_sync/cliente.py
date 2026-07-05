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
        )
        self._semaforo = asyncio.Semaphore(concorrencia_maxima)

    async def fechar(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> "ClienteCanvas":
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

    async def listar_canais_de_comunicacao(self, user_id: str) -> list[dict[str, Any]]:
        """Canais de contato do usuário (email/push). Uma chamada POR aluno —
        usar só no backfill ou em lotes pequenos no incremental."""
        return await self._get_paginado(f"/users/{user_id}/communication_channels")

    async def obter_estatisticas_quiz(self, course_id: str, quiz_id: str) -> dict[str, Any]:
        resposta = await self._get(f"/courses/{course_id}/quizzes/{quiz_id}/statistics")
        return resposta.json()
