import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

import { Campo, Dialogo, Linha2 } from '../../componentes/dialogos/Dialogo';
import { CabecaDeCampo } from '../../componentes/ui/Campo';
import { BarraFiltros, Busca, Pills } from '../../componentes/ui/filtros/BarraFiltros';
import { resumirSelecao, resumirTexto } from '../../dominio/filtros';
import { Kpi } from '../../componentes/ui/Kpi';
import { useAcessosDeAlunos, useCoordenadores } from '../../hooks/consultas';
import {
  useAlterarPapelCoordenador, useCriarCoordenador, useEditarCoordenador,
  useRedefinirSenhaCoordenador,
} from '../../hooks/mutacoes';
import * as sessao from '../../servicos/sessao';
import type { AcessoAluno, PapelCoordenacao, UsuarioCoordenacao } from '../../tipos/dominio';
import { normalizar } from '../../util/formato';

// Painel de administrador (docs/18 §4.6, docs/35 §11): quem pode entrar.
//
// Duas metades, e desde 04/09 elas têm PERMISSÕES DIFERENTES — é por isso que
// a divisão aparece na tela e não só no backend:
//
//   * em cima, as contas da coordenação. Ver é de qualquer coordenador; criar,
//     renomear, desativar, redefinir senha e trocar o papel é só do
//     administrador, e o que ele não pode nem aparece — botão que existe para
//     dar 403 ensina a pessoa a desconfiar da tela;
//   * embaixo, os alunos. Trabalho diário de coordenação, e continua de todo
//     mundo — "quando o aluno faz isso, aparece na tela de gerenciamento do
//     coordenador" (21/08, 19h15).
//
// ⚠️ A coluna "Canvas" das contas saiu. Ela dizia se a conta entrava pelo SSO,
// e a coordenação não entra mais por lá (docs/35 §11.6). O dado continua no
// banco; só deixou de significar alguma coisa aqui.
//
// ⚠️ A pergunta da metade de baixo mudou junto. Era "quem já criou senha"; sem
// senha de aluno, esse número congelou em 04/09. O que decide hoje é ter conta
// ligada ao Canvas — quem não tem, não entra, e é essa a lista que a
// coordenação precisa enxergar.

function fmtQuando(iso: string | null | undefined): string {
  if (!iso) return 'nunca';
  return new Date(iso).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
}

type FiltroAcesso = 'com' | 'sem';

export function Contas() {
  const { data: coordenadores = [] } = useCoordenadores();
  const { data: acessos } = useAcessosDeAlunos();
  // Lido uma vez: o papel vem do login e não muda no meio da sessão.
  const souAdministrador = sessao.ehAdministrador();
  const [filtros, setFiltros] = useState<ReadonlySet<string>>(new Set());
  const [busca, setBusca] = useState('');
  const [criando, setCriando] = useState(false);
  // A senha sorteada aparece UMA vez, aqui, e nunca mais — é o contrato da
  // rota. Fica até o coordenador fechar, para ele copiar com calma.
  const [senhaRevelada, setSenhaRevelada] = useState<{ email: string; senha: string } | null>(null);

  const alunos = useMemo(() => {
    const lista = acessos?.alunos ?? [];
    const q = normalizar(busca.trim());
    return lista.filter((a) => {
      if (filtros.has('com') && !a.temCanvas) return false;
      if (filtros.has('sem') && a.temCanvas) return false;
      if (q && !normalizar(a.nome).includes(q) && !(a.matricula ?? '').includes(q)) return false;
      return true;
    });
  }, [acessos, filtros, busca]);

  function alternar(v: string) {
    setFiltros((s) => {
      const novo = new Set(s);
      // 'com' e 'sem' são excludentes.
      if (novo.has(v)) novo.delete(v);
      else { novo.clear(); novo.add(v); }
      return novo;
    });
  }

  return (
    <div className="tela">
      <CabecaDeCampo titulo="Quem tem acesso" para="/administracao" destino="Administração" />

      <div className="tela-cabecalho">
        <div>
          <p className="tela-subtitulo">Quem pode entrar no painel. Contas não são apagadas: desativar preserva a autoria na auditoria.</p>
          {/*
            O modelo está certo; o produto é que não contava (docs/25 §3). As
            quatro dúvidas do áudio de 29/08 têm resposta no código e nenhuma
            estava escrita em lugar visível — e se o autor do produto não sabe,
            o coordenador também não vai saber.

            A frase que resume a regra está em `auth_canvas.py`: "o Canvas diz
            QUEM é; o SAS decide quem ENTRA".
          */}
          <p className="tela-subtitulo admin__explicacao">
            <b>Criar um acesso aqui não cria nada no Canvas</b>, e o contrário também não vale:
            <b> ser admin no Canvas não dá acesso ao SAS</b>. A conta existe só aqui e entra só
            por e-mail e senha — a coordenação não usa o botão do Canvas, que é o caminho do
            aluno.
          </p>
          {!souAdministrador && (
            <p className="tela-subtitulo admin__explicacao">
              Você vê as contas, mas criar, renomear, desativar, redefinir senha e mudar o
              papel de alguém é do administrador do SAS. Procure-o para qualquer uma dessas.
            </p>
          )}
        </div>
        {souAdministrador && (
          <button className="btn btn-primary" onClick={() => setCriando(true)}>Nova conta</button>
        )}
      </div>

      <section className="card">
        <table className="data-table">
          <thead>
            <tr>
              <th>Nome</th><th>E-mail</th><th>Papel</th><th>Último login</th><th>Situação</th>
              {souAdministrador && <th />}
            </tr>
          </thead>
          <tbody>
            {coordenadores.map((u) => (
              <LinhaCoordenador
                key={u.id}
                usuario={u}
                souAdministrador={souAdministrador}
                onSenha={(senha) => setSenhaRevelada({ email: u.email, senha })}
              />
            ))}
          </tbody>
        </table>
      </section>

      <div className="tela-cabecalho">
        <div>
          <h2 className="section__title">Acesso dos alunos</h2>
          <p className="tela-subtitulo">
            O aluno entra com a conta do Canvas, e só com ela. Quem não tem conta ligada ao
            Canvas não consegue entrar — e é no Canvas, não aqui, que isso se resolve.
          </p>
        </div>
      </div>

      {acessos && (
        <div className="kpi-grid kpi-grid--cartoes">
          <Kpi rotulo="Alunos ativos" valor={acessos.total} />
          <Kpi rotulo="Conseguem entrar" valor={acessos.comCanvas} sufixo={` de ${acessos.total}`} tone="tone-verde" />
          <Kpi rotulo="Sem conta no Canvas" valor={acessos.total - acessos.comCanvas} tone={acessos.total - acessos.comCanvas > 0 ? 'tone-ambar' : ''} />
        </div>
      )}

      <BarraFiltros
        tela="administracao"
        algumAtivo={filtros.size > 0 || busca.trim() !== ''}
        onLimpar={() => { setFiltros(new Set()); setBusca(''); }}
        grupos={[
          {
            chave: 'acesso', rotulo: 'Acesso',
            resumo: resumirSelecao(
              filtros,
              [
                { valor: 'com', label: 'conseguem entrar' },
                { valor: 'sem', label: 'sem conta no Canvas' },
              ],
              'situação', 'situações',
            ),
            corpo: (
              <Pills
                opcoes={[
                  { valor: 'com' satisfies FiltroAcesso, label: 'Conseguem entrar' },
                  { valor: 'sem' satisfies FiltroAcesso, label: 'Sem Canvas' },
                ]}
                selecionados={filtros}
                onToggle={alternar}
              />
            ),
          },
          {
            chave: 'busca', rotulo: 'Buscar',
            resumo: resumirTexto(busca),
            corpo: (
              <Busca
                valor={busca}
                onChange={setBusca}
                placeholder="Nome ou matrícula…"
                rotulo="Buscar aluno por nome ou matrícula"
              />
            ),
          },
        ]}
      />

      <section className="card">
        <table className="data-table">
          <thead>
            <tr><th>Aluno</th><th>Matrícula</th><th>E-mail</th><th>Entra pelo Canvas</th><th>Último login</th></tr>
          </thead>
          <tbody>
            {alunos.slice(0, 300).map((a) => <LinhaAluno key={a.id} aluno={a} />)}
          </tbody>
        </table>
        {alunos.length > 300 && (
          <p className="section__subtitle" style={{ padding: '12px 16px' }}>
            {`Mostrando 300 de ${alunos.length}. Use a busca ou os filtros.`}
          </p>
        )}
      </section>

      {criando && (
        <NovaConta
          onFechar={(resultado) => {
            setCriando(false);
            if (resultado) setSenhaRevelada(resultado);
          }}
        />
      )}

      {senhaRevelada && (
        <Dialogo
          titulo="Senha gerada"
          subtitulo={senhaRevelada.email}
          onFechar={() => setSenhaRevelada(null)}
          rodape={<button className="btn btn--primary" onClick={() => setSenhaRevelada(null)}>Já anotei</button>}
        >
          <p className="section__subtitle">
            Esta é a única vez que ela aparece. Entregue ao titular pelo canal do colégio — depois
            disto ninguém consegue lê-la de volta, só redefinir.
          </p>
          <p className="section__subtitle">
            Ela vale <b>só no SAS</b>: não é a senha do Canvas, e redefinir aqui não mexe em nada
            lá. É também o único jeito de a coordenação entrar — o botão do Canvas é do aluno.
          </p>
          <code className="agendar__preview-nome" style={{ fontSize: 18, userSelect: 'all' }}>{senhaRevelada.senha}</code>
        </Dialogo>
      )}
    </div>
  );
}

function LinhaCoordenador({
  usuario: u, souAdministrador, onSenha,
}: {
  usuario: UsuarioCoordenacao;
  souAdministrador: boolean;
  onSenha: (senha: string) => void;
}) {
  const editar = useEditarCoordenador();
  const redefinir = useRedefinirSenhaCoordenador();
  const alterarPapel = useAlterarPapelCoordenador();
  // O servidor é quem recusa mexer na própria conta (422); isto aqui é só
  // para não oferecer um botão que nunca funciona.
  const souEu = u.nome === sessao.nome();
  const ehAdministrador = u.papel === 'administrador';

  async function alternarAtivo() {
    const acao = u.ativo ? 'Desativar' : 'Reativar';
    if (!window.confirm(`${acao} a conta de ${u.nome}?`)) return;
    await editar.mutateAsync({ id: u.id, corpo: { ativo: !u.ativo } });
  }

  async function renomear() {
    const nome = window.prompt('Novo nome:', u.nome);
    if (!nome || nome.trim() === u.nome) return;
    await editar.mutateAsync({ id: u.id, corpo: { nome: nome.trim() } });
  }

  async function trocarPapel() {
    const destino: PapelCoordenacao = ehAdministrador ? 'coordenador' : 'administrador';
    // O texto diz o que a pessoa GANHA ou PERDE, não o nome do papel: quem
    // clica precisa saber que está entregando (ou tirando) o poder de criar
    // login e de alterar nota — inclusive sobre a própria conta de quem clica.
    const pergunta = ehAdministrador
      ? `Rebaixar ${u.nome} a coordenador?\n\nEle perde na hora — sem esperar a sessão dele acabar — o poder de criar, renomear e desativar contas, redefinir senha, mudar papel e alterar nota pelo painel. Continua entrando no SAS como coordenador.`
      : `Tornar ${u.nome} administrador do SAS?\n\nPassa a criar, renomear e desativar contas de coordenação, redefinir senha, mudar o papel de outras contas — a sua inclusive — e alterar nota pelo painel.`;
    if (!window.confirm(pergunta)) return;
    await alterarPapel.mutateAsync({ id: u.id, papel: destino });
  }

  async function novaSenha() {
    if (!window.confirm(`Redefinir a senha de ${u.nome}? A atual deixa de valer na hora.`)) return;
    const r = await redefinir.mutateAsync(u.id);
    onSenha(r.senha_nova);
  }

  return (
    <tr className={u.ativo ? '' : 'is-inativo'}>
      <td>{u.nome}{souEu && <span className="sim-selo-ok" style={{ marginLeft: 8 }}>você</span>}</td>
      <td>{u.email}</td>
      <td>
        {ehAdministrador
          ? <span className="sim-selo-ok" title="Cria logins e altera nota pelo painel.">administrador</span>
          : <span className="sim-selo-canvas">coordenador</span>}
      </td>
      <td>{fmtQuando(u.ultimo_login_em)}</td>
      <td>{u.ativo ? <span className="sim-selo-ok">ativa</span> : <span className="sim-selo-canvas">desativada</span>}</td>
      {/* Nada de botão desabilitado para quem não é administrador: a coluna
          inteira some, e o cabeçalho junto. Botão cinza convida a clicar e
          ensina a pessoa a esperar recusa da tela. */}
      {souAdministrador && (
        <td>
          <button className="btn-editar" onClick={renomear}>Renomear</button>
          <button className="btn-editar" onClick={novaSenha}>Nova senha</button>
          {/* As duas ações que mexem em PODER ficam juntas, e nenhuma delas
              vale para a própria conta: o último administrador se rebaixando
              (ou se desativando) deixaria a casa sem quem cria login — nem
              para desfazer, porque desfazer também é dele. */}
          {!souEu && (
            <>
              <button
                className="btn-editar"
                onClick={trocarPapel}
                title={ehAdministrador
                  ? 'Tira o poder de criar login e de alterar nota.'
                  : 'Dá o poder de criar login e de alterar nota.'}
              >
                {ehAdministrador ? 'Rebaixar' : 'Promover'}
              </button>
              <button className="btn-editar" onClick={alternarAtivo}>{u.ativo ? 'Desativar' : 'Reativar'}</button>
            </>
          )}
        </td>
      )}
    </tr>
  );
}

function LinhaAluno({ aluno: a }: { aluno: AcessoAluno }) {
  return (
    <tr>
      <td><Link to={`/alunos/${a.id}`}>{a.nome}</Link></td>
      <td>{a.matricula || '—'}</td>
      <td>{a.email || <span className="sim-selo-canvas">sem e-mail</span>}</td>
      <td>{a.temCanvas ? <span className="sim-selo-ok">sim</span> : <span className="sim-selo-divergente">sem conta no Canvas</span>}</td>
      <td>{fmtQuando(a.ultimoLoginEm)}</td>
    </tr>
  );
}

function NovaConta({ onFechar }: { onFechar: (r: { email: string; senha: string } | null) => void }) {
  const criar = useCriarCoordenador();
  const [email, setEmail] = useState('');
  const [nome, setNome] = useState('');
  const [erro, setErro] = useState('');

  async function salvar() {
    setErro('');
    try {
      const r = await criar.mutateAsync({ email: email.trim(), nome: nome.trim() });
      onFechar({ email: r.email, senha: r.senha_inicial });
    } catch (e) {
      setErro((e as Error).message || 'Falha ao criar.');
    }
  }

  return (
    <Dialogo
      titulo="Nova conta da coordenação"
      subtitulo="A senha inicial é sorteada e mostrada uma vez"
      onFechar={() => onFechar(null)}
      rodape={
        <>
          <button className="btn btn--ghost" onClick={() => onFechar(null)}>Cancelar</button>
          <button className="btn btn--primary" disabled={criar.isPending || !email || !nome} onClick={salvar}>
            {criar.isPending ? 'Criando…' : 'Criar'}
          </button>
        </>
      }
    >
      <Linha2>
        <Campo label="Nome">
          {/* biome-ignore lint/a11y/noAutofocus: é o primeiro campo de um
              diálogo modal, onde levar o foco para dentro é o comportamento
              correto — a regra existe para autofocus em página inteira. */}
          <input className="dialog__input" value={nome} onChange={(e) => setNome(e.target.value)} autoFocus />
        </Campo>
        <Campo label="E-mail">
          <input className="dialog__input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </Campo>
      </Linha2>
      <p className="agendar__ajuda">
        A conta nasce <b>coordenadora</b> e entra por e-mail e senha. Se ela precisar criar
        logins e alterar nota pelo painel, promova depois pelo botão <b>Promover</b> na linha
        dela — em dois passos de propósito, para ninguém virar administrador por distração ao
        preencher um cadastro.
      </p>
      {erro && <div className="agendar__erro">{erro}</div>}
    </Dialogo>
  );
}
