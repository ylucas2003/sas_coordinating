"""Os roteiros do assistente — o método de cada tarefa, sob demanda (docs/43 §4.3).

Três coisas se trancam aqui:

  1. o FORMATO, que falha fechado no import (cabeçalho torto derruba o boot,
     e não a conversa);
  2. o CONTEÚDO que importa — os do aluno repetem as regras duras, e o de
     explicar questão manda buscar a resolução oficial ANTES de explicar
     (docs/27 §10); toda tool que um roteiro cita existe, e no escopo certo;
  3. o CONTRATO que o servidor MCP consome (`listar`, `obter`, `Roteiro`), que
     não muda depois de publicado.

Rodar:  cd api && APP_ENV=dev ./.venv/bin/python -m pytest tests/test_chat_roteiros.py -q
"""

import dataclasses
import inspect
import re
import warnings

import pytest

from app.chat import roteiros
from app.chat.ferramentas import REGISTRO, Sessao

ALUNO = Sessao(tipo="aluno", usuario="aluno:a1", aluno_id="a1", nome="Ana")
COORDENACAO = Sessao(tipo="coordenador", usuario="coord:c1", papel="coordenador")
SESSAO = {"aluno": ALUNO, "coordenacao": COORDENACAO}

#: Tool citada no roteiro = nome entre crases. Parâmetro e valor vão sem crase.
_CITADA = re.compile(r"`([a-z][a-z0-9_]*)`")

#: As tools que o docs/43 §4.3 encomendou em 24/10 e que estavam sendo escritas
#: AO MESMO TEMPO que os roteiros. Enquanto uma delas não estiver no registro, o
#: teste de citação a tolera e AVISA; quando todas existirem, este conjunto pode
#: sair e o teste fica estrito. Um nome fora daqui e fora do registro reprova.
_ENCOMENDADAS_EM_24_10 = {
    "aluno": {
        "meu_panorama", "minha_zona", "minha_agenda_do_ciclo", "minha_trajetoria",
        "distribuicao_do_simulado", "o_que_mais_cai", "missao_de_hoje",
        "questoes_do_banco", "resolucao_oficial", "meu_progresso_no_banco",
    },
    "coordenacao": {
        "topicos_do_edital", "buscar_questoes_do_banco", "recorrencia_no_banco",
        "reguas_de_corte", "cortados_pela_regua", "estado_do_sync_canvas",
        "pendencias_canvas_do_ciclo", "estado_das_gravacoes", "historico_de_alteracoes",
        "lembretes_agendados", "buscar_aluno_por_matricula",
    },
}

PEDIDOS = {
    "aluno": {"revisar_simulado", "plano_da_semana", "explicar_questao", "antes_da_prova"},
    "coordenacao": {"diagnostico_do_ciclo", "alunos_em_risco", "preparar_reuniao", "conferir_a_regua"},
}

TODOS = [(e, r) for e in roteiros.ESCOPOS for r in roteiros.listar(e)]


def _id(par):
    return f"{par[0]}/{par[1].nome}"


class ClienteIntocavel:
    def table(self, *_args, **_kwargs):
        raise AssertionError("roteiro não lê banco")


# ─── O que existe ─────────────────────────────────────────────────────────


class TestCatalogo:
    def test_os_roteiros_pedidos_existem(self):
        for escopo, nomes in PEDIDOS.items():
            assert {r.nome for r in roteiros.listar(escopo)} == nomes

    def test_listar_vem_em_ordem_de_nome(self):
        for escopo in roteiros.ESCOPOS:
            nomes = [r.nome for r in roteiros.listar(escopo)]
            assert nomes == sorted(nomes)

    def test_obter_fica_no_escopo(self):
        """O nome de um roteiro da coordenação não abre nada no escopo do aluno."""
        assert roteiros.obter("aluno", "revisar_simulado").escopo == "aluno"
        assert roteiros.obter("aluno", "diagnostico_do_ciclo") is None
        assert roteiros.obter("coordenacao", "explicar_questao") is None
        assert roteiros.obter("cantina", "revisar_simulado") is None
        assert roteiros.listar("cantina") == []

    @pytest.mark.parametrize("par", TODOS, ids=_id)
    def test_cada_roteiro_cabe_em_40_linhas(self, par):
        escopo, roteiro = par
        arquivo = roteiros.PASTA_DOS_ROTEIROS / escopo / f"{roteiro.nome}.md"
        assert len(arquivo.read_text(encoding="utf-8").splitlines()) <= 40


# ─── O conteúdo ───────────────────────────────────────────────────────────


class TestConteudo:
    @pytest.mark.parametrize("par", TODOS, ids=_id)
    def test_toda_tool_citada_existe_no_mesmo_escopo(self, par):
        """Roteiro que cita tool inexistente manda o modelo chamar o vazio — e
        gasta uma volta inteira no erro. Tool do OUTRO escopo é pior: o aluno
        receberia "não existe" (invariante 1), e o roteiro diria que existe."""
        escopo, roteiro = par
        citadas = set(_CITADA.findall(roteiro.texto))
        do_escopo = {f.nome for f in REGISTRO.catalogo(escopo)}
        outro = "coordenacao" if escopo == "aluno" else "aluno"
        do_outro = {f.nome for f in REGISTRO.catalogo(outro)}

        assert citadas, "roteiro que não cita tool nenhuma não é método"
        assert not citadas & do_outro, f"cita tool do escopo {outro}: {sorted(citadas & do_outro)}"
        desconhecidas = citadas - do_escopo - _ENCOMENDADAS_EM_24_10[escopo]
        assert not desconhecidas, f"cita tool que não existe: {sorted(desconhecidas)}"

        ainda_nao = sorted(citadas - do_escopo)
        if ainda_nao:
            warnings.warn(
                f"{escopo}/{roteiro.nome} cita tools encomendadas que ainda não estão "
                f"no registro: {', '.join(ainda_nao)}",
                stacklevel=1,
            )

    def test_nada_encomendado_existe_no_escopo_errado(self):
        for escopo, nomes in _ENCOMENDADAS_EM_24_10.items():
            outro = "coordenacao" if escopo == "aluno" else "aluno"
            assert not nomes & {f.nome for f in REGISTRO.catalogo(outro)}

    @pytest.mark.parametrize("roteiro", roteiros.listar("aluno"), ids=lambda r: r.nome)
    def test_os_do_aluno_repetem_as_regras_duras(self, roteiro):
        """Só os dados dele, comparação só com agregado, a régua é dado, e o
        que é mock (docs/26) não existe para o mentor."""
        texto = roteiro.texto
        assert "só enxerga os dados deste aluno" in texto
        assert "Comparação só com agregados da turma" in texto
        assert "nunca com um colega" in texto
        assert "A régua é dado" in texto
        for mock in ("XP", "liga", "conquistas"):
            assert mock in texto
        assert "não existem no SAS" in texto

    def test_explicar_questao_busca_a_resolucao_oficial_antes(self):
        """docs/27 §10: a fórmula bonita e errada é o risco que ninguém vê."""
        texto = roteiros.obter("aluno", "explicar_questao").texto
        chamada = texto.index("Chame `resolucao_oficial` antes de escrever qualquer conta")
        assert chamada < texto.index("Diga a origem da resolução")
        assert "Nunca derive a conta do zero quando existe resolução" in texto
        # As três origens, cada uma com o que fazer.
        for origem in ("do professor do Ari", "sugerida", "nenhuma"):
            assert origem in texto
        assert "gerada por IA" in texto

    @pytest.mark.parametrize("roteiro", roteiros.listar("coordenacao"), ids=lambda r: r.nome)
    def test_os_da_coordenacao_servem_tambem_fora_do_app(self, roteiro):
        """Viram prompts do MCP (docs/43 §5.1), onde nem toda tool está exposta."""
        assert "não estiver disponível nesta conexão" in roteiro.texto
        assert "diga sempre qual régua está em uso" in roteiro.texto


# ─── As tools ─────────────────────────────────────────────────────────────


class TestTools:
    @pytest.mark.parametrize(
        "escopo,tool", [("aluno", "roteiro_do_mentor"), ("coordenacao", "roteiro_da_coordenacao")]
    )
    def test_a_tool_entrega_o_texto_sem_ler_banco(self, escopo, tool):
        for roteiro in roteiros.listar(escopo):
            resultado = REGISTRO.despachar(
                SESSAO[escopo], tool, ClienteIntocavel(), {"nome": roteiro.nome}
            )
            assert resultado["nome"] == roteiro.nome
            assert resultado["titulo"] == roteiro.titulo
            assert resultado["roteiro"] == roteiro.texto
            assert "Não copie o roteiro" in resultado["comoUsar"]

    @pytest.mark.parametrize(
        "escopo,tool", [("aluno", "roteiro_do_mentor"), ("coordenacao", "roteiro_da_coordenacao")]
    )
    def test_o_enum_e_a_descricao_saem_dos_arquivos(self, escopo, tool):
        f = REGISTRO.obter(SESSAO[escopo], tool)
        assert f.propriedades["nome"]["enum"] == [r.nome for r in roteiros.listar(escopo)]
        assert f.parametros["required"] == ["nome"]
        for roteiro in roteiros.listar(escopo):
            assert f"- {roteiro.nome}: {roteiro.descricao}" in f.descricao

    def test_nome_do_outro_escopo_e_erro_de_argumento(self):
        """O enum é conferido no despacho (invariante 3), antes do handler."""
        resultado = REGISTRO.despachar(
            ALUNO, "roteiro_do_mentor", ClienteIntocavel(), {"nome": "diagnostico_do_ciclo"}
        )
        assert "'nome' deve ser um de" in resultado["erro"]

    def test_o_aluno_nao_alcanca_a_tool_da_coordenacao(self):
        resultado = REGISTRO.despachar(
            ALUNO, "roteiro_da_coordenacao", ClienteIntocavel(), {"nome": "alunos_em_risco"}
        )
        assert resultado == {"erro": "tool 'roteiro_da_coordenacao' não existe"}

    def test_o_handler_chamado_direto_recusa_nome_inventado(self):
        """O MCP chama o domínio sem passar pelo despacho do chat."""
        resultado = roteiros.roteiro_da_coordenacao(None, nome="inventado")
        assert "Não existe o roteiro 'inventado'" in resultado["erro"]
        assert "alunos_em_risco" in resultado["erro"]

    def test_o_modulo_nao_escreve_no_banco(self):
        """A mesma régua de test_chat_tools.py: o registro só tem tool de leitura."""
        fonte = inspect.getsource(roteiros)
        for escrita in (".insert(", ".update(", ".upsert(", ".delete("):
            assert escrita not in fonte


# ─── O contrato do MCP ────────────────────────────────────────────────────


class TestContrato:
    def test_roteiro_tem_os_cinco_campos_publicados(self):
        campos = [c.name for c in dataclasses.fields(roteiros.Roteiro)]
        assert campos == ["nome", "titulo", "descricao", "escopo", "texto"]
        assert roteiros.Roteiro.__dataclass_params__.frozen

    def test_listar_e_obter_tem_a_assinatura_publicada(self):
        assert list(inspect.signature(roteiros.listar).parameters) == ["escopo"]
        assert list(inspect.signature(roteiros.obter).parameters) == ["escopo", "nome"]


# ─── O formato, que falha fechado ─────────────────────────────────────────


def _arquivo(pasta, nome, conteudo):
    caminho = pasta / f"{nome}.md"
    caminho.write_text(conteudo, encoding="utf-8")
    return caminho


VALIDO = "---\nnome: {nome}\ntitulo: Um título\ndescricao: Quando usar.\n---\n1. Faça isto.\n"


class TestFormato:
    def test_arquivo_valido(self, tmp_path):
        r = roteiros.ler_roteiro(_arquivo(tmp_path, "um_roteiro", VALIDO.format(nome="um_roteiro")), "aluno")
        assert (r.nome, r.titulo, r.descricao, r.escopo, r.texto) == (
            "um_roteiro", "Um título", "Quando usar.", "aluno", "1. Faça isto.",
        )

    @pytest.mark.parametrize(
        "conteudo,trecho",
        [
            ("nome: x\n1. sem cabeçalho\n", "começa pelo cabeçalho"),
            ("---\nnome: x\ntitulo: t\ndescricao: d\n1. sem fechar\n", "fechamento"),
            ("---\nnome: x\ntitulo: t\ndescricao: d\nautor: eu\n---\n1. a\n", "linha de cabeçalho inválida"),
            ("---\nnome: x\ntitulo: t\ndescricao d\n---\n1. a\n", "linha de cabeçalho inválida"),
            ("---\nnome: x\ntitulo: t\n---\n1. a\n", "falta descricao"),
            ("---\nnome: x\ntitulo: t\ntitulo: u\ndescricao: d\n---\n1. a\n", "duas vezes"),
            ("---\nnome: outro\ntitulo: t\ndescricao: d\n---\n1. a\n", "tem de ser o do arquivo"),
            ("---\nnome: x\ntitulo: t\ndescricao: d\n---\n\n", "sem texto"),
        ],
    )
    def test_o_que_nao_esta_no_formato_falha_fechado(self, tmp_path, conteudo, trecho):
        with pytest.raises(ValueError, match=trecho):
            roteiros.ler_roteiro(_arquivo(tmp_path, "x", conteudo), "aluno")

    def test_nome_fora_do_padrao(self, tmp_path):
        with pytest.raises(ValueError, match="fora do padrão"):
            roteiros.ler_roteiro(_arquivo(tmp_path, "Com-Hifen", VALIDO.format(nome="Com-Hifen")), "aluno")

    def test_carregar_le_uma_pasta_por_escopo(self, tmp_path):
        for escopo in roteiros.ESCOPOS:
            (tmp_path / escopo).mkdir()
            _arquivo(tmp_path / escopo, f"de_{escopo}", VALIDO.format(nome=f"de_{escopo}"))
        carregados = roteiros.carregar(tmp_path)
        assert {e: list(r) for e, r in carregados.items()} == {
            "aluno": ["de_aluno"], "coordenacao": ["de_coordenacao"],
        }
        assert carregados["coordenacao"]["de_coordenacao"].escopo == "coordenacao"

    def test_pasta_de_escopo_vazia_falha_fechado(self, tmp_path):
        """Imagem sem os arquivos é imagem quebrada: melhor não subir."""
        (tmp_path / "aluno").mkdir()
        _arquivo(tmp_path / "aluno", "um", VALIDO.format(nome="um"))
        (tmp_path / "coordenacao").mkdir()
        with pytest.raises(ValueError, match="nenhum roteiro"):
            roteiros.carregar(tmp_path)
