import { useEffect } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { QRCodeSVG } from 'qrcode.react';

import { BOM_PROVEITO, horaLegivel, ROTULO_DA_REFEICAO, rotuloDoDia, situacaoDoDia } from '../../dominio/cantina';
import { chavesCantina, useCantinaDoAluno, useTokenDeRetirada } from '../../hooks/cantina';

// A TELA DO CÓDIGO — `/cantina/retirada/:cardapioId` (docs/40 §6).
//
// É a única tela do produto que existe para ser lida por uma CÂMERA, e o
// desenho sai daí: o QR ocupa a tela, o resto é legenda.
//
// ⚠️ **O QR não segue o tema.** Ele é sempre escuro sobre branco, dentro de uma
// placa branca própria, mesmo no tema noite. Um código invertido é lido por
// alguns leitores e por outros não — e quem descobre isso é o aluno, na fila,
// sem ter o que fazer a respeito.
//
// ⚠️ **A renovação é silenciosa e não tem botão.** O token dura dois minutos
// (docs/40 §4) e `useTokenDeRetirada` o refaz antes de vencer. Não há
// "atualizar" na tela de propósito: um botão ali seria a confissão de que o
// código pode estar velho, e a única pessoa capaz de perceber isso é a que
// está do outro lado do balcão.

export function RetiradaDoAluno() {
  const { cardapioId = '' } = useParams<{ cardapioId: string }>();
  const qc = useQueryClient();
  const { data, isPending } = useCantinaDoAluno();

  const dia = data?.dias.find((d) => d.id === cardapioId);
  const retirado = !!dia?.retiradoEm;

  // O POST que gera o token é o mesmo que CRIA a linha presencial. Ele só sai
  // depois de o dia chegar — sem isso, um id de cardápio colado na URL viraria
  // uma linha no banco antes de a tela saber se aquele dia sequer existe.
  const token = useTokenDeRetirada(cardapioId, !!dia && !retirado);

  // A linha presencial acabou de nascer, e o resto do app ainda acha que este
  // dia está em aberto: o card em Hoje diria "Escolha seu almoço" ao lado de um
  // QR já gerado. Uma invalidação, na primeira resposta — as renovações
  // seguintes não mexem em nada que `/me/cantina` mostre.
  const nasceu = token.isSuccess;
  useEffect(() => {
    if (nasceu) qc.invalidateQueries({ queryKey: chavesCantina.doAluno });
  }, [nasceu, qc]);

  if (isPending) return <p className="alu-vazio">Carregando…</p>;

  if (!dia) {
    return (
      <div className="alu-retirada">
        <Voltar />
        <p className="alu-vazio">Não encontrei esta refeição. Ela pode ter saído do cardápio.</p>
      </div>
    );
  }

  const refeicao = ROTULO_DA_REFEICAO[dia.refeicao];
  const situacao = situacaoDoDia(dia);

  // O desfecho, e ele chega pelo caminho normal: o stream avisa que mudou, o
  // `GET /me/cantina` traz `retiradoEm`, e a tela decide o texto (docs/40 §5).
  // Sem XP, sem confete e sem cor de alerta — mesma régua do resto da área do
  // aluno (docs/38 §4).
  if (retirado) {
    return (
      <div className="alu-retirada">
        <Voltar />
        <p className="alu-retirada__proveito">{BOM_PROVEITO[dia.refeicao]}</p>
        <p className="alu-retirada__legenda">
          {refeicao} de {rotuloDoDia(dia.data)} · retirado às {horaLegivel(dia.retiradoEm)}
        </p>
      </div>
    );
  }

  return (
    <div className="alu-retirada">
      <Voltar />

      <h1 className="alu-retirada__titulo">
        {refeicao} · {rotuloDoDia(dia.data)}
      </h1>

      {token.isError && (
        // A recusa vem por extenso porque ela EXPLICA uma regra do produto:
        // "você já fez o pedido", "este cardápio não aceita retirada". Trocá-la
        // por "não foi possível" apagaria a única informação útil.
        <p className="alu-cantina__erro" role="alert">{mensagemDaRecusa(token.error)}</p>
      )}

      {!token.isError && (
        <div className="alu-retirada__placa">
          {token.data ? (
            <QRCodeSVG
              className="alu-retirada__qr"
              value={token.data.token}
              size={320}
              // Correção baixa e margem de 2 módulos: numa tela de celular não
              // há sujeira nem amassado para corrigir, e menos correção dá
              // módulos MAIORES — que é o que a câmera do balcão precisa.
              level="L"
              marginSize={2}
              bgColor="#ffffff"
              fgColor="#111111"
              title={`Código de retirada do ${refeicao.toLowerCase()}`}
            />
          ) : (
            <p className="alu-retirada__esperando">Gerando o código…</p>
          )}
        </div>
      )}

      <p className="alu-retirada__legenda">
        Mostre este código no balcão. Ele se renova sozinho enquanto esta tela estiver aberta.
      </p>

      {/* O elo discreto do docs/40 §6 — e ele some quando pedir já não é
          caminho (prazo vencido, ou este cardápio não aceita pedido). */}
      {situacao.podePedir && (
        <Link className="alu-retirada__elo" to="/cantina">Prefiro fazer o pedido</Link>
      )}
    </div>
  );
}

function Voltar() {
  return (
    <Link className="alu-retirada__voltar" to="/cantina">‹ Cantina</Link>
  );
}

/** A frase do servidor passa inteira; só o `GET /x → 422` cru vira texto de
    gente, porque esse não foi escrito para ninguém ler. */
function mensagemDaRecusa(erro: unknown): string {
  if (erro instanceof Error && erro.message && !/→ \d{3}$/.test(erro.message)) return erro.message;
  return 'Não consegui gerar o código agora. Tente de novo em instantes.';
}
