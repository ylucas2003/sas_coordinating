"""Ensaio da escrita do cadastro no Canvas de verdade, no curso sandbox (docs/46 §5).

`tests/test_cadastro_canvas.py` prova a lógica com um Canvas falso. O que ele
não prova é o contrato HTTP: se o Canvas aceita o corpo de `criar_usuario_aluno`,
quantos e-mails de cadastro chegam (e qual), se o SIS Import com
`canvas_password_notification` faz o mesmo, e o que acontece quando a mesma
matrícula é POSTada duas vezes. Isso só se vê escrevendo — e escrever num dos
19 cursos reais do 3º poria um aluno de mentira na lista de todos os
professores.

Por isso o ensaio só toca o curso sandbox 694 "SAS · testes (não usar)":

  1. cria uma conta pela rota REST (o "um por vez") e a matricula no 694,
     duas vezes, para ver se o Canvas duplica;
  2. dá ao 694 uma SIS ID temporária (o SIS Import só fala em SIS ID) e cria
     uma segunda conta pelo SIS Import (o "lote");
  3. desfaz tudo: apaga as duas contas e tira a SIS ID — a não ser com
     `--manter`, para olhar no Canvas antes.

    python -m scripts.ensaio_cadastro_canvas --email voce@exemplo.com
    python -m scripts.ensaio_cadastro_canvas --email voce@exemplo.com --manter

O e-mail recebe os convites do Canvas: use um que você leia, e conte quantos
chegam de cada conta. ⚠️ Roda contra o Canvas de PRODUÇÃO do colégio — é o
único que existe. Só com autorização de quem o administra.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from typing import Any

CURSO_SANDBOX = "694"
SIS_DO_ENSAIO = "SAS-ENSAIO-694"


def _linha(titulo: str, valor: Any = "") -> None:
    print(f"  {titulo:<38} {valor}")


async def _ensaiar(email: str, manter: bool) -> int:
    from app.canvas_sync import cadastro
    from app.canvas_sync.cliente import ClienteCanvas

    conta = os.environ.get("CANVAS_ACCOUNT_ID", "1")
    canvas = ClienteCanvas(
        base_url=os.environ["CANVAS_BASE_URL"], token=os.environ["CANVAS_API_TOKEN"]
    )
    criados: list[str] = []
    sis_definida = False
    async with canvas:
        curso = await canvas.obter_curso(CURSO_SANDBOX)
        if "testes" not in (curso.get("name") or "").lower():
            print(f"O curso {CURSO_SANDBOX} não é o sandbox ({curso.get('name')!r}). Parei.")
            return 2
        if curso.get("sis_course_id") not in (None, "", SIS_DO_ENSAIO):
            print(f"O sandbox já tem SIS ID {curso['sis_course_id']!r}; não vou trocar. Parei.")
            return 2

        # 9 + 7 dígitos do relógio: oito dígitos, como as reais, e nenhuma
        # matrícula real começa com 9 (2026: todas começam com 2).
        base = int(time.time()) % 10**7
        m_rest, m_sis = f"9{base:07d}", f"9{(base + 1) % 10**7:07d}"
        for m in (m_rest, m_sis):
            if await canvas.obter_usuario_por_sis(m) is not None:
                print(f"A matrícula de teste {m} já existe no Canvas. Rode de novo.")
                return 2

        try:
            print("\n1 · Um por vez (REST)")
            usuario = await canvas.criar_usuario_aluno(
                conta, nome="Ensaio Cadastro SAS Rest", matricula=m_rest, email=email
            )
            criados.append(str(usuario["id"]))
            _linha("conta criada", f"id {usuario['id']} · login {m_rest}")
            primeira = await canvas.matricular_aluno(CURSO_SANDBOX, str(usuario["id"]))
            _linha("1ª matrícula", f"id {primeira.get('id')} · {primeira.get('enrollment_state')}")
            segunda = await canvas.matricular_aluno(CURSO_SANDBOX, str(usuario["id"]))
            _linha("2ª matrícula (mesmo POST)", f"id {segunda.get('id')} · {segunda.get('enrollment_state')}")
            ativas = await canvas.listar_matriculas_ativas_do_usuario(str(usuario["id"]))
            _linha("matrículas ativas no sandbox", sum(1 for a in ativas if str(a.get("course_id")) == CURSO_SANDBOX))
            _linha("o Canvas duplicou?", "SIM" if primeira.get("id") != segunda.get("id") else "não — devolveu a mesma")

            print("\n2 · Em lote (SIS Import)")
            await canvas.definir_sis_do_curso(CURSO_SANDBOX, SIS_DO_ENSAIO)
            sis_definida = True
            _linha("SIS ID temporária no sandbox", SIS_DO_ENSAIO)
            linha = cadastro.LinhaDoLote(
                linha=2, matricula=m_sis, nome="Ensaio Cadastro SAS Lote", email=email,
                serie=3, sede=None,
            )
            pacote = cadastro.Pacote(
                ano=0, serie=3,
                cursos=(cadastro.Curso(id=CURSO_SANDBOX, nome=curso["name"], sis_id=SIS_DO_ENSAIO),),
                curso_de_provas=None, sedes=(),
            )
            importacao = await canvas.enviar_sis_import(
                conta, arquivo_zip=cadastro.montar_zip_do_lote([linha], {3: pacote})
            )
            _linha("SIS Import", f"id {importacao['id']}")
            for _ in range(60):
                resumo = cadastro.resumir_sis_import(
                    await canvas.obter_sis_import(conta, str(importacao["id"]))
                )
                if resumo["estado"] != "processando":
                    break
                await asyncio.sleep(5)
            _linha("estado", f"{resumo['estado']} ({resumo['estado_canvas']})")
            _linha("contagem", f"{resumo['contas']} conta(s) · {resumo['matriculas']} matrícula(s)")
            for mensagem in resumo["erros"] + resumo["avisos"]:
                _linha("·", mensagem)
            pelo_lote = await canvas.obter_usuario_por_sis(m_sis)
            if pelo_lote:
                criados.append(str(pelo_lote["id"]))
                _linha("conta pelo lote", f"id {pelo_lote['id']} · login {pelo_lote.get('login_id')}")
        finally:
            print("\n3 · Limpeza")
            if manter:
                _linha("--manter", f"contas {', '.join(criados) or '—'} ficaram; SIS ID ficou")
            else:
                for user_id in criados:
                    await canvas.apagar_usuario_da_conta(conta, user_id)
                    _linha("conta apagada", user_id)
                if sis_definida:
                    await canvas.definir_sis_do_curso(CURSO_SANDBOX, "")
                    _linha("SIS ID do sandbox", "tirada")

    print("\nConfira na caixa do e-mail quantos convites chegaram de cada conta (docs/46 §5).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--email", required=True, help="e-mail que recebe os convites do Canvas")
    parser.add_argument("--manter", action="store_true", help="não apaga nada no fim")
    args = parser.parse_args()

    from dotenv import load_dotenv

    load_dotenv()
    if not os.environ.get("CANVAS_BASE_URL") or not os.environ.get("CANVAS_API_TOKEN"):
        print("CANVAS_BASE_URL e CANVAS_API_TOKEN precisam estar no ambiente.")
        return 2
    return asyncio.run(_ensaiar(args.email.strip(), args.manter))


if __name__ == "__main__":
    sys.exit(main())
