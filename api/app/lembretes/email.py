"""Envio de e-mail via AWS SES — o único canal até a P5.

Sem retry próprio: quem re-tenta é a máquina de estados do disparo
(despachante), não o cliente HTTP. Sem config, `enviar_email` levanta
EmailNaoConfigurado — nunca silêncio: lembrete que não chega sem ninguém
saber é o pior resultado possível deste módulo.

P3 acrescentou três coisas, todas por causa do volume (docs/13 §4.5):
  - EMAIL_DESTINATARIO_TESTE, a rede que impede 873 e-mails reais saírem de
    um curl de teste;
  - o configuration set, que é o que faz bounce/complaint chegarem no SNS;
  - Reply-To no coordenador — aluno responde o lembrete, e a resposta não
    pode cair na caixa pessoal de quem programou.
"""

from __future__ import annotations

from ..config import get_settings


class EmailNaoConfigurado(Exception):
    """SES sem credencial ou remetente no .env — quem chama decide o que fazer."""


def email_configurado() -> bool:
    s = get_settings()
    return bool(
        s.aws_ses_access_key_id and s.aws_ses_secret_access_key and s.email_remetente
    )


def aplicar_destinatario_teste(
    destinatario: str, assunto: str
) -> tuple[str, str]:
    """Redireciona o envio quando EMAIL_DESTINATARIO_TESTE está preenchido.

    O destinatário real vira prefixo do assunto — sem isso, um teste com 873
    alunos vira 873 e-mails idênticos na mesma caixa, sem saber de quem eram.
    Função pura: é o que os testes cobrem.
    """
    teste = get_settings().email_destinatario_teste.strip()
    if not teste or teste.lower() == destinatario.strip().lower():
        return destinatario, assunto
    return teste, f"[para: {destinatario}] {assunto}"


def enviar_email(*, destinatario: str, assunto: str, corpo: str) -> None:
    """Um e-mail, texto puro, via SES."""
    if not email_configurado():
        raise EmailNaoConfigurado(
            "SES não configurado — defina AWS_SES_ACCESS_KEY_ID, "
            "AWS_SES_SECRET_ACCESS_KEY e EMAIL_REMETENTE no .env"
        )
    # Import tardio: boto3 só é necessário quando há envio de verdade — a API
    # sobe (e o resto do sistema funciona) mesmo sem ele instalado.
    import boto3

    s = get_settings()
    destinatario, assunto = aplicar_destinatario_teste(destinatario, assunto)

    cliente = boto3.client(
        "ses",
        region_name=s.aws_ses_regiao,
        aws_access_key_id=s.aws_ses_access_key_id,
        aws_secret_access_key=s.aws_ses_secret_access_key,
    )
    extra: dict[str, object] = {}
    if s.email_configuration_set:
        extra["ConfigurationSetName"] = s.email_configuration_set
    if s.coordenador_email:
        extra["ReplyToAddresses"] = [s.coordenador_email]

    cliente.send_email(
        Source=s.email_remetente,
        Destination={"ToAddresses": [destinatario]},
        Message={
            "Subject": {"Data": assunto, "Charset": "UTF-8"},
            "Body": {"Text": {"Data": corpo, "Charset": "UTF-8"}},
        },
        **extra,
    )
