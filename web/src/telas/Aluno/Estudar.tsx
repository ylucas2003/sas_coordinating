import { Link } from 'react-router-dom';

import { useMeusErros, useProgressoBanco } from '../../dados/aluno';
import { Icone } from './pecas/Icone';
import { TarjaFonte } from './pecas/TarjaFonte';
import { fmtInteiro } from './pecas/formato';

// ESTUDAR — três campos, e nada além deles.
//
// ⚠️ Substitui o desenho de duas metades ("Treinar agora" + "Todas as
// questões"), que por sua vez tinha substituído três abas. A razão da troca
// está no desenho de 02/09: as duas metades misturavam o que fazer AGORA com o
// acervo inteiro na mesma rolagem, e o acervo — que é a coisa grande — ficava
// abaixo da dobra atrás de três cartões que quase sempre diziam a mesma coisa.
//
//   BANCO         o material: 2.693 questões de prova do ITA e do IME
//   ESTATÍSTICAS  o mundo: o que mais cai em cada assunto, ano a ano
//   MEU PROGRESSO você: o que já marcou como feito, e de quanto
//
// A divisão é por PERGUNTA, não por tipo de dado, e é isso que faz cada card ter
// um destino óbvio. Note que Estatísticas fala só do mundo: nenhuma métrica de
// acerto do aluno entra ali. O eixo do aluno vive em Meu progresso, e ele diz
// "o que você marcou", nunca "o que você domina" — as duas coisas não são a
// mesma, e a tela é obrigada a separá-las.
//
// A missão do dia NÃO está aqui: ela é o herói da aba Hoje (docs/24 §7.1), e
// repeti-la aqui daria dois lugares para começar a mesma coisa.

export function Estudar() {
  const progresso = useProgressoBanco();
  const erros = useMeusErros();

  const total = progresso.data?.total;
  const feitas = progresso.data?.feitas;
  const quantosErros = erros.data?.length ?? 0;

  return (
    <>
      <h1 className="alu-titulo-tela">Estudar</h1>

      <div className="alu-campos">
        <Link className="alu-campo-cartao" to="/estudar/banco">
          <span className="alu-campo-cartao__texto">
            <span className="alu-olho">Material</span>
            <span className="alu-campo-cartao__titulo">Banco de questões</span>
            <span className="alu-campo-cartao__sub">
              {/* ⚠️ Sem número inventado enquanto a contagem não chega. "2.693"
                  fixo no código envelheceria calado na próxima importação. */}
              {total == null
                ? 'Provas do ITA e do IME, por assunto'
                : `${fmtInteiro(total)} questões de prova do ITA e do IME`}
            </span>
          </span>
          <IconeBanco />
        </Link>

        <Link className="alu-campo-cartao" to="/estudar/estatisticas">
          <span className="alu-campo-cartao__texto">
            <span className="alu-olho">Diagnóstico</span>
            <span className="alu-campo-cartao__titulo">Estatísticas</span>
            <span className="alu-campo-cartao__sub">
              O que mais cai em cada assunto, ano a ano
            </span>
          </span>
          <IconeEstatisticas />
        </Link>

        <Link className="alu-campo-cartao" to="/estudar/progresso">
          <span className="alu-campo-cartao__texto">
            <span className="alu-olho">Você</span>
            <span className="alu-campo-cartao__titulo">Meu progresso</span>
            <span className="alu-campo-cartao__sub">
              {/* Três estados, e nenhum deles chuta: sem resposta ainda, sem
                  marcação nenhuma, ou o par (feitas, total). */}
              {progresso.isError
                ? 'Não deu para contar agora'
                : total == null || feitas == null
                  ? 'O que você já resolveu do banco'
                  : feitas === 0
                    ? 'Comece a marcar o que você já resolveu'
                    : `${fmtInteiro(feitas)} de ${fmtInteiro(total)} questões marcadas`}
            </span>
          </span>
          <IconeProgresso />
        </Link>
      </div>

      {/* O elo quieto: mantém `/treino/erros` alcançável sem virar um quarto
          campo. Some quando não há erro nenhum — um atalho para uma lista vazia
          é convite para uma tela vazia. E some também no ERRO da consulta: "0
          erros" para quem tem 34 é a mentira mais cara desta aba. */}
      {!erros.isError && quantosErros > 0 && (
        <Link className="alu-est-elo-quieto" to="/treino/erros">
          {/* A contagem ainda é mock: `meusErros` é agregação de
              `/me/simulado/{id}/questoes`, que existe por simulado e não somada
              (registro.ts). A tarja é obrigatória enquanto for — número falso
              sem marca é a superfície mockada virando invisível. */}
          <TarjaFonte chave="meusErros" ponto />
          Revisar os {quantosErros} erros dos seus simulados
          <Icone nome="avancar" tamanho={15} />
        </Link>
      )}
    </>
  );
}

// Os três desenhos. Decorativos (`aria-hidden`): quem nomeia o destino é o
// texto do cartão, e um `alt` aqui seria a terceira vez que o leitor de tela
// ouve "banco de questões".

function IconeBanco() {
  return (
    <svg
      className="alu-campo-cartao__icone"
      viewBox="0 0 70 70"
      fill="none"
      stroke="var(--alu-dado)"
      strokeWidth="1.4"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M22 12h20l8 8v34a2 2 0 0 1-2 2H22a2 2 0 0 1-2-2V14a2 2 0 0 1 2-2z" />
      <path d="M42 12v8h8" />
      <path d="M28 30h16M28 37h16M28 44h10" strokeLinecap="round" />
      <path d="M16 18v38a4 4 0 0 0 4 4h26" opacity=".5" />
    </svg>
  );
}

function IconeEstatisticas() {
  return (
    <svg
      className="alu-campo-cartao__icone"
      viewBox="0 0 70 70"
      fill="none"
      stroke="var(--alu-dado)"
      strokeWidth="1.4"
      aria-hidden="true"
    >
      <rect x="16" y="38" width="10" height="18" />
      <rect x="30" y="26" width="10" height="30" />
      <rect x="44" y="14" width="10" height="42" />
      <path d="M12 60h48" strokeLinecap="round" opacity=".5" />
    </svg>
  );
}

function IconeProgresso() {
  return (
    <svg
      className="alu-campo-cartao__icone"
      viewBox="0 0 70 70"
      fill="none"
      stroke="var(--alu-dado)"
      strokeWidth="1.4"
      aria-hidden="true"
    >
      <rect x="14" y="16" width="12" height="12" rx="2" fill="var(--alu-dado)" stroke="none" />
      <rect x="30" y="16" width="12" height="12" rx="2" />
      <rect x="46" y="16" width="12" height="12" rx="2" />
      <rect
        x="14"
        y="30"
        width="12"
        height="12"
        rx="2"
        fill="var(--alu-dado)"
        stroke="none"
        opacity=".55"
      />
      <rect x="30" y="30" width="12" height="12" rx="2" />
      <rect x="46" y="30" width="12" height="12" rx="2" />
      <rect x="14" y="44" width="12" height="12" rx="2" />
      <rect x="30" y="44" width="12" height="12" rx="2" />
      <rect x="46" y="44" width="12" height="12" rx="2" />
    </svg>
  );
}
