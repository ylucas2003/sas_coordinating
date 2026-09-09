"""O código do QR que muda a cada 10 segundos (docs/40 §12.9).

⚠️ O que estes testes protegem é uma propriedade, não um formato: **um print de
tela deixa de valer em 10 segundos**. O token de 120 s já resolvia o print
mandado no grupo depois do almoço; não resolvia o print mandado agora, para
quem está na fila ao lado.

E protegem o preço disso: o código tem de continuar valendo o tempo suficiente
para a câmera do balcão focar, num aparelho cujo relógio pode estar errado.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app import cantina_token as token

SEGREDO = "segredo-de-teste-com-mais-de-32-caracteres"
PEDIDO = "11111111-1111-1111-1111-111111111111"
OUTRO = "22222222-2222-2222-2222-222222222222"


@pytest.fixture(autouse=True)
def _config(monkeypatch):
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("JWT_SECRET_KEY", SEGREDO)
    yield
    get_settings.cache_clear()


def _qr(pedido: str, quando: datetime) -> str:
    janela = token.janela_de(quando)
    codigo = token.codigo_da_janela(token.semente_da_retirada(pedido), janela)
    return token.montar_qr(pedido, janela, codigo)


AGORA = datetime(2026, 9, 9, 12, 0, 0, tzinfo=UTC)


class TestAJanela:
    def test_o_codigo_da_janela_atual_passa(self):
        assert token.ler_qr_rotativo(_qr(PEDIDO, AGORA), agora=AGORA) == PEDIDO

    def test_o_codigo_da_janela_ANTERIOR_ainda_passa(self):
        """Não é folga, é requisito: entre o aluno mostrar e a câmera focar
        passam segundos, e um código que morre no instante exato transformaria
        a fila em repetição."""
        antes = AGORA - timedelta(seconds=token.SEGUNDOS_DA_JANELA)
        assert token.ler_qr_rotativo(_qr(PEDIDO, antes), agora=AGORA) == PEDIDO

    def test_o_codigo_de_DUAS_janelas_atras_nao_passa(self):
        """É esta linha que faz o print valer 10 s, e não para sempre."""
        velho = AGORA - timedelta(seconds=token.SEGUNDOS_DA_JANELA * 2)
        with pytest.raises(token.RetiradaIlegivel):
            token.ler_qr_rotativo(_qr(PEDIDO, velho), agora=AGORA)

    def test_o_codigo_do_FUTURO_nao_passa(self):
        """Aceitar a janela seguinte é onde este desenho costuma abrir a fresta
        que queria fechar — e não é preciso, porque o cliente conta o tempo
        decorrido a partir da janela que o servidor mandou."""
        futuro = AGORA + timedelta(seconds=token.SEGUNDOS_DA_JANELA)
        with pytest.raises(token.RetiradaIlegivel):
            token.ler_qr_rotativo(_qr(PEDIDO, futuro), agora=AGORA)

    def test_o_codigo_muda_de_uma_janela_para_a_outra(self):
        semente = token.semente_da_retirada(PEDIDO)
        j = token.janela_de(AGORA)
        assert token.codigo_da_janela(semente, j) != token.codigo_da_janela(semente, j + 1)


class TestASemente:
    def test_a_semente_de_um_pedido_nao_serve_para_outro(self):
        """Ela é presa ao pedido: quem tiver a própria semente não gera código
        para a refeição de outro aluno."""
        semente_alheia = token.semente_da_retirada(OUTRO)
        janela = token.janela_de(AGORA)
        forjado = token.montar_qr(
            PEDIDO, janela, token.codigo_da_janela(semente_alheia, janela),
        )
        with pytest.raises(token.RetiradaIlegivel):
            token.ler_qr_rotativo(forjado, agora=AGORA)

    def test_a_semente_NAO_aparece_no_conteudo_do_qr(self):
        """A propriedade que faz a rotação valer alguma coisa.

        Se a semente viajasse no QR, um print carregaria o material para derivar
        as janelas seguintes — e os 10 segundos seriam decoração.
        """
        conteudo = _qr(PEDIDO, AGORA)
        assert token.semente_da_retirada(PEDIDO) not in conteudo

    def test_a_semente_e_estavel_para_o_mesmo_pedido(self):
        """O servidor não guarda nada: ele recalcula quando o balcão lê."""
        assert token.semente_da_retirada(PEDIDO) == token.semente_da_retirada(PEDIDO)


class TestOQueNaoEntra:
    @pytest.mark.parametrize("ruim", ["", "sem-ponto", "a.b", "a.b.c.d", " . . "])
    def test_formato_errado_e_recusado_sem_explicar_qual(self, ruim):
        with pytest.raises(token.RetiradaIlegivel):
            token.ler_qr_rotativo(ruim, agora=AGORA)

    def test_janela_ilegivel_e_recusada(self):
        with pytest.raises(token.RetiradaIlegivel):
            token.ler_qr_rotativo(f"{PEDIDO}.abc.0123456789", agora=AGORA)

    def test_codigo_trocado_por_outro_do_mesmo_tamanho_nao_passa(self):
        janela = token.janela_de(AGORA)
        with pytest.raises(token.RetiradaIlegivel):
            token.ler_qr_rotativo(
                token.montar_qr(PEDIDO, janela, "0" * token.TAMANHO_DO_CODIGO), agora=AGORA,
            )
