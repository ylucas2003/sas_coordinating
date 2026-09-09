"""A senha que o administrador escolhe (docs/40 §12.7).

⚠️ O pedido original era **ver** as senhas da cantina. Isso não é possível e
não vai passar a ser: o hash é PBKDF2 de mão única, e guardar texto legível
exporia contas que alcançam nome, turma e restrição alimentar de menores. O que
resolve a mesma necessidade é DEFINIR — quem define, sabe.

Estes testes existem para trancar o outro lado disso: a validação é do
SERVIDOR. Um campo de formulário com as mesmas regras é conveniência; quem
manda `curl` não passa por ele, e a conta que ele cria vale por oito horas de
token sem segundo fator.
"""

import pytest
from fastapi import HTTPException

from app import senha_definida

EMAIL = "cantina@aridesa.com.br"


def _recusa(senha: str) -> str:
    with pytest.raises(HTTPException) as erro:
        senha_definida.validar(senha, email=EMAIL)
    assert erro.value.status_code == 422
    return erro.value.detail


class TestOPiso:
    def test_curta_demais_e_recusada(self):
        detalhe = _recusa("Abc123!")
        assert str(senha_definida.MINIMO_DE_CARACTERES) in detalhe

    def test_o_minimo_exato_passa(self):
        senha = "Chuvisco#42x"
        assert len(senha) == senha_definida.MINIMO_DE_CARACTERES
        assert senha_definida.validar(senha, email=EMAIL) == senha

    def test_a_mensagem_diz_QUAL_regra_falhou(self):
        """Recusa genérica faz a pessoa tentar às cegas — e a quarta tentativa
        às cegas costuma ser pior que a primeira."""
        assert "caracteres" in _recusa("curta")
        assert "adivinhar" in _recusa("123456789012")
        assert "e-mail" in _recusa("cantina-do-ari-2026")


class TestOQueNaoPassa:
    def test_a_senha_nao_pode_conter_o_local_do_email(self):
        """`cantina` em `cantina@aridesa.com.br` é a primeira coisa que se
        tenta, e é o que vem à cabeça de quem cadastra com o e-mail na tela."""
        _recusa("cantinaSegura9")

    def test_acento_e_caixa_nao_disfarcam(self):
        """`Cantina@2026` e `cantina2026` são a mesma ideia para quem ataca."""
        _recusa("CANTÍNA-forte-1")

    def test_poucos_caracteres_distintos_e_recusado(self):
        _recusa("aaaaaaaaaaaaaa")

    def test_espaco_em_volta_nao_cria_comprimento(self):
        """`'   abc   '` tem 9 caracteres e serve para nada."""
        _recusa("   abc123   ")


class TestOSorteio:
    def test_sem_senha_sorteia(self):
        """O contrato antigo continua de pé: cliente que não manda o campo
        recebe uma senha gerada, como sempre recebeu."""
        assert len(senha_definida.resolver(None, email=EMAIL)) >= 12
        assert len(senha_definida.resolver("   ", email=EMAIL)) >= 12

    def test_duas_sorteadas_nunca_sao_iguais(self):
        assert senha_definida.sortear() != senha_definida.sortear()

    def test_a_sorteada_passa_pela_propria_regua(self):
        """Se um dia o piso subir acima do que o sorteio produz, a rota de
        criar conta passaria a recusar a senha que ela mesma gerou."""
        for _ in range(20):
            gerada = senha_definida.sortear()
            assert senha_definida.validar(gerada, email=EMAIL) == gerada
