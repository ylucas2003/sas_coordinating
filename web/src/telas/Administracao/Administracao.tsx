import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

import { Campo, Dialogo, Linha2 } from '../../componentes/dialogos/Dialogo';
import { AbasAdmin } from '../../componentes/layout/AbasAdmin';
import { BarraFiltros, Busca, Pills } from '../../componentes/ui/filtros/BarraFiltros';
import { resumirSelecao, resumirTexto } from '../../dominio/filtros';
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
    <div className="tela">
      <AbasAdmin />

      <div className="tela-cabecalho">
        <div>
          <h1 className="tela-titulo">Contas da coordenação</h1>
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
            <b>Criar um acesso aqui não cria nada no Canvas.</b> A conta passa a existir só no
            SAS, e funciona inteira com e-mail e senha. Se você usar <b>o mesmo e-mail que a
            pessoa tem no Canvas</b>, ela também poderá entrar pelo botão do Canvas — na hora,
            pelo botão “Ligar ao Canvas”, ou sozinho no primeiro login. E o caminho contrário
            não existe: <b>ser admin no Canvas não dá acesso ao SAS</b> enquanto alguém não
            criar a conta por aqui.
          </p>
        </div>
        <button className="btn btn-primary" onClick={() => setCriando(true)}>Nova conta</button>
      </div>

      <section className="card">
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

      <div className="tela-cabecalho">
        <div>
          <h2 className="tela-titulo">Acesso dos alunos</h2>
          <p className="tela-subtitulo">Quem já criou a senha e quem nunca entrou. Para liberar de novo, use a ficha do aluno.</p>
        </div>
      </div>

      {acessos && (
        <div className="kpi-grid kpi-grid--cartoes">
          <Kpi rotulo="Alunos ativos" valor={acessos.total} />
          <Kpi rotulo="Já fizeram primeiro acesso" valor={acessos.comAcesso} sufixo={` de ${acessos.total}`} tone="tone-verde" />
          <Kpi rotulo="Nunca entraram" valor={acessos.total - acessos.comAcesso} tone={acessos.total - acessos.comAcesso > 0 ? 'tone-ambar' : ''} />
        </div>
      )}

      <BarraFiltros
        tela="administracao"
        algumAtivo={filtros.size > 0 || busca.trim() !== ''}
        onLimpar={() => { setFiltros(new Set()); setBusca(''); }}
        grupos={[
          {
            chave: 'acesso', rotulo: 'Primeiro acesso',
            resumo: resumirSelecao(
              filtros,
              [
                { valor: 'com', label: 'já fez o primeiro acesso' },
                { valor: 'sem', label: 'nunca entrou' },
              ],
              'situação', 'situações',
            ),
            corpo: (
              <Pills
                opcoes={[
                  { valor: 'com' satisfies FiltroAcesso, label: 'Já fez' },
                  { valor: 'sem' satisfies FiltroAcesso, label: 'Nunca entrou' },
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
            <tr><th>Aluno</th><th>Matrícula</th><th>E-mail</th><th>Primeiro acesso</th><th>Último login</th></tr>
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
            lá. Quem entrar pelo botão do Canvas nem chega a usá-la.
          </p>
          <code className="agendar__preview-nome" style={{ fontSize: 18, userSelect: 'all' }}>{senhaRevelada.senha}</code>
        </Dialogo>
      )}
    </div>
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
        Use o mesmo e-mail do Canvas: o SAS liga o login pelo Canvas sozinho — agora, ou na
        primeira vez que a pessoa entrar por ele. Com outro e-mail a conta funciona igual, só
        entra por senha.
      </p>
      {erro && <div className="agendar__erro">{erro}</div>}
    </Dialogo>
  );
}
