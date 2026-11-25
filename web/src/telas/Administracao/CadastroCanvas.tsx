import { type ReactNode, useId, useState } from 'react';
import { Navigate } from 'react-router-dom';

import '../../../styles/cadastro-canvas.css';
import { Dialogo } from '../../componentes/dialogos/Dialogo';
import { CabecaDeCampo } from '../../componentes/ui/Campo';
import { Esqueleto } from '../../componentes/ui/Esqueleto';
import {
  DOMINIOS_DE_EMAIL, MODELO_DA_PLANILHA, OUTRO_DOMINIO, contagemDoLote, frasesDaPrevia,
  matriculaCompleta, montarEmail, ordenarParaRevisao, plural, podeEnviar,
  resumoDoCadastro, rotuloDoEstadoDoCurso, rotuloDoLote, soDigitos, totalDeMatriculas,
} from '../../dominio/cadastroCanvas';
import {
  useCadastrarAluno, useEnviarLote, useLotesRecentes, usePacotesDoCanvas, usePreviaDoLote,
  useSituacaoDoLote,
} from '../../hooks/cadastroCanvas';
import { baixarBlob } from '../../servicos/baixar';
import { ErroApi } from '../../servicos/http';
import * as sessao from '../../servicos/sessao';
import type {
  CadastroDeAluno, CatalogoDePacotes, LinhaDaPrevia, LoteNoCanvas, PreviaDoLote,
  ResultadoDoCadastro,
} from '../../tipos/cadastroCanvas';

// CADASTRAR ALUNOS NO CANVAS (docs/46) — só do administrador.
//
// Duas portas para a mesma coisa: criar a conta do aluno no Canvas do colégio
// e matriculá-lo nos cursos da série. Um por vez, com resposta curso a curso,
// ou por planilha, que vira um SIS Import — o mesmo que o administrador do
// Canvas já sobe à mão.
//
// O que a tela precisa dizer, porque ninguém deduz:
//
//   * A SENHA NÃO PASSA POR AQUI. O Canvas manda ao aluno o e-mail de terminar
//     o cadastro, e é ali que ele a cria (decisão de 25/11/2026). Por isso o
//     e-mail é obrigatório para conta nova.
//   * Conta que já existe NÃO É ALTERADA: só ganha as matrículas que faltam. É
//     o caso da virada de ano, o aluno do 2º que vai para o 3º.
//   * O aluno não aparece no SAS na hora: quem o traz é o sync de 5 minutos,
//     como todo aluno.
//
// ⚠️ O guard é desta tela, e não do casco, como em `TrocaDeTelas.tsx`; o
// servidor recusa o resto com 403 de qualquer jeito. Os hooks moram em
// `TelaDoCadastro` para o `return` antecipado não quebrar a regra dos hooks.

export function CadastroCanvas() {
  if (!sessao.ehAdministrador()) return <Navigate to="/administracao" replace />;
  return <TelaDoCadastro />;
}

function fmtQuando(iso: string | null | undefined): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('pt-BR', {
    day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
  });
}

/**
 * Campo com rótulo DE VERDADE, nas classes do diálogo. O `Campo` de
 * `Dialogo.tsx` desenha o rótulo como `<span>`, e o leitor de tela anuncia o
 * campo sem nome; aqui o `<label for>` liga os dois, e a ajuda entra como
 * descrição do campo.
 */
function CampoRotulado({
  rotulo, ajuda, children,
}: {
  rotulo: string;
  ajuda?: ReactNode;
  children: (atributos: { id: string; 'aria-describedby'?: string }) => ReactNode;
}) {
  const id = useId();
  const idDaAjuda = `${id}-ajuda`;
  return (
    <div className="dialog__campo">
      <label className="dialog__label" htmlFor={id}>{rotulo}</label>
      {children({ id, 'aria-describedby': ajuda ? idDaAjuda : undefined })}
      {ajuda && <span className="agendar__ajuda" id={idDaAjuda}>{ajuda}</span>}
    </div>
  );
}

function TelaDoCadastro() {
  // `null` = o ano que o servidor escolhe (o mais novo com curso no Canvas).
  const [ano, setAno] = useState<number | null>(null);
  const pacotes = usePacotesDoCanvas(ano);
  const catalogo = pacotes.data;

  return (
    <div className="tela cadcanvas">
      <CabecaDeCampo titulo="Cadastrar alunos no Canvas" para="/administracao" destino="Administração" />

      <div className="tela-cabecalho">
        <div>
          <p className="tela-subtitulo admin__explicacao">
            Cria a conta do aluno no Canvas do colégio e o matricula nos cursos da série. O
            login é a matrícula. <b>A senha o aluno cria pelo e-mail que o Canvas manda</b> — ela
            nunca passa pelo SAS.
          </p>
          <p className="tela-subtitulo admin__explicacao">
            Conta que já existe não é alterada (nem nome, nem e-mail, nem senha): só ganha as
            matrículas que faltam. O aluno aparece no SAS na próxima sincronização, em até 5
            minutos.
          </p>
        </div>
        {catalogo && catalogo.anos.length > 1 && (
          <label className="dialog__campo cadcanvas__ano">
            <span className="dialog__label">Ano letivo</span>
            <select
              aria-label="Ano letivo"
              className="dialog__input"
              value={catalogo.ano}
              onChange={(e) => setAno(Number(e.target.value))}
            >
              {catalogo.anos.map((a) => <option key={a} value={a}>{a}</option>)}
            </select>
          </label>
        )}
      </div>

      {pacotes.isLoading && <Esqueleto />}
      {pacotes.isError && (
        <section className="card cadcanvas__falha-de-leitura" role="alert">
          <p>
            Não consegui ler os cursos no Canvas agora: {(pacotes.error as Error).message}
          </p>
          <button type="button" className="btn btn--ghost" onClick={() => pacotes.refetch()}>Tentar de novo</button>
        </section>
      )}

      {catalogo && (
        <>
          {/* `key` pelo ano: trocar o ano muda os cursos, e um formulário ou
              uma prévia do ano anterior não podem sobreviver à troca. */}
          <UmAluno key={`um-${catalogo.ano}`} catalogo={catalogo} />
          <EmLote key={`lote-${catalogo.ano}`} catalogo={catalogo} />
        </>
      )}

      <LotesRecentes />
    </div>
  );
}

// ─── Um aluno ─────────────────────────────────────────────────────────────

// `email` é o que está no campo — em geral só o começo do endereço —, e
// `dominio` é o do botão ao lado. O endereço inteiro sai de `montarEmail`.
const VAZIO = {
  matricula: '', nome: '', email: '', dominio: DOMINIOS_DE_EMAIL[0] as string, serie: '', sede: '',
};

function UmAluno({ catalogo }: { catalogo: CatalogoDePacotes }) {
  const cadastrar = useCadastrarAluno();
  const [campos, setCampos] = useState(VAZIO);
  const [erro, setErro] = useState('');
  // O 409 da rota é "esta matrícula já é de outra pessoa no Canvas". Guarda a
  // frase do servidor, que traz o nome que está lá.
  const [confirmacao, setConfirmacao] = useState<string | null>(null);
  const [confirmado, setConfirmado] = useState(false);
  const [resultado, setResultado] = useState<ResultadoDoCadastro | null>(null);

  const pacote = catalogo.pacotes.find((p) => String(p.serie) === campos.serie) ?? null;
  const pronto =
    matriculaCompleta(campos.matricula) && campos.nome.trim() !== '' && pacote != null
    && (!pacote.exige_sede || campos.sede !== '');

  const email = montarEmail(campos.email, campos.dominio);
  // Com "@" no campo, o endereço é o digitado e o botão não manda mais nada.
  const emailDigitadoInteiro = campos.email.includes('@');

  function mudar(campo: keyof typeof VAZIO, valor: string) {
    setCampos((c) => ({ ...c, [campo]: valor, ...(campo === 'serie' ? { sede: '' } : {}) }));
    // Mudou o que foi digitado: a confirmação e o resultado eram de outro aluno.
    setConfirmacao(null);
    setConfirmado(false);
    setResultado(null);
    setErro('');
  }

  async function enviar(confirmarNome: boolean) {
    if (!pacote) return;
    setErro('');
    setConfirmacao(null);
    const corpo: CadastroDeAluno = {
      matricula: campos.matricula,
      nome: campos.nome.trim(),
      email: email || null,
      serie: pacote.serie,
      sede_id: pacote.exige_sede ? campos.sede : null,
      ano: catalogo.ano,
      confirmar_nome_existente: confirmarNome,
    };
    try {
      setResultado(await cadastrar.mutateAsync(corpo));
      setConfirmado(confirmarNome);
    } catch (e) {
      if (e instanceof ErroApi && e.status === 409) {
        setConfirmacao(e.message);
      } else {
        setErro((e as Error).message || 'Falha ao cadastrar.');
      }
    }
  }

  function outro() {
    setCampos(VAZIO);
    setResultado(null);
    setConfirmado(false);
  }

  return (
    <section className="card cadcanvas__bloco" aria-labelledby="cadcanvas-um">
      <h2 className="section__title" id="cadcanvas-um">Um aluno</h2>

      <form
        className="cadcanvas__form"
        onSubmit={(e) => {
          e.preventDefault();
          if (pronto && !cadastrar.isPending) enviar(confirmado);
        }}
      >
        <CampoRotulado rotulo="Matrícula" ajuda="8 dígitos — é também o login no Canvas">
          {(a) => (
            <input
              {...a}
              className="dialog__input"
              inputMode="numeric"
              autoComplete="off"
              value={campos.matricula}
              onChange={(e) => mudar('matricula', soDigitos(e.target.value))}
            />
          )}
        </CampoRotulado>
        <CampoRotulado rotulo="Nome completo">
          {(a) => (
            <input
              {...a}
              className="dialog__input"
              autoComplete="off"
              value={campos.nome}
              onChange={(e) => mudar('nome', e.target.value)}
            />
          )}
        </CampoRotulado>
        <CampoRotulado
          rotulo="E-mail do aluno"
          ajuda={
            // O endereço inteiro, por extenso: um erro aqui é o aluno que nunca
            // recebe o e-mail de criar a senha.
            email
              ? <>O convite do Canvas vai para <b>{email}</b>. Obrigatório se ele ainda não tem conta.</>
              : 'Obrigatório se ele ainda não tem conta: é por ele que cria a senha'
          }
        >
          {(a) => (
            <div className="cadcanvas__email">
              {/* `text`, e não `email`: o campo costuma ter só o começo do
                  endereço, e o navegador barraria o envio do formulário por
                  falta de "@". O `inputMode` mantém o teclado de e-mail. */}
              <input
                {...a}
                className="dialog__input"
                type="text"
                inputMode="email"
                autoComplete="off"
                autoCapitalize="none"
                autoCorrect="off"
                spellCheck={false}
                placeholder={
                  campos.dominio === OUTRO_DOMINIO || emailDigitadoInteiro ? 'nome@dominio.com' : 'nome.sobrenome'
                }
                value={campos.email}
                onChange={(e) => mudar('email', e.target.value)}
              />
              <select
                className="dialog__input cadcanvas__dominio"
                aria-label="Domínio do e-mail"
                title={emailDigitadoInteiro ? 'O endereço digitado já tem @: o domínio é o dele' : undefined}
                disabled={emailDigitadoInteiro}
                value={emailDigitadoInteiro ? OUTRO_DOMINIO : campos.dominio}
                onChange={(e) => mudar('dominio', e.target.value)}
              >
                {DOMINIOS_DE_EMAIL.map((dominio) => (
                  <option key={dominio} value={dominio}>@{dominio}</option>
                ))}
                <option value={OUTRO_DOMINIO}>outro domínio</option>
              </select>
            </div>
          )}
        </CampoRotulado>
        <CampoRotulado rotulo={`Série em ${catalogo.ano}`}>
          {(a) => (
            <select
              {...a}
              className="dialog__input"
              value={campos.serie}
              onChange={(e) => mudar('serie', e.target.value)}
            >
              <option value="">Escolha…</option>
              {catalogo.pacotes.map((p) => <option key={p.serie} value={p.serie}>{p.rotulo}</option>)}
            </select>
          )}
        </CampoRotulado>
        {pacote?.exige_sede && (
          <CampoRotulado rotulo="Sede" ajuda={`A turma no curso ${pacote.curso_de_provas ?? 'de provas'}`}>
            {(a) => (
              <select
                {...a}
                className="dialog__input"
                value={campos.sede}
                onChange={(e) => mudar('sede', e.target.value)}
              >
                <option value="">Escolha…</option>
                {pacote.sedes.map((s) => <option key={s.id} value={s.id}>{s.nome}</option>)}
              </select>
            )}
          </CampoRotulado>
        )}

        {pacote && (
          <details className="cadcanvas__pacote">
            <summary>
              Vai matricular {pacote.cursos.length === 1 ? 'no curso' : `nos ${pacote.cursos.length} cursos`} do {pacote.rotulo} de {catalogo.ano}
            </summary>
            <ul>{pacote.cursos.map((c) => <li key={c.id}>{c.nome}</li>)}</ul>
          </details>
        )}

        <div className="cadcanvas__acoes">
          <button type="submit" className="btn btn--primary" disabled={!pronto || cadastrar.isPending}>
            {cadastrar.isPending ? 'Cadastrando no Canvas…' : 'Cadastrar no Canvas'}
          </button>
        </div>
      </form>

      {erro && <p className="cadcanvas__falha" role="alert">{erro}</p>}

      {confirmacao && (
        <div className="cadcanvas__aviso" role="alert">
          <p>{confirmacao}</p>
          <div className="cadcanvas__acoes">
            {/* A ação SEGURA é a de destaque. Confirmar matricula em 19
                cursos uma conta que já é de alguém — se a matrícula estiver
                errada, de outro aluno. */}
            <button type="button" className="btn btn--primary" onClick={() => setConfirmacao(null)}>
              Corrigir a matrícula
            </button>
            <button
              type="button"
              className="btn btn--ghost"
              disabled={cadastrar.isPending}
              onClick={() => enviar(true)}
            >
              É a mesma pessoa — matricular
            </button>
          </div>
        </div>
      )}

      {resultado && (
        <ResultadoDeUm
          resultado={resultado}
          repetindo={cadastrar.isPending}
          onRepetir={() => enviar(confirmado)}
          onOutro={outro}
        />
      )}
    </section>
  );
}

function ResultadoDeUm({
  resultado: r, repetindo, onRepetir, onOutro,
}: {
  resultado: ResultadoDoCadastro;
  repetindo: boolean;
  onRepetir: () => void;
  onOutro: () => void;
}) {
  return (
    <div className="cadcanvas__resultado" aria-live="polite">
      <p className="cadcanvas__resultado-titulo">
        <b>{r.nome}</b> ({r.matricula}) · {resumoDoCadastro(r)}
      </p>
      {r.email_enviado && (
        <p className="agendar__ajuda">
          O Canvas mandou o e-mail para o aluno terminar o cadastro e criar a senha.
        </p>
      )}
      {r.conta === 'existente' && r.nome_no_canvas && r.nome_no_canvas !== r.nome && (
        <p className="agendar__ajuda">No Canvas, a conta continua com o nome “{r.nome_no_canvas}”.</p>
      )}
      <ul className="cadcanvas__cursos">
        {r.cursos.map((c) => (
          <li key={c.id} className={c.estado === 'falhou' ? 'cadcanvas__falha' : undefined}>
            <span>{c.nome}</span>
            <span className="tag">{rotuloDoEstadoDoCurso(c.estado)}</span>
            {c.detalhe && <span className="cadcanvas__detalhe">{c.detalhe}</span>}
          </li>
        ))}
      </ul>
      <div className="cadcanvas__acoes">
        {!r.completo && r.cursos.some((c) => c.estado === 'falhou') && (
          <button type="button" className="btn btn--primary" disabled={repetindo} onClick={onRepetir}>
            {repetindo ? 'Tentando…' : 'Tentar de novo os que falharam'}
          </button>
        )}
        <button type="button" className="btn btn--ghost" onClick={onOutro}>Cadastrar outro aluno</button>
      </div>
    </div>
  );
}

// ─── Em lote ──────────────────────────────────────────────────────────────

function EmLote({ catalogo }: { catalogo: CatalogoDePacotes }) {
  const previa = usePreviaDoLote();
  const enviar = useEnviarLote();
  const [arquivo, setArquivo] = useState<string | null>(null);
  const [confirmando, setConfirmando] = useState(false);
  const [loteEnviado, setLoteEnviado] = useState<LoteNoCanvas | null>(null);
  const [erroDoEnvio, setErroDoEnvio] = useState('');

  const dados: PreviaDoLote | undefined = previa.data;
  const semSisId = catalogo.pacotes.filter((p) => p.problemas_no_lote.length > 0);

  function escolher(ev: React.ChangeEvent<HTMLInputElement>) {
    const escolhido = ev.target.files?.[0];
    // Limpa o campo: escolher o MESMO arquivo de novo (corrigido no Excel)
    // precisa disparar outra prévia, e o `change` não dispara sem isso.
    ev.target.value = '';
    if (!escolhido) return;
    setArquivo(escolhido.name);
    setLoteEnviado(null);
    setErroDoEnvio('');
    previa.mutate({ arquivo: escolhido, ano: catalogo.ano });
  }

  async function confirmarEnvio() {
    if (!dados) return;
    setErroDoEnvio('');
    try {
      const lote = await enviar.mutateAsync({ ano: dados.ano, linhas: dados.linhas });
      setLoteEnviado(lote);
      previa.reset();
      setArquivo(null);
    } catch (e) {
      setErroDoEnvio((e as Error).message || 'Falha ao enviar.');
    } finally {
      setConfirmando(false);
    }
  }

  const validas = dados ? dados.resumo.novas + dados.resumo.existentes : 0;
  const matriculas = dados ? totalDeMatriculas(dados.linhas, catalogo.pacotes) : 0;

  return (
    <section className="card cadcanvas__bloco" aria-labelledby="cadcanvas-lote">
      <h2 className="section__title" id="cadcanvas-lote">Em lote, por planilha</h2>
      <p className="tela-subtitulo admin__explicacao">
        Uma linha por aluno, com as colunas <code>matricula</code>, <code>nome</code>,{' '}
        <code>email</code>, <code>serie</code> e <code>sede</code> (a sede só no 3º ano, com o
        nome como está no Canvas). Aceita .xlsx e .csv. Nada é enviado antes de você ver a
        prévia e confirmar.
      </p>
      {semSisId.map((p) => (
        <p key={p.serie} className="cadcanvas__falha">
          O {p.rotulo} não entra no lote: {p.problemas_no_lote.join('; ')}. Cadastre esses alunos
          um por vez.
        </p>
      ))}

      <div className="cadcanvas__acoes">
        <label className={`btn btn--primary${previa.isPending ? ' cadcanvas__desligado' : ''}`}>
          {previa.isPending ? 'Conferindo no Canvas…' : 'Escolher planilha'}
          <input
            type="file"
            accept=".xlsx,.xlsm,.csv,text/csv"
            className="cadcanvas__arquivo"
            disabled={previa.isPending}
            onChange={escolher}
          />
        </label>
        <button
          type="button"
          className="btn btn--ghost"
          onClick={() => baixarBlob(
            new Blob([`﻿${MODELO_DA_PLANILHA}`], { type: 'text/csv;charset=utf-8' }),
            'modelo-cadastro-canvas.csv',
          )}
        >
          Baixar modelo
        </button>
        {arquivo && <span className="agendar__ajuda">{arquivo}</span>}
      </div>

      {previa.isError && (
        <p className="cadcanvas__falha" role="alert">{(previa.error as Error).message}</p>
      )}

      {dados && (
        <PreviaDaPlanilha
          previa={dados}
          matriculas={matriculas}
          enviando={enviar.isPending}
          onEnviar={() => setConfirmando(true)}
        />
      )}

      {erroDoEnvio && <p className="cadcanvas__falha" role="alert">{erroDoEnvio}</p>}

      {loteEnviado && <AcompanhamentoDoLote inicial={loteEnviado} />}

      {confirmando && dados && (
        <Dialogo
          titulo={`Enviar ${validas} ${validas === 1 ? 'aluno' : 'alunos'} ao Canvas`}
          subtitulo={`Ano letivo ${dados.ano}`}
          onFechar={() => setConfirmando(false)}
          rodape={(
            <>
              <button type="button" className="btn btn--ghost" onClick={() => setConfirmando(false)}>
                Cancelar
              </button>
              <button
                type="button"
                className="btn btn--primary"
                disabled={enviar.isPending}
                onClick={confirmarEnvio}
              >
                {enviar.isPending ? 'Enviando…' : 'Enviar ao Canvas'}
              </button>
            </>
          )}
        >
          <p>
            Isto cria <b>{plural(dados.resumo.novas, 'conta nova', 'contas novas')}</b> e
            pede <b>{plural(matriculas, 'matrícula', 'matrículas')}</b> no Canvas do colégio.
          </p>
          <p className="agendar__ajuda">
            {dados.resumo.novas > 0 && 'Cada conta nova recebe do Canvas o e-mail para criar a senha. '}
            {dados.resumo.existentes > 0 && (
              `${dados.resumo.existentes === 1 ? 'A conta que já existe não é alterada' : `As ${dados.resumo.existentes} contas que já existem não são alteradas`}: só ganha as matrículas que faltam. `
            )}
            {dados.resumo.com_aviso > 0 && `${plural(dados.resumo.com_aviso, 'linha tem', 'linhas têm')} aviso na prévia: confira antes.`}
          </p>
        </Dialogo>
      )}
    </section>
  );
}

function PreviaDaPlanilha({
  previa, matriculas, enviando, onEnviar,
}: {
  previa: PreviaDoLote;
  matriculas: number;
  enviando: boolean;
  onEnviar: () => void;
}) {
  const { resumo } = previa;
  const linhas = ordenarParaRevisao(previa.linhas);
  const frases = frasesDaPrevia(resumo, matriculas);
  return (
    <div className="cadcanvas__previa">
      <p className="cadcanvas__resultado-titulo">
        {frases.base}
        {frases.erro && <span className="cadcanvas__falha"> · {frases.erro}</span>}
        {frases.aviso && ` · ${frases.aviso}`}
      </p>
      {resumo.com_erro > 0 && (
        <p className="agendar__ajuda">
          Corrija as linhas com erro na planilha e escolha o arquivo de novo. O envio só fica
          disponível com a planilha inteira certa.
        </p>
      )}

      <div className="cadcanvas__tabela">
        <table className="data-table data-table--cartoes">
          <thead>
            <tr>
              <th>Linha</th><th>Matrícula</th><th>Nome</th><th>Série</th><th>Sede</th>
              <th>Situação</th><th>Observação</th>
            </tr>
          </thead>
          <tbody>
            {linhas.map((l) => <LinhaDaTabela key={`${l.linha}-${l.matricula}`} linha={l} />)}
          </tbody>
        </table>
      </div>

      <div className="cadcanvas__acoes">
        <button
          type="button"
          className="btn btn--primary"
          disabled={!podeEnviar(previa) || enviando}
          onClick={onEnviar}
        >
          Enviar ao Canvas…
        </button>
      </div>
    </div>
  );
}

const SITUACAO: Record<LinhaDaPrevia['situacao'], string> = {
  nova: 'conta nova',
  existente: 'já tem conta',
  erro: 'erro',
};

function LinhaDaTabela({ linha: l }: { linha: LinhaDaPrevia }) {
  const observacoes = [...l.erros, ...l.avisos];
  return (
    <tr>
      {/* No celular esta célula vira o TÍTULO do cartão, e um "4" sozinho não
          diz que é o número da linha na planilha. */}
      <td data-rotulo="Linha" data-titulo><span className="cadcanvas__so-celular">Linha </span>{l.linha}</td>
      <td data-rotulo="Matrícula">{l.matricula || '—'}</td>
      <td data-rotulo="Nome">{l.nome || '—'}</td>
      <td data-rotulo="Série">{l.serie ? `${l.serie}º` : '—'}</td>
      <td data-rotulo="Sede">{l.sede_nome ?? '—'}</td>
      <td data-rotulo="Situação">
        <span className={l.situacao === 'erro' ? 'tag cadcanvas__falha' : 'tag'}>{SITUACAO[l.situacao]}</span>
      </td>
      <td data-rotulo="Observação" className={l.erros.length ? 'cadcanvas__falha' : undefined}>
        {observacoes.length ? observacoes.join(' · ') : '—'}
      </td>
    </tr>
  );
}

function ListaDeMensagens({ titulo, mensagens, total }: { titulo: string; mensagens: string[]; total: number }) {
  if (!total) return null;
  return (
    <details className="cadcanvas__mensagens">
      <summary>{titulo} ({total})</summary>
      <ul>
        {mensagens.map((m, i) => (
          // biome-ignore lint/suspicious/noArrayIndexKey: a lista vem pronta do Canvas, não muda de ordem e pode repetir o mesmo texto — o índice é a chave certa aqui.
          <li key={i}>{m}</li>
        ))}
      </ul>
      {total > mensagens.length && (
        <p className="agendar__ajuda">Mostrando {mensagens.length} de {total}. O resto está no Canvas, em SIS Import.</p>
      )}
    </details>
  );
}

function AcompanhamentoDoLote({ inicial }: { inicial: LoteNoCanvas }) {
  const { data } = useSituacaoDoLote(inicial.id);
  const lote = data ?? inicial;
  return (
    <div className="cadcanvas__resultado" aria-live="polite">
      <p className="cadcanvas__resultado-titulo">
        Lote {lote.id} enviado · <b>{rotuloDoLote(lote)}</b>
        {contagemDoLote(lote) && ` · ${contagemDoLote(lote)}`}
      </p>
      {lote.estado === 'processando' && (
        <p className="agendar__ajuda">
          O Canvas processa o lote em segundo plano. Esta tela acompanha sozinha; pode sair dela
          que o lote continua.
        </p>
      )}
      <ListaDeMensagens titulo="Erros" mensagens={lote.erros} total={lote.total_erros} />
      <ListaDeMensagens titulo="Avisos" mensagens={lote.avisos} total={lote.total_avisos} />
    </div>
  );
}

// ─── O que já foi enviado ─────────────────────────────────────────────────

function LotesRecentes() {
  const { data: lotes, isLoading, isError } = useLotesRecentes();
  // Falha de leitura aqui é do Canvas, e a tela de cima já diz isso quando é
  // o caso: não repetir o mesmo alarme duas vezes.
  if (isLoading || isError || !lotes || lotes.length === 0) return null;
  return (
    <section className="card cadcanvas__bloco" aria-labelledby="cadcanvas-recentes">
      <h2 className="section__title" id="cadcanvas-recentes">Lotes enviados pelo SAS</h2>
      <p className="tela-subtitulo">
        Os dez mais recentes. Os lotes que alguém sobe direto pela tela do Canvas não aparecem
        aqui.
      </p>
      <table className="data-table data-table--cartoes">
        <thead>
          <tr><th>Enviado em</th><th>Situação</th><th>O que o Canvas contou</th><th /></tr>
        </thead>
        <tbody>
          {lotes.map((l) => (
            <tr key={l.id}>
              <td data-rotulo="Enviado em" data-titulo>{fmtQuando(l.criado_em)}</td>
              <td data-rotulo="Situação" className={l.estado === 'falhou' ? 'cadcanvas__falha' : undefined}>
                {rotuloDoLote(l)}
              </td>
              <td data-rotulo="Contagem">{contagemDoLote(l) || '—'}</td>
              <td data-rotulo="Detalhes">
                <ListaDeMensagens titulo="Erros" mensagens={l.erros} total={l.total_erros} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
