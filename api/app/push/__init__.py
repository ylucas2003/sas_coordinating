"""Notificação push no aparelho — Web Push padrão, sem SDK de fornecedor (docs/45).

A capacidade, e só ela: guardar a inscrição que o navegador gera, cifrar uma
notificação para ela e entregá-la ao serviço de push do fabricante. NENHUM evento
do SAS manda push ainda; quem decidir mandar chama `envio.enviar_para_dono` com
uma `Notificacao`, e o contrato que cada evento preenche está no docs/45 §9.

Por que não Firebase, OneSignal ou o `pywebpush`:
  - SDK de push na página é exatamente o que o docs/20 §6 proíbe (dados de menor,
    armadilha 7 do CLAUDE.md). Aqui a página só usa a API do navegador.
  - O protocolo cabe em três primitivas que o `cryptography` — já no projeto, via
    `python-jose` — tem prontas: ECDH P-256, HKDF-SHA256 e AES-128-GCM. A
    composição segue a RFC 8291 e é conferida, byte a byte, contra o vetor de
    teste do Apêndice A dela (tests/test_push.py). Nenhuma dependência nova.

Os módulos:
  - `chaves`     — a chave VAPID do servidor (uma variável de ambiente só).
  - `cifra`      — o corpo cifrado `aes128gcm` (RFC 8188 + RFC 8291).
  - `vapid`      — o cabeçalho `Authorization: vapid …` (RFC 8292).
  - `endpoints`  — a lista FECHADA de hosts para onde o servidor aceita fazer POST.
  - `envio`      — `Notificacao`, a leitura das respostas e a manutenção da tabela.
"""
