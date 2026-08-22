import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

import { Campo, Dialogo, Linha2 } from '../../componentes/dialogos/Dialogo';
import { Sidebar } from '../../componentes/layout/Sidebar';
import { CorpoChips, PainelFiltros } from '../../componentes/ui/filtros/PainelFiltros';
import { Kpi } from '../../componentes/ui/Kpi';
import { useAcessosDeAlunos, useCoordenadores } from '../../hooks/consultas';
import {
  useCriarCoordenador, useEditarCoordenador, useLigarCoordenadorAoCanvas, useRedefinirSenhaCoordenador,
} from '../../hooks/mutacoes';
import * as sessao from '../../servicos/sessao';
import type { AcessoAluno, UsuarioCoordenacao } from '../../tipos/dominio';
import { normalizar } from '../../util/formato';

// Painel de administrador (docs/18 §4.6): quem pode entrar.
//
// Duas metades. Em cima, as contas da coordenação — criar, renomear,
// desativar, redefinir senha; nunca apagar, porque a conta é autora na
// trilha de auditoria. Embaixo, os alunos: quem já fez primeiro acesso, quem
// nunca entrou — "quando o aluno faz isso, aparece na tela de gerenciamento
// do coordenador" (21/08, 19h15).

function fmtQuando(iso: string | null | undefined): string {
  if (!iso) return 'nunca';
  return new Date(iso).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
}

type FiltroAcesso = 'com' | 'sem';

export function Administracao() {
  const { data: coordenadores = [] } = useCoordenadores();
  const { data: acessos } = useAcessosDeAlunos();
  const [filtros, setFiltros] = useState<ReadonlySet<string>>(new Set());
  const [abertas, setAbertas] = useState<ReadonlySet<string>>(new Set(['acesso']));
  const [busca, setBusca] = useState('');
  const [criando, setCriando] = useState(false);
  // A senha sorteada aparece UMA vez, aqui, e nunca mais — é o contrato da
  // rota. Fica até o coordenador fechar, para ele copiar com calma.
  const [senhaRevelada, setSenhaRevelada] = useState<{ email: string; senha: string } | null>(null);

  const alunos = useMemo(() => {
    const lista = acessos?.alunos ?? [];
    const q = normalizar(busca.trim());
    return lista.filter((a) => {
      if (filtros.has('com') && !a.primeiroAcessoFeito) return false;
      if (filtros.has('sem') && a.primeiroAcessoFeito) return false;
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
    <>
      <Sidebar rotulo="Filtros">
        <PainelFiltros
          abertas={abertas}
          onToggleSecao={(chave) => setAbertas((a) => {
            const novo = new Set(a);
            if (novo.has(chave)) novo.delete(chave);
            else novo.add(chave);
            return novo;
          })}
          algumAtivo={filtros.size > 0}
          onLimpar={() => setFiltros(new Set())}
          secoes={[
            {
              chave: 'acesso', rotulo: 'Primeiro acesso', icone: 'turmas',
              corpo: (
                <CorpoChips
                  opcoes={[
                    { valor: 'com' satisfies FiltroAcesso, label: 'Já fez' },
                    { valor: 'sem' satisfies FiltroAcesso, label: 'Nunca entrou' },
                  ]}
                  selecionados={filtros}
                  onToggle={alternar}
                />
              ),
            },
          ]}
        />
      </Sidebar>

      <main className="app-main">
        <section className="card">
          <div className="screen-header">
            <div>
              <div className="screen-breadcrumb">Administração</div>
              <h1 className="screen-title">Contas da coordenação</h1>
              <p className="screen-subtitle">Quem pode entrar no painel. Contas não são apagadas: desativar preserva a autoria na auditoria.</p>
            </div>
            <button className="btn btn--primary" onClick={() => setCriando(true)}>Nova conta</button>
          </div>

          <table className="data-table">
            <thead>
              <tr>
                <th>Nome</th><th>E-mail</th><th>Canvas</th><th>Último login</th><th>Situação</th><th />
              </tr>
            </thead>
            <tbody>
              {coordenadores.map((u) => (
                <LinhaCoordenador key={u.id} usuario={u} onSenha={(senha) => setSenhaRevelada({ email: u.email, senha })} />
              ))}
            </tbody>
          </table>
        </section>

        <section className="card" style={{ marginTop: 16 }}>
          <div className="screen-header">
            <div>
              <h2 className="screen-title">Acesso dos alunos</h2>
              <p className="screen-subtitle">Quem já criou a senha e quem nunca entrou. Para liberar de novo, use a ficha do aluno.</p>
            </div>
            <input
              className="painel-busca"
              placeholder="Buscar por nome ou matrícula…"
              value={busca}
              onChange={(e) => setBusca(e.target.value)}
            />
          </div>

          {acessos && (
            <div className="painel-kpis">
              <Kpi rotulo="Alunos ativos" valor={acessos.total} />
              <Kpi rotulo="Já fizeram primeiro acesso" valor={acessos.comAcesso} sufixo={` de ${acessos.total}`} tone="tone-verde" />
              <Kpi rotulo="Nunca entraram" valor={acessos.total - acessos.comAcesso} tone={acessos.total - acessos.comAcesso > 0 ? 'tone-ambar' : ''} />
            </div>
          )}

          <table className="data-table">
            <thead>
              <tr><th>Aluno</th><th>Matrícula</th><th>E-mail</th><th>Primeiro acesso</th><th>Último login</th></tr>
            </thead>
            <tbody>
              {alunos.slice(0, 300).map((a) => <LinhaAluno key={a.id} aluno={a} />)}
            </tbody>
          </table>
          {alunos.length > 300 && (
            <p className="section__subtitle">{`Mostrando 300 de ${alunos.length}. Use a busca ou os filtros.`}</p>
          )}
        </section>
      </main>

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
            Esta é a única vez que ela aparece. Entregue ao titular pelo canal do colégio — depois disto ninguém consegue lê-la de volta, só redefinir.
          </p>
          <code className="agendar__preview-nome" style={{ fontSize: 18, userSelect: 'all' }}>{senhaRevelada.senha}</code>
        </Dialogo>
      )}
    </>
  );
}

function LinhaCoordenador({ usuario: u, onSenha }: { usuario: UsuarioCoordenacao; onSenha: (senha: string) => void }) {
  const editar = useEditarCoordenador();
  const redefinir = useRedefinirSenhaCoordenador();
  const ligar = useLigarCoordenadorAoCanvas();
  const souEu = u.nome === sessao.nome();
  const [erroCanvas, setErroCanvas] = useState('');

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

  // O SAS procura o id do Canvas pelo e-mail da conta — a pessoa não digita
  // número nenhum. Se o e-mail não existir lá, o erro diz isso.
  async function ligarCanvas() {
    setErroCanvas('');
    try {
      await ligar.mutateAsync(u.id);
    } catch (e) {
      setErroCanvas((e as Error).message || 'Não achei no Canvas.');
    }
  }

  async function desligarCanvas() {
    if (!window.confirm(`Desligar o login pelo Canvas de ${u.nome}? A conta volta a entrar só por senha.`)) return;
    await editar.mutateAsync({ id: u.id, corpo: { canvas_user_id: '' } });
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
        {u.canvas_user_id
          ? <span className="sim-selo-ok" title={`id no Canvas: ${u.canvas_user_id}`}>entra pelo Canvas</span>
          : <span className="sim-selo-canvas" title="Liga sozinho no primeiro login pelo Canvas, se o e-mail for o mesmo.">só senha</span>}
        {erroCanvas && <div className="agendar__erro" style={{ marginTop: 4 }}>{erroCanvas}</div>}
      </td>
      <td>{fmtQuando(u.ultimo_login_em)}</td>
      <td>{u.ativo ? <span className="sim-selo-ok">ativa</span> : <span className="sim-selo-canvas">desativada</span>}</td>
      <td>
        <button className="btn-editar" onClick={renomear}>Renomear</button>
        {u.canvas_user_id
          ? <button className="btn-editar" onClick={desligarCanvas}>Desligar Canvas</button>
          : <button className="btn-editar" disabled={ligar.isPending} onClick={ligarCanvas}>{ligar.isPending ? 'Procurando…' : 'Ligar ao Canvas'}</button>}
        <button className="btn-editar" onClick={novaSenha}>Nova senha</button>
        {!souEu && (
          <button className="btn-editar" onClick={alternarAtivo}>{u.ativo ? 'Desativar' : 'Reativar'}</button>
        )}
      </td>
    </tr>
  );
}

function LinhaAluno({ aluno: a }: { aluno: AcessoAluno }) {
  return (
    <tr>
      <td><Link to={`/alunos/${a.id}`}>{a.nome}</Link></td>
      <td>{a.matricula || '—'}</td>
      <td>{a.email || <span className="sim-selo-canvas">sem e-mail</span>}</td>
      <td>{a.primeiroAcessoFeito ? <span className="sim-selo-ok">feito</span> : <span className="sim-selo-divergente">nunca entrou</span>}</td>
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
          <input className="dialog__input" value={nome} onChange={(e) => setNome(e.target.value)} autoFocus />
        </Campo>
        <Campo label="E-mail">
          <input className="dialog__input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </Campo>
      </Linha2>
      <p className="agendar__ajuda">
        Use o mesmo e-mail do Canvas: o SAS liga o login pelo Canvas sozinho — agora, ou na primeira vez que a pessoa entrar por ele.
      </p>
      {erro && <div className="agendar__erro">{erro}</div>}
    </Dialogo>
  );
}
