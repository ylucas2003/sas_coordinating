"""O nome do arquivo de patch vira o prefixo do id da questão.

`banco-questoes/patches/ita_2008_fase1.json` com a chave `q11` significa a
questão `ita_2008_fase1_q11`. É uma convenção implícita — o patch não diz o id
inteiro —, e quando ela quebra o script não falha: ele não encontra questão
nenhuma e relata "0 a classificar", que parece sucesso. Daí o teste.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.aplicar_patches_de_classificacao import _questoes_do_patch


def test_o_nome_do_arquivo_prefixa_o_id(tmp_path):
    arquivo = tmp_path / "ita_2008_fase1.json"
    arquivo.write_text(
        json.dumps({"q11": {"topicos_ids": ["13.1", "4.1"], "confianca": "alta"}}),
        encoding="utf-8",
    )
    assert _questoes_do_patch(arquivo) == {
        "ita_2008_fase1_q11": {"topicos_ids": ["13.1", "4.1"], "confianca": "alta"}
    }


def test_chave_de_metadado_nao_vira_questao(tmp_path):
    """`_comentario` e afins são notas de quem classificou, não questões.

    Sem o filtro elas viram um id inexistente, e o script relata "não existe
    neste banco" para algo que nunca foi questão — ruído que esconde o aviso
    de verdade.
    """
    arquivo = tmp_path / "ime_2022_fase1_qui.json"
    arquivo.write_text(
        json.dumps({
            "_nota": "conferido contra a prova impressa",
            "q31": {"topicos_ids": ["10.1"]},
        }),
        encoding="utf-8",
    )
    assert list(_questoes_do_patch(arquivo)) == ["ime_2022_fase1_qui_q31"]


def test_os_patches_do_repositorio_descrevem_as_44(tmp_path):
    """As seis provas de 04/09 somam 44 questões, e é o número do docs/35 §3.

    Se alguém acrescentar um patch e o total mudar sem o documento mudar, é
    aqui que aparece — foi um número cravado que envelheceu em silêncio que
    deixou 44 questões sem assunto por duas semanas.
    """
    patches = sorted((Path(__file__).resolve().parent.parent.parent
                      / "banco-questoes" / "patches").glob("*.json"))
    assert len(patches) == 6
    total = sum(len(_questoes_do_patch(p)) for p in patches)
    assert total == 44
