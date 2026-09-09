import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { QRCodeSVG } from 'qrcode.react';

import {
  BOM_PROVEITO, codigoNaTela, horaLegivel, placaDaRetirada, ROTULO_DA_REFEICAO, rotuloDoDia,
  situacaoDoDia,
} from '../../dominio/cantina';
import type { RecusaDaLeitura } from '../../dominio/cantina';
import {
  chavesCantina, useCantinaDoAluno, useCodigoRotativo, useTelaAcesa, useTokenDeRetirada,
} from '../../hooks/cantina';
import { ErroApi } from '../../servicos/http';
import { useFotoPerfil } from '../../hooks/consultas';
import * as sessao from '../../servicos/sessao';

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
// ⚠️ **A renovação é silenciosa e não tem botão — enquanto ela funciona.** O
// token dura dois minutos (docs/40 §4) e `useTokenDeRetirada` o refaz antes de
// vencer, inclusive com a aba escondida. Não há "atualizar" ao lado de um código
// que está valendo, de propósito: seria a confissão de que ele pode estar velho,
// e a única pessoa capaz de perceber isso é a que está do outro lado do balcão.
//
// ⚠️ **Quando a renovação FALHA, a tela passa a oferecer uma saída** — e não é
// contradição, é a mesma regra: a essa altura a placa já admitiu que não tem
// código, então não há o que confessar. Esconder a única ação restante deixaria
// o aluno na frente da fila com uma tela que não faz nada. O botão também é a
// única coisa capaz de SUBSTITUIR uma tentativa pendurada (o `refetch` do React
// Query cancela a anterior, e `queryFn` repassa o `signal` para isso valer); o
// tique automático de 5 s, sozinho, só devolve a promessa que já estava presa.

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

  // Enquanto o código está à mostra, o aparelho não apaga. É o percurso da fila
  // inteiro — abrir o QR, guardar o celular, destravar no balcão — e sem isso
  // ele termina numa tela preta na frente de quem está lendo.
  useTelaAcesa(!!dia && !retirado);

  // A linha presencial acabou de nascer, e o resto do app ainda acha que este
  // dia está em aberto: o card em Hoje diria "Escolha seu almoço" ao lado de um
  // QR já gerado. Uma invalidação, na primeira resposta — as renovações
  // seguintes não mexem em nada que `/me/cantina` mostre.
  const nasceu = token.isSuccess;
  useEffect(() => {
    if (nasceu) qc.invalidateQueries({ queryKey: chavesCantina.doAluno });
  }, [nasceu, qc]);

  // O código morre pelo relógio, e nada na tela muda quando isso acontece: sem
  // este despertador o QR vencido ficaria na placa até a próxima resposta do
  // servidor — que é justamente o que pode estar demorando.
  const expiraEm = token.data?.expiraEm;
  const recebidoEm = token.dataUpdatedAt;
  const [, despertar] = useState(0);
  useEffect(() => {
    const prazo = codigoNaTela(expiraEm, recebidoEm).msAteVencer;
    if (prazo === null) return;
    const despertador = setTimeout(() => despertar((n) => n + 1), prazo);
    return () => clearTimeout(despertador);
  }, [expiraEm, recebidoEm]);

  // ⚠️ ANTES dos `return` antecipados abaixo, e não junto do resto do cálculo:
  // hook depois de um `return` condicional muda a ORDEM dos hooks entre
  // renders, que é o defeito que o React não consegue avisar direito — ele
  // aparece como estado trocando de dono. O Biome pegou; a tela não teria
  // pegado.
  const foto = useFotoPerfil({ tipo: 'aluno', proprio: true });
  const codigoRotativo = useCodigoRotativo(
    token.data
      ? {
        pedidoId: token.data.pedidoId,
        semente: token.data.semente,
        janela: token.data.janela,
        segundosDaJanela: token.data.segundosDaJanela,
      }
      : undefined,
  );

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
  const nome = sessao.nome() ?? '';
  // Recalculado a cada render, com o relógio de agora: o `despertar` acima é o
  // que garante que exista um render no instante em que a resposta muda.
  const codigo = codigoNaTela(expiraEm, recebidoEm);
  // Quem decide o que vai para a placa é o domínio, e a ordem das perguntas é a
  // regra — inclusive a que faltava aqui: um código que ainda vale vence a
  // falha da renovação SEGUINTE, porque o `query-core` preserva `data` no erro.
  const placa = placaDaRetirada({
    temCodigo: !!token.data,
    codigoVale: codigo.vale,
    falha: token.isError ? recusaDoToken(token.error) : null,
  });
  const esperando = placa.tipo === 'gerando' || placa.tipo === 'renovando';

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

      {/* NOME E FOTO acima do código (docs/40 §12.9.1).
          ⚠️ Não é enfeite: **o print resolve a cópia no tempo, a foto resolve a
          cópia no espaço.** Quem mostrar o celular de outro aparece com a cara
          de outro, e quem serve olha para a pessoa de qualquer jeito.
          É mais fraco que a foto na tela da CANTINA — o print carrega a foto
          junto, então só funciona se quem serve comparar. Estreita a fresta;
          quem a fecha continua sendo a fase 4 (§14.2). */}
      <div className="alu-retirada__quem">
        {foto.data?.fotoDataUrl ? (
          <img className="alu-retirada__foto" src={foto.data.fotoDataUrl} alt="" />
        ) : (
          // Sem foto cadastrada, as iniciais. Bloquear quem não tem foto é
          // decisão da fase 4, não desta.
          <span className="alu-retirada__iniciais" aria-hidden="true">{iniciais(nome)}</span>
        )}
        <span className="alu-retirada__nome">{nome}</span>
      </div>

      {(placa.tipo === 'codigo' || esperando) && (
        <div className="alu-retirada__placa">
          {placa.tipo === 'codigo' ? (
            <QRCodeSVG
              className="alu-retirada__qr"
              // ⚠️ O código ROTATIVO, e não o token (docs/40 §12.9.2). O token
              // continua existindo — é ele que prova ao servidor que esta linha
              // presencial é sua —, mas o que a câmera lê muda a cada 10 s, e
              // é por isso que um print mandado para o colega da fila não vale
              // nada. `?? token.data!.token` cobre o instante entre a resposta
              // chegar e o primeiro HMAC ficar pronto: melhor um QR válido de
              // 120 s por meio segundo do que um vão na tela com a fila
              // andando.
              value={codigoRotativo ?? token.data!.token}
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
            // ⚠️ A placa fica SEM código enquanto o token novo não chega.
            // Mostrar o vencido seria pior que não mostrar nada: o aluno o
            // apresenta, a leitura falha, e a frase que a cantina recebe manda
            // atualizar uma tela que não tem como ser atualizada à mão
            // (docs/40 §4). A placa mantém o tamanho para a fila não ver o
            // layout pular a cada renovação.
            <p className="alu-retirada__esperando" role="status">
              {placa.tipo === 'renovando' ? 'Renovando o código…' : 'Gerando o código…'}
            </p>
          )}
        </div>
      )}

      {/* Ou a legenda, ou a falha — nunca as duas. A legenda promete que não há
          nada para atualizar, e essa promessa só é verdade enquanto a renovação
          está de pé; ao lado de uma falha ela mandava o aluno apertar o que ela
          mesma dizia não existir. */}
      {placa.tipo === 'sem-resposta' || placa.tipo === 'recusado' ? (
        <p className="alu-cantina__erro" role="alert">{placa.mensagem}</p>
      ) : (
        <p className="alu-retirada__legenda">
          Mostre este código no balcão. Ele se renova sozinho — não há nada para atualizar.
        </p>
      )}

      {/* A saída, só onde ela muda alguma coisa: sem veredito do servidor,
          tentar de novo é a ação certa. Sobre uma recusa definitiva — "você já
          fez o pedido" — o mesmo botão só repetiria a mesma frase. */}
      {placa.tipo === 'sem-resposta' && (
        <button
          type="button"
          className="alu-tecla alu-tecla--fantasma"
          onClick={() => void token.refetch()}
          disabled={token.isFetching}
        >
          {token.isFetching ? 'Tentando…' : 'Tentar agora'}
        </button>
      )}

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

/**
 * O erro do React Query no par que o domínio lê: status e frase.
 *
 * É a MESMA conversão que o balcão faz antes de `lerRespostaDoQr`
 * (`telas/Cantina/AoVivo.tsx`), e pelo mesmo motivo: `status: 0` é a convenção de
 * `servicos/http.ts` para "não houve resposta HTTP nenhuma", e é ela que separa
 * "a rede não voltou" de "o servidor disse não".
 *
 * O que não é `ErroApi` também entra como `status: 0` — um `SyntaxError` de corpo
 * ilegível não é veredito sobre este aluno, e mostrar o texto do motor de JS na
 * fila não ajudaria ninguém.
 */
function recusaDoToken(erro: unknown): RecusaDaLeitura {
  if (erro instanceof ErroApi) return { status: erro.status, mensagem: erro.message };
  return { status: 0, mensagem: '' };
}


/** As duas primeiras iniciais do nome — o lugar da foto, quando não há foto. */
function iniciais(nome: string): string {
  const partes = nome.trim().split(/\s+/).filter(Boolean);
  if (!partes.length) return '?';
  const primeira = partes[0][0] ?? '';
  const ultima = partes.length > 1 ? (partes[partes.length - 1][0] ?? '') : '';
  return (primeira + ultima).toUpperCase();
}
