import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

import { Campo, Dialogo } from '../../componentes/dialogos/Dialogo';
import { CabecaDeCampo } from '../../componentes/ui/Campo';
import { BarraFiltros, Busca, Pills } from '../../componentes/ui/filtros/BarraFiltros';
import { Kpi } from '../../componentes/ui/Kpi';
import { resumirSelecao, resumirTexto } from '../../dominio/filtros';
import { ROTULO_DA_REFEICAO } from '../../dominio/cantina';
import {
  useCantinas, useConcederDireito, useCriarContaDeCantina, useDireitos,
  useEditarContaDeCantina, useRedefinirSenhaDeCantina, useSalvarRestricao,
} from '../../hooks/cantina';
import * as sessao from '../../servicos/sessao';
import type { AlunoComDireito, Refeicao } from '../../tipos/cantina';
import { normalizar } from '../../util/formato';

// A CANTINA na administração — duas metades, e as DUAS são de escrita
// exclusiva do administrador (docs/38 §6).
//
//   * em cima, as contas da cantina — mesma regra da 0045: criar login para
//     outra pessoa fica com UMA conta;
//   * embaixo, quem tem direito a refeição, com concessão em LOTE.
//
// ⚠️ Esta é a primeira tela da coordenação em que as duas metades são só do
// administrador. Para o coordenador comum ela é uma tela de leitura inteira — e
// é desenhada como tal: o que ele não pode não aparece, em vez de aparecer
// cinza. Botão que existe para dar 403 ensina a pessoa a desconfiar da tela.
// Ele continua entrando porque as duas perguntas ("quantos alunos comem aqui",
// "a cantina lançou o cardápio de amanhã") são de coordenação.
//
// ⚠️ **A concessão em lote existe POR CAUSA da decisão de que só o
// administrador concede**, não apesar dela. Com uma única pessoa autorizada,
// ligar o direito de 80 alunos um a um é a tarefa que não acontece — e o que
// não acontece na véspera do primeiro dia letivo derruba a feature inteira.

type FiltroDireito = 'almoco' | 'janta' | 'sem';

export function AdministracaoCantina() {
  const souAdministrador = sessao.ehAdministrador();
  const { data: cantinas = [] } = useCantinas();
  const { data: painel } = useDireitos();

  const [filtros, setFiltros] = useState<ReadonlySet<string>>(new Set());
  const [busca, setBusca] = useState('');
  const [selecao, setSelecao] = useState<ReadonlySet<string>>(new Set());
  const [criandoConta, setCriandoConta] = useState(false);
  const [editandoRestricao, setEditandoRestricao] = useState<AlunoComDireito | null>(null);
  // A senha sorteada aparece UMA vez, aqui, e nunca mais — é o contrato da
  // rota. Fica até o administrador fechar, para ele copiar com calma.
  const [senhaRevelada, setSenhaRevelada] = useState<{ email: string; senha: string } | null>(null);

  const conceder = useConcederDireito();

  const alunos = useMemo(() => {
    const lista = painel?.alunos ?? [];
    const q = normalizar(busca.trim());
    return lista.filter((a) => {
      if (filtros.has('sem') && a.direitos.length) return false;
      if (filtros.has('almoco') && !a.direitos.includes('almoco')) return false;
      if (filtros.has('janta') && !a.direitos.includes('janta')) return false;
      if (q && !normalizar(a.nome).includes(q) && !(a.matricula ?? '').includes(q)) return false;
      return true;
    });
  }, [painel, filtros, busca]);

  function alternarFiltro(v: string) {
    setFiltros((s) => {
      const novo = new Set(s);
      // 'sem' exclui os outros dois: "sem direito" e "tem almoço" não se
      // combinam, e deixar combinar devolveria lista vazia sem explicação.
      if (novo.has(v)) novo.delete(v);
      else if (v === 'sem') { novo.clear(); novo.add(v); }
      else { novo.delete('sem'); novo.add(v); }
      return novo;
    });
  }

  function aplicarEmLote(refeicao: Refeicao, ligar: boolean) {
    if (!selecao.size) return;
    conceder.mutate(
      { aluno_ids: [...selecao], refeicao, conceder: ligar },
      { onSuccess: () => setSelecao(new Set()) },
    );
  }

  return (
    <div className="tela">
      <CabecaDeCampo
        titulo="A cantina"
        para="/cantina"
        destino="os cardápios"
        acoes={<Link className="btn btn--fino" to="/administracao">Administração</Link>}
      />

      {/* ─── Metade 1 · as contas ─────────────────────────────────────── */}
      <section className="card">
        <header className="tela-cabecalho">
          <h2 className="tela-subtitulo">Quem lança o cardápio</h2>
          {souAdministrador && cantinas.length > 0 && (
            <button type="button" className="btn" onClick={() => setCriandoConta(true)}>
              Nova conta
            </button>
          )}
        </header>

        {!cantinas.length && (
          <p className="cant-vazio">
            Nenhuma cantina cadastrada ainda.
            {souAdministrador
              ? ' Crie a cantina antes de criar contas.'
              : ' Peça ao administrador do SAS para cadastrar.'}
          </p>
        )}

        {cantinas.map((cantina) => (
          <div key={cantina.id} className="cant-admin__cantina">
            <h3 className="cant-admin__nome">
              {cantina.nome}
              {!cantina.ativo && <span className="cant-tarja">inativa</span>}
            </h3>
            <p className="cant-sub">
              Prazo padrão: {cantina.prazo_padrao_dias_antes === 0
                ? 'no próprio dia'
                : `${cantina.prazo_padrao_dias_antes} dia(s) antes`}
              {' '}às {cantina.prazo_padrao_hora.slice(0, 5)}
            </p>
            <ContasDaCantina
              contas={cantina.contas}
              souAdministrador={souAdministrador}
              onSenha={setSenhaRevelada}
            />
          </div>
        ))}
      </section>

      {/* ─── Metade 2 · quem come ─────────────────────────────────────── */}
      <section className="card">
        <header className="tela-cabecalho">
          <h2 className="tela-subtitulo">Quem tem direito a refeição</h2>
        </header>

        <div className="kpi-grid kpi-grid--cartoes">
          <Kpi rotulo="Alunos ativos" valor={painel?.total ?? '—'} />
          <Kpi rotulo="Com direito" valor={painel?.comDireito ?? '—'} />
        </div>

        {/* A `tela` é a SUPERFÍCIE, não a rota — e o resumo é obrigatório em
            todo grupo: sem ele, um filtro em vigor fica invisível quando a
            faixa colapsa, e a tabela abaixo mente em silêncio. */}
        <BarraFiltros
          tela="administracao.cantina"
          algumAtivo={filtros.size > 0 || busca.trim() !== ''}
          onLimpar={() => { setFiltros(new Set()); setBusca(''); }}
          grupos={[
            {
              chave: 'direito', rotulo: 'Direito',
              resumo: resumirSelecao(
                filtros,
                [
                  { valor: 'almoco', label: 'almoço' },
                  { valor: 'janta', label: 'janta' },
                  { valor: 'sem', label: 'sem direito' },
                ],
                'recorte', 'recortes',
              ),
              corpo: (
                <Pills
                  opcoes={[
                    { valor: 'almoco' satisfies FiltroDireito, label: 'Almoço' },
                    { valor: 'janta' satisfies FiltroDireito, label: 'Janta' },
                    { valor: 'sem' satisfies FiltroDireito, label: 'Sem direito' },
                  ]}
                  selecionados={filtros}
                  onToggle={alternarFiltro}
                />
              ),
            },
            {
              chave: 'busca', rotulo: 'Buscar',
              resumo: resumirTexto(busca),
              corpo: (
                <Busca valor={busca} onChange={setBusca} placeholder="Nome ou matrícula…" />
              ),
            },
          ]}
        />

        {souAdministrador && (
          <div className="cant-admin__lote" aria-live="polite">
            <span>
              {selecao.size
                ? `${selecao.size} selecionado${selecao.size === 1 ? '' : 's'}`
                : 'Selecione alunos para conceder ou revogar em lote'}
            </span>
            {(['almoco', 'janta'] as Refeicao[]).map((refeicao) => (
              <span key={refeicao} className="cant-admin__par">
                <button
                  type="button" className="btn"
                  disabled={!selecao.size || conceder.isPending}
                  onClick={() => aplicarEmLote(refeicao, true)}
                >
                  + {ROTULO_DA_REFEICAO[refeicao]}
                </button>
                <button
                  type="button" className="btn btn--fino"
                  disabled={!selecao.size || conceder.isPending}
                  onClick={() => aplicarEmLote(refeicao, false)}
                >
                  − {ROTULO_DA_REFEICAO[refeicao]}
                </button>
              </span>
            ))}
          </div>
        )}

        <table className="data-table">
          <thead>
            <tr>
              {souAdministrador && <th aria-label="Seleção" />}
              <th>Aluno</th>
              <th>Turma</th>
              <th>Direito</th>
              <th>Restrição alimentar</th>
            </tr>
          </thead>
          <tbody>
            {alunos.map((aluno) => (
              <tr key={aluno.id}>
                {souAdministrador && (
                  <td>
                    <input
                      type="checkbox"
                      aria-label={`Selecionar ${aluno.nome}`}
                      checked={selecao.has(aluno.id)}
                      onChange={() => setSelecao((s) => {
                        const novo = new Set(s);
                        if (novo.has(aluno.id)) novo.delete(aluno.id);
                        else novo.add(aluno.id);
                        return novo;
                      })}
                    />
                  </td>
                )}
                <td>{aluno.nome}</td>
                <td>{aluno.turma ?? '—'}</td>
                <td>
                  {aluno.direitos.length
                    ? aluno.direitos.map((r) => ROTULO_DA_REFEICAO[r]).join(' · ')
                    : '—'}
                </td>
                <td>
                  {aluno.restricaoAlimentar ?? '—'}
                  {souAdministrador && (
                    <button
                      type="button" className="btn btn--fino"
                      onClick={() => setEditandoRestricao(aluno)}
                    >
                      {aluno.restricaoAlimentar ? 'Editar' : 'Anotar'}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!alunos.length && <p className="cant-vazio">Nenhum aluno com esses filtros.</p>}
      </section>

      {criandoConta && cantinas.length > 0 && (
        <DialogoNovaConta
          cantinaId={cantinas[0].id}
          onFechar={() => setCriandoConta(false)}
          onSenha={(s) => { setCriandoConta(false); setSenhaRevelada(s); }}
        />
      )}

      {editandoRestricao && (
        <DialogoRestricao aluno={editandoRestricao} onFechar={() => setEditandoRestricao(null)} />
      )}

      {senhaRevelada && (
        <Dialogo
          titulo="Senha criada"
          subtitulo="Ela aparece uma única vez. Entregue pelo canal do colégio."
          onFechar={() => setSenhaRevelada(null)}
          rodape={<button type="button" className="btn" onClick={() => setSenhaRevelada(null)}>Fechar</button>}
        >
          <p><b>{senhaRevelada.email}</b></p>
          <p className="cant-senha">{senhaRevelada.senha}</p>
          <p className="cant-sub">
            O hash é de mão única: depois de fechar, ninguém — nem o sistema — lê esta senha de
            volta. Se perder, redefina.
          </p>
        </Dialogo>
      )}
    </div>
  );
}

function ContasDaCantina({
  contas, souAdministrador, onSenha,
}: {
  contas: { id: string; email: string; nome: string; ativo: boolean; ultimo_login_em: string | null }[];
  souAdministrador: boolean;
  onSenha: (s: { email: string; senha: string }) => void;
}) {
  const editar = useEditarContaDeCantina();
  const redefinir = useRedefinirSenhaDeCantina();

  if (!contas.length) return <p className="cant-vazio">Nenhuma conta nesta cantina.</p>;

  return (
    <table className="data-table">
      <thead>
        <tr>
          <th>Nome</th><th>E-mail</th><th>Último acesso</th>
          {souAdministrador && <th aria-label="Ações" />}
        </tr>
      </thead>
      <tbody>
        {contas.map((conta) => (
          <tr key={conta.id} className={conta.ativo ? '' : 'linha--inativa'}>
            <td>{conta.nome}</td>
            <td>{conta.email}</td>
            <td>{conta.ultimo_login_em
              ? new Date(conta.ultimo_login_em).toLocaleString('pt-BR', {
                  day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
                })
              : 'nunca'}</td>
            {souAdministrador && (
              <td>
                <button
                  type="button" className="btn btn--fino"
                  onClick={() => editar.mutate({ id: conta.id, corpo: { ativo: !conta.ativo } })}
                >
                  {conta.ativo ? 'Desativar' : 'Reativar'}
                </button>
                <button
                  type="button" className="btn btn--fino"
                  onClick={() => redefinir.mutate(conta.id, {
                    onSuccess: (r) => onSenha({ email: conta.email, senha: r.senha_nova }),
                  })}
                >
                  Redefinir senha
                </button>
              </td>
            )}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function DialogoNovaConta({
  cantinaId, onFechar, onSenha,
}: {
  cantinaId: string;
  onFechar: () => void;
  onSenha: (s: { email: string; senha: string }) => void;
}) {
  const [email, setEmail] = useState('');
  const [nome, setNome] = useState('');
  const criar = useCriarContaDeCantina();

  return (
    <Dialogo
      titulo="Nova conta de cantina"
      subtitulo="A senha é sorteada e mostrada uma única vez."
      onFechar={onFechar}
      rodape={(
        <>
          <button type="button" className="btn btn--fino" onClick={onFechar}>Cancelar</button>
          <button
            type="button" className="btn"
            disabled={!email.trim() || !nome.trim() || criar.isPending}
            onClick={() => criar.mutate(
              { cantina_id: cantinaId, email: email.trim(), nome: nome.trim() },
              { onSuccess: (r) => onSenha({ email: r.email, senha: r.senha_inicial }) },
            )}
          >
            {criar.isPending ? 'Criando…' : 'Criar'}
          </button>
        </>
      )}
    >
      <Campo label="Nome">
        <input className="input" value={nome} onChange={(e) => setNome(e.target.value)} />
      </Campo>
      <Campo label="E-mail">
        <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
      </Campo>
      {criar.isError && <p className="cant-erro" role="alert">{(criar.error as Error).message}</p>}
    </Dialogo>
  );
}

/**
 * A restrição alimentar (docs/38 §2.6).
 *
 * ⚠️ Quem preenche é a COORDENAÇÃO, e não o aluno: autodeclaração de saúde por
 * menor abre um problema de consentimento que este produto não resolve. O
 * diálogo diz onde o texto vai aparecer, porque quem digita precisa saber que
 * outra pessoa vai ler.
 */
function DialogoRestricao({
  aluno, onFechar,
}: { aluno: AlunoComDireito; onFechar: () => void }) {
  const [texto, setTexto] = useState(aluno.restricaoAlimentar ?? '');
  const salvar = useSalvarRestricao();

  return (
    <Dialogo
      titulo={`Restrição alimentar · ${aluno.nome}`}
      subtitulo="Aparece para a cantina ao lado do pedido, e em lugar nenhum mais."
      onFechar={onFechar}
      rodape={(
        <>
          <button type="button" className="btn btn--fino" onClick={onFechar}>Cancelar</button>
          <button
            type="button" className="btn"
            disabled={salvar.isPending}
            onClick={() => salvar.mutate(
              { alunoId: aluno.id, restricao: texto.trim() || null },
              { onSuccess: onFechar },
            )}
          >
            {salvar.isPending ? 'Salvando…' : 'Salvar'}
          </button>
        </>
      )}
    >
      <Campo label="O que a cantina precisa saber">
        <textarea
          className="input"
          rows={3}
          value={texto}
          placeholder="Ex.: alergia a amendoim"
          onChange={(e) => setTexto(e.target.value)}
        />
      </Campo>
      <p className="cant-sub">
        Deixe em branco para apagar. O conteúdo não vai para a trilha de auditoria — só o fato de
        ter sido alterado.
      </p>
    </Dialogo>
  );
}
