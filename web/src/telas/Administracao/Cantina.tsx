import { useEffect, useMemo, useRef, useState } from 'react';

import { Campo, Dialogo } from '../../componentes/dialogos/Dialogo';
import { CabecaDeCampo } from '../../componentes/ui/Campo';
import { BarraFiltros, Busca, Pills } from '../../componentes/ui/filtros/BarraFiltros';
import { Kpi } from '../../componentes/ui/Kpi';
import { resumirSelecao, resumirTexto } from '../../dominio/filtros';
import { ROTULO_DA_REFEICAO } from '../../dominio/cantina';
import { GLIFO_DA_REFEICAO } from '../Cantina/GradeDeCardapios';
import {
  useCantinas, useConcederDireito, useCriarCantina, useCriarContaDeCantina, useDireitos,
  useEditarCantina, useEditarContaDeCantina, useRedefinirSenhaDeCantina, useSalvarRestricao,
} from '../../hooks/cantina';
import * as sessao from '../../servicos/sessao';
import type { AlunoComDireito, CantinaAdmin, ContaDeCantina, Refeicao } from '../../tipos/cantina';
import { normalizar } from '../../util/formato';

// A CANTINA que a coordenação ESCREVE — quem come, e quem lança.
//
// Era UMA tela em `/administracao/cantina`, com as duas metades empilhadas. Ela
// se dividiu em duas rotas na fase 5 do docs/39, pela regra C3 do padrão de
// campo: cada destino é tela inteira com URL própria. As duas perguntas não têm
// nada a ver uma com a outra — "quem come aqui?" é sobre 900 alunos, "quem
// lança o cardápio?" é sobre duas contas —, e empilhá-las obrigava a rolar por
// uma para chegar à outra.
//
//   /cantina/direitos   quem come — ESCRITA do administrador, leitura de todos
//   /cantina/acesso     as cantinas e as contas — SÓ ADMINISTRADOR
//
// ⚠️ Os dois arquivos continuam em `telas/Administracao/` embora as rotas sejam
// `/cantina/*`: mover é trabalho de outra rodada, e o import errado é mais
// barato de consertar que um arquivo movido no meio de quatro agentes.

const REFEICOES: Refeicao[] = ['almoco', 'janta'];

// ─── /cantina/direitos · quem come aqui ───────────────────────────────────

type FiltroDireito = 'almoco' | 'janta' | 'sem';

/**
 * Quem tem direito a refeição.
 *
 * São DUAS telas na mesma rota, e a de leitura não é a de escrita com botões
 * cinzas — é uma tela mais curta:
 *
 *   administrador   caixa de seleção, barra de lote e pílula que alterna na
 *                   própria linha;
 *   coordenador     a mesma lista, sem caixa e sem barra, com só os direitos
 *                   que o aluno TEM (uma pílula vazia de "janta" que ele não
 *                   pode ligar é um botão que existe para dar erro).
 *
 * ⚠️ **A concessão em lote existe POR CAUSA da decisão de que só o
 * administrador concede**, não apesar dela. Com uma única pessoa autorizada,
 * ligar o direito de 80 alunos um a um é a tarefa que não acontece — e o que
 * não acontece na véspera do primeiro dia letivo derruba a feature inteira.
 * A pílula na linha é o outro caso, o do meio do ano, quando muda um aluno.
 * Os dois convivem porque o ALVO é diferente: a pílula é do aluno, a barra é
 * da seleção.
 */
export function DireitosDaCantina() {
  const souAdministrador = sessao.ehAdministrador();
  const { data: painel, isLoading, isError } = useDireitos();

  const [filtros, setFiltros] = useState<ReadonlySet<string>>(new Set());
  const [busca, setBusca] = useState('');
  const [selecao, setSelecao] = useState<ReadonlySet<string>>(new Set());
  const [restricaoAberta, setRestricaoAberta] = useState<string | null>(null);
  const [editandoRestricao, setEditandoRestricao] = useState<AlunoComDireito | null>(null);

  // Duas instâncias da MESMA mutação, de propósito: o `isPending` de uma
  // aplicação em lote não pode congelar a pílula da linha, e vice-versa. É o
  // que faz os dois modos conviverem sem brigar.
  const emLote = useConcederDireito();
  const naLinha = useConcederDireito();

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

  const porRefeicao = useMemo(() => {
    const lista = painel?.alunos ?? [];
    return {
      almoco: lista.filter((a) => a.direitos.includes('almoco')).length,
      janta: lista.filter((a) => a.direitos.includes('janta')).length,
      ambos: lista.filter((a) => a.direitos.length === 2).length,
    };
  }, [painel]);

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
    emLote.mutate(
      { aluno_ids: [...selecao], refeicao, conceder: ligar },
      { onSuccess: () => setSelecao(new Set()) },
    );
  }

  return (
    <div className="tela">
      <CabecaDeCampo
        titulo="Quem come aqui?"
        para="/cantina"
        destino="a cantina"
        acoes={
          <div className="cant-kpis">
            <div className="cant-kpi">
              <Kpi rotulo="Alunos ativos" valor={painel?.total ?? '—'} />
              <span className="cant-kpi__legenda">na lista da coordenação</span>
            </div>
            <div className="cant-kpi">
              <Kpi rotulo="Com direito" valor={painel?.comDireito ?? '—'} />
              <span className="cant-kpi__legenda">
                {painel
                  ? `${porRefeicao.almoco} almoço · ${porRefeicao.janta} janta`
                    + ` · ${porRefeicao.ambos} os dois`
                  : '—'}
              </span>
            </div>
          </div>
        }
      />

      <p className="cant-intro">
        {souAdministrador
          ? 'Você concede e revoga: em lote, para a véspera do ano letivo, ou na própria linha,'
            + ' para o caso do meio do ano.'
          : 'Leitura. Conceder direito é do administrador — esta tela não tem caixa de seleção'
            + ' nem barra de lote.'}
      </p>

      {/* A `tela` é a SUPERFÍCIE, não a rota — e ela mudou junto com a divisão:
          `/cantina/direitos` é uma superfície nova, e herdar a preferência de
          filtro da tela antiga traria um recorte que ninguém escolheu aqui.
          O resumo é obrigatório em todo grupo: sem ele, um filtro em vigor fica
          invisível quando a faixa colapsa, e a tabela abaixo mente em silêncio. */}
      <BarraFiltros
        tela="cantina.direitos"
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

      {/* A barra só existe quando há seleção. Uma barra permanente dizendo
          "selecione alunos" ocupa a linha mais cara da tela para dar instrução
          — e a instrução já está no subtítulo, onde ela é lida uma vez. */}
      {souAdministrador && selecao.size > 0 && (
        <div className="cant-lote" aria-live="polite">
          <span className="cant-lote__quantos">
            {selecao.size} aluno{selecao.size === 1 ? '' : 's'} selecionado{selecao.size === 1 ? '' : 's'}
            <span className="cant-lote__nota"> · a ação vale para todos de uma vez</span>
          </span>
          {REFEICOES.map((refeicao) => (
            <span key={refeicao} className="cant-lote__par">
              <button
                type="button" className="cant-tecla cant-tecla--conceder"
                disabled={emLote.isPending}
                onClick={() => aplicarEmLote(refeicao, true)}
              >
                + {ROTULO_DA_REFEICAO[refeicao]}
              </button>
              <button
                type="button" className="cant-tecla"
                disabled={emLote.isPending}
                onClick={() => aplicarEmLote(refeicao, false)}
              >
                − {ROTULO_DA_REFEICAO[refeicao]}
              </button>
            </span>
          ))}
          <button
            type="button" className="cant-tecla cant-tecla--nua"
            onClick={() => setSelecao(new Set())}
          >
            Limpar seleção
          </button>
        </div>
      )}

      {emLote.isError && (
        <p className="cant-erro" role="alert">{(emLote.error as Error).message}</p>
      )}
      {naLinha.isError && (
        <p className="cant-erro" role="alert">{(naLinha.error as Error).message}</p>
      )}

      <div className="cant-superficie">
        <table className="data-table cant-direitos">
          <thead>
            <tr>
              {souAdministrador && <th className="cant-direitos__marca" aria-label="Seleção" />}
              <th>Aluno</th>
              <th>Turma</th>
              <th>Direito</th>
              <th>Restrição alimentar</th>
            </tr>
          </thead>
          <tbody>
            {alunos.map((aluno) => (
              <tr key={aluno.id} className={selecao.has(aluno.id) ? 'cant-direitos__linha--marcada' : ''}>
                {souAdministrador && (
                  <td className="cant-direitos__marca">
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
                <td>
                  <span className="cant-direitos__aluno">
                    <span className="cant-direitos__iniciais" aria-hidden="true">
                      {iniciais(aluno.nome)}
                    </span>
                    <span>
                      <span className="cant-direitos__nome">{aluno.nome}</span>
                      {aluno.matricula && (
                        <span className="cant-direitos__matricula">matrícula {aluno.matricula}</span>
                      )}
                    </span>
                  </span>
                </td>
                <td>{aluno.turma ?? '—'}</td>
                <td>
                  <PilulasDeDireito
                    aluno={aluno}
                    souAdministrador={souAdministrador}
                    ocupado={naLinha.isPending}
                    onAlternar={(refeicao, conceder) => naLinha.mutate({
                      aluno_ids: [aluno.id], refeicao, conceder,
                    })}
                  />
                </td>
                <td>
                  <Restricao
                    aluno={aluno}
                    aberta={restricaoAberta === aluno.id}
                    podeEditar={souAdministrador}
                    onAlternar={() => setRestricaoAberta((id) => (id === aluno.id ? null : aluno.id))}
                    onEditar={() => setEditandoRestricao(aluno)}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {isLoading && <p className="cant-vazio">Carregando…</p>}
        {isError && <p className="cant-vazio">Não consegui carregar a lista.</p>}
        {!isLoading && !isError && !alunos.length && (
          <p className="cant-vazio">Nenhum aluno com esses filtros.</p>
        )}
      </div>

      <p className="cant-nota">
        A restrição é dado de saúde de menor: a coluna diz que existe, e o texto abre sob clique —
        alcançável por quem precisa, não varrido por quem procurava outra coisa.
      </p>

      {editandoRestricao && (
        <DialogoRestricao aluno={editandoRestricao} onFechar={() => setEditandoRestricao(null)} />
      )}
    </div>
  );
}

/**
 * As pílulas de direito, na própria linha.
 *
 * Para o administrador são BOTÕES que alternam; para o coordenador comum são
 * `<span>`, e só as que o aluno TEM. `cursor: default` esconderia a promessa do
 * mouse e a manteria para o teclado e o leitor de tela — que é justamente quem
 * não pode receber a promessa de revogar um direito que o papel não altera.
 */
function PilulasDeDireito({
  aluno, souAdministrador, ocupado, onAlternar,
}: {
  aluno: AlunoComDireito;
  souAdministrador: boolean;
  ocupado: boolean;
  onAlternar: (refeicao: Refeicao, conceder: boolean) => void;
}) {
  const visiveis = REFEICOES.filter((r) => souAdministrador || aluno.direitos.includes(r));
  if (!visiveis.length) return <span className="cant-direitos__nenhum">nenhum</span>;

  return (
    <span className="cant-pilulas">
      {visiveis.map((refeicao) => {
        const tem = aluno.direitos.includes(refeicao);
        const rotulo = ROTULO_DA_REFEICAO[refeicao];
        const glifo = tem ? 'M4 12.6l5 5L20 6.4' : GLIFO_DA_REFEICAO[refeicao];
        const face = (
          <>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor"
              strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d={glifo} />
            </svg>
            {rotulo}
          </>
        );
        const classe = `cant-pilula${tem ? ' cant-pilula--tem' : ''}`;

        if (!souAdministrador) return <span key={refeicao} className={classe}>{face}</span>;
        return (
          <button
            key={refeicao}
            type="button"
            className={classe}
            aria-pressed={tem}
            aria-label={`${tem ? 'Revogar' : 'Conceder'} ${rotulo.toLowerCase()} de ${aluno.nome}`}
            disabled={ocupado}
            onClick={() => onAlternar(refeicao, !tem)}
          >
            {face}
          </button>
        );
      })}
    </span>
  );
}

/**
 * A restrição alimentar — a revelação deliberada.
 *
 * ⚠️ É **dado de saúde de menor**, a categoria mais sensível da LGPD e o único
 * dado dessa natureza no produto. Até 05/09/2026 ele era o texto na quarta
 * coluna de uma tabela de 900 linhas, visível a qualquer coordenador que
 * rolasse. A decisão (docs/39 fase 5): a coluna diz apenas que EXISTE
 * restrição, e o texto abre sob clique. Editar continua só do administrador;
 * **ler passa a ser ato deliberado para todos**.
 *
 * Não está escondido atrás de nada bonito e difícil de achar: é um alvo de
 * 44px, com o rótulo dizendo o que vai acontecer. Quem precisa, precisa rápido.
 *
 * ⚠️ **A metade que falta é do servidor.** `GET /administracao/direito-refeicao`
 * ainda manda o texto de todo mundo junto da lista, então o dado já está no
 * navegador antes do clique — o gesto protege a LEITURA humana, não o tráfego.
 * O conserto é mandar só `temRestricao` e buscar o texto sob demanda; enquanto
 * isso não existe, não há estado "abrindo" para desenhar, e inventar um seria
 * fingir uma proteção que não está lá.
 */
function Restricao({
  aluno, aberta, podeEditar, onAlternar, onEditar,
}: {
  aluno: AlunoComDireito;
  aberta: boolean;
  podeEditar: boolean;
  onAlternar: () => void;
  onEditar: () => void;
}) {
  if (!aluno.restricaoAlimentar) {
    return (
      <span className="cant-direitos__nenhum">
        nenhuma
        {podeEditar && (
          <button type="button" className="cant-tecla cant-tecla--nua" onClick={onEditar}>
            Anotar
          </button>
        )}
      </span>
    );
  }

  return (
    <>
      <button
        type="button"
        className="cant-pilula cant-pilula--saude"
        aria-expanded={aberta}
        onClick={onAlternar}
      >
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor"
          strokeWidth="2" strokeLinecap="round" aria-hidden="true">
          <circle cx="12" cy="12" r="8.6" />
          <path d="M12 8v5M12 16.4v.4" />
        </svg>
        {aberta ? 'Fechar' : 'Tem restrição · ver'}
      </button>

      {aberta && (
        <div className="cant-saude">
          <span className="cant-saude__olho">Dado de saúde · aberto por você agora</span>
          <p className="cant-saude__texto">{aluno.restricaoAlimentar}</p>
          <div className="cant-saude__acoes">
            <button type="button" className="cant-tecla" onClick={onAlternar}>Fechar</button>
            {podeEditar && (
              <button type="button" className="cant-tecla cant-tecla--conceder" onClick={onEditar}>
                Editar
              </button>
            )}
          </div>
        </div>
      )}
    </>
  );
}

// ─── /cantina/acesso · quem lança o cardápio ──────────────────────────────

/**
 * As cantinas e as contas que lançam por elas. **Só administrador** — o portão
 * é a rota (`App.tsx`), e é por isso que não há um único ramo de papel aqui
 * dentro: uma tela que se desenha em dois papéis convida a alcançá-la nos dois.
 *
 * Três coisas desta tela precisaram de desenho próprio, e as três estão
 * comentadas onde acontecem: a senha que aparece uma vez, os dois raios de
 * explosão de "desativar", e o fato de nada ser apagado.
 */
export function AcessoDaCantina() {
  const { data: cantinas = [], isLoading } = useCantinas();
  const [editandoCantina, setEditandoCantina] = useState<CantinaAdmin | 'nova' | null>(null);
  const [criandoConta, setCriandoConta] = useState<string | null>(null);
  const [senhaRevelada, setSenhaRevelada] = useState<{ email: string; senha: string } | null>(null);

  return (
    <div className="tela">
      <CabecaDeCampo titulo="Quem lança o cardápio?" para="/cantina" destino="a cantina" />
      <p className="cant-intro">
        {cantinas.length
          ? 'A cantina como estabelecimento, e as contas que lançam por ela. Nada aqui é apagado.'
          : 'Nenhuma cantina, nenhuma conta — e o caminho para a primeira está nesta tela.'}
      </p>

      {senhaRevelada && (
        <SenhaRevelada
          email={senhaRevelada.email}
          senha={senhaRevelada.senha}
          onFechar={() => setSenhaRevelada(null)}
        />
      )}

      {isLoading && <p className="cant-vazio">Carregando…</p>}

      {!isLoading && !cantinas.length && (
        <PrimeiroDia onCriar={() => setEditandoCantina('nova')} />
      )}

      {cantinas.map((cantina) => (
        <section key={cantina.id} className="cant-estabelecimento">
          <header className="cant-estabelecimento__cabeca">
            <div>
              <span className="cant-refeicao__olho">O estabelecimento</span>
              <h2 className="cant-estabelecimento__nome">
                {cantina.nome}
                {!cantina.ativo && <span className="cant-tarja">inativa</span>}
              </h2>
              <p className="cant-sub">
                {/* A REGRA da casa, que pré-preenche cada cardápio novo. Não é o
                    prazo: o prazo é do dia, e a cantina troca no editor. */}
                prazo padrão: {cantina.prazo_padrao_dias_antes === 0
                  ? 'no próprio dia'
                  : `${cantina.prazo_padrao_dias_antes} dia${cantina.prazo_padrao_dias_antes === 1 ? '' : 's'} antes`}
                , às {cantina.prazo_padrao_hora.slice(0, 5)}
              </p>
            </div>
            {/* UM botão, e não os dois da prancheta: o diálogo edita o nome e a
                regra de prazo juntos, e dois botões abrindo a mesma coisa
                prometeriam dois escopos que não existem. */}
            <button
              type="button" className="cant-tecla"
              onClick={() => setEditandoCantina(cantina)}
            >
              Editar nome e prazo padrão
            </button>
          </header>

          <div className="cant-estabelecimento__risco">
            <p className="cant-sub">
              {/* ⚠️ **Não é o mesmo que desativar as contas uma a uma**, e a
                  diferença é o ponto: `_login_da_cantina` confere
                  `cantina.ativo` além de `usuario_cantina.ativo`, então
                  desligar aqui tranca TODO mundo daquela cantina de uma vez —
                  inclusive uma conta criada depois. */}
              Desativar a cantina tranca todas as contas dela de uma vez, inclusive uma criada
              depois. É o botão para “a cantina saiu do colégio”, não para “a Dona Maria saiu de
              férias”.
            </p>
            <DesativarCantina cantina={cantina} />
          </div>

          <ContasDaCantina
            cantina={cantina}
            onCriarConta={() => setCriandoConta(cantina.id)}
            onSenha={setSenhaRevelada}
          />
        </section>
      ))}

      {/* ⚠️ NÃO fica escondido atrás de "existe cantina": era assim, e o
          resultado é que a PRIMEIRA cantina não tinha como nascer — a tela
          dizia "crie a cantina antes de criar contas" e não oferecia onde. Um
          estado vazio que dá uma instrução sem oferecer o caminho é pior que um
          estado vazio mudo. Com cantina cadastrada o botão continua aqui, para
          a segunda. */}
      {!!cantinas.length && (
        <button type="button" className="cant-tecla" onClick={() => setEditandoCantina('nova')}>
          Nova cantina
        </button>
      )}

      {editandoCantina && (
        <DialogoCantina
          cantina={editandoCantina === 'nova' ? null : editandoCantina}
          onFechar={() => setEditandoCantina(null)}
        />
      )}

      {criandoConta && (
        <DialogoNovaConta
          cantinaId={criandoConta}
          onFechar={() => setCriandoConta(null)}
          onSenha={(s) => { setCriandoConta(null); setSenhaRevelada(s); }}
        />
      )}
    </div>
  );
}

/**
 * O primeiro dia.
 *
 * ⚠️ **O estado vazio desta tela já causou defeito real** (docs/38): o botão de
 * criar conta ficava atrás de "já existe cantina", e a PRIMEIRA cantina não
 * tinha como nascer. Por isso este bloco não é um aviso: é a instrução com o
 * caminho ao lado dela, e a ordem escrita — a cantina primeiro, as contas
 * dentro dela.
 */
function PrimeiroDia({ onCriar }: { onCriar: () => void }) {
  return (
    <section className="cant-primeiro-dia">
      <div>
        <span className="cant-refeicao__olho">Primeiro dia</span>
        <h2 className="cant-primeiro-dia__titulo">Nenhuma cantina cadastrada</h2>
        <p className="cant-primeiro-dia__texto">
          A cantina vem primeiro, porque é ela que dá nome às contas e ao prazo padrão. Depois de
          criada, as contas de acesso aparecem abaixo dela — e o botão de criar conta fica aqui,
          não em outra tela.
        </p>
        <button type="button" className="cant-tecla cant-tecla--principal" onClick={onCriar}>
          Criar a primeira cantina
        </button>
      </div>
      {/* Duas fichas vazias, a de baixo pendurada na de cima: o desenho DIZ a
          ordem que o texto explica. */}
      <svg
        width="230" height="150" viewBox="0 0 230 150" fill="none"
        role="img" aria-label="Duas fichas vazias: a cantina, e a conta dentro dela"
        className="cant-primeiro-dia__desenho"
      >
        <rect x="10" y="18" width="200" height="52" rx="10" stroke="currentColor" strokeWidth="1.4" strokeDasharray="4 4" />
        <rect x="34" y="86" width="176" height="44" rx="10" stroke="currentColor" strokeWidth="1.4" strokeDasharray="4 4" />
        <path d="M22 70v34h10" stroke="currentColor" strokeWidth="1.4" />
      </svg>
    </section>
  );
}

/**
 * A senha aparece UMA vez e nunca mais.
 *
 * ⚠️ É o momento mais frágil da tela: quem fechar sem copiar cria uma conta
 * inútil. Por isso ela **não é um diálogo**: `Dialogo` fecha no clique do
 * fundo, e o clique do fundo é exatamente o gesto distraído que perde a senha.
 * Este painel fica no fluxo da tela, e sai só pelo botão que declara o que a
 * pessoa está afirmando ("já guardei").
 */
function SenhaRevelada({
  email, senha, onFechar,
}: { email: string; senha: string; onFechar: () => void }) {
  const [copia, setCopia] = useState<'nao' | 'feita' | 'falhou'>('nao');
  const painel = useRef<HTMLElement>(null);

  // O painel nasce no TOPO da tela, e "Redefinir senha" pode ter sido clicado
  // na última linha de uma lista rolada. Sem isto a senha aparece fora da
  // dobra, a pessoa não vê nada acontecer e clica de novo — gerando uma
  // segunda senha e invalidando a primeira, que ela também não viu.
  useEffect(() => {
    painel.current?.scrollIntoView({ block: 'center', behavior: 'smooth' });
  }, []);

  async function copiar() {
    try {
      await navigator.clipboard.writeText(senha);
      setCopia('feita');
    } catch {
      // Contexto sem clipboard (http simples, permissão negada). Falhar em
      // silêncio aqui seria o pior caso da tela: a pessoa acha que copiou.
      setCopia('falhou');
    }
  }

  return (
    <section className="cant-senha" aria-live="polite" ref={painel}>
      <span className="cant-refeicao__olho">A senha aparece uma vez</span>
      <p className="cant-senha__conta">{email}</p>
      <p className="cant-senha__valor"><code>{senha}</code></p>
      <div className="cant-senha__acoes">
        <button type="button" className="cant-tecla cant-tecla--principal" onClick={copiar}>
          {copia === 'feita' ? 'Copiada' : 'Copiar a senha'}
        </button>
        <button type="button" className="cant-tecla" onClick={onFechar}>
          Já guardei — fechar
        </button>
      </div>
      {copia === 'falhou' && (
        <p className="cant-erro" role="alert">
          Não consegui copiar por aqui. Selecione o texto acima e copie à mão antes de fechar.
        </p>
      )}
      <p className="cant-sub">
        O hash é de mão única: depois de fechar, ninguém — nem o sistema — lê esta senha de volta.
        Se perder, redefina.
      </p>
    </section>
  );
}

function ContasDaCantina({
  cantina, onCriarConta, onSenha,
}: {
  cantina: CantinaAdmin;
  onCriarConta: () => void;
  onSenha: (s: { email: string; senha: string }) => void;
}) {
  const editar = useEditarContaDeCantina();
  const redefinir = useRedefinirSenhaDeCantina();
  const contas = cantina.contas;

  return (
    <div className="cant-contas">
      <header className="cant-contas__cabeca">
        <span className="cant-refeicao__olho">
          Contas que lançam cardápio · {contas.length}
        </span>
        <button type="button" className="cant-tecla cant-tecla--principal" onClick={onCriarConta}>
          Criar conta
        </button>
      </header>

      {!contas.length && <p className="cant-vazio">Nenhuma conta nesta cantina.</p>}

      {contas.map((conta) => (
        <div key={conta.id} className="cant-conta">
          <div className="cant-conta__quem">
            <span className="cant-conta__nome">{conta.nome}</span>
            <span className="cant-conta__email">{conta.email}</span>
          </div>
          <span className="cant-conta__ultimo">{ultimoAcesso(conta)}</span>
          <span className={`cant-selo cant-selo--${conta.ativo ? 'aberto' : 'sem-cardapio'}`}>
            {conta.ativo ? 'ativa' : 'inativa'}
          </span>
          <div className="cant-conta__acoes">
            <button
              type="button" className="cant-tecla cant-tecla--fina"
              disabled={redefinir.isPending}
              onClick={() => redefinir.mutate(conta.id, {
                onSuccess: (r) => onSenha({ email: conta.email, senha: r.senha_nova }),
              })}
            >
              Redefinir senha
            </button>
            <button
              type="button" className="cant-tecla cant-tecla--fina"
              disabled={editar.isPending}
              onClick={() => editar.mutate({ id: conta.id, corpo: { ativo: !conta.ativo } })}
            >
              {conta.ativo ? 'Desativar' : 'Reativar'}
            </button>
          </div>
        </div>
      ))}

      {/* ⚠️ **Nada é apagado, nunca**, e a tela precisa dizer isso porque o
          usuário vai supor que "desativar" e "apagar" são sinônimos. Uma linha
          apagada viraria um identificador sem nome em `cardapio.criado_por` e
          na trilha de auditoria, e os cardápios de março ficariam órfãos. */}
      <p className="cant-nota">
        Nada é apagado aqui. Desativar mantém a linha e o nome — uma conta removida viraria um
        identificador sem dono na autoria dos cardápios e na trilha de auditoria.
      </p>
    </div>
  );
}

/** Desativar a cantina inteira — o raio de explosão maior dos dois. */
function DesativarCantina({ cantina }: { cantina: CantinaAdmin }) {
  const editar = useEditarCantina();
  return (
    <button
      type="button"
      // O único vermelho desta parte do produto, e ele obedece a R4: falha e
      // ação de consequência operacional. Não é semáforo — nada aqui está
      // "ruim"; é o botão que tranca um estabelecimento inteiro.
      className={`cant-tecla${cantina.ativo ? ' cant-tecla--risco' : ''}`}
      disabled={editar.isPending}
      onClick={() => editar.mutate({ id: cantina.id, corpo: { ativo: !cantina.ativo } })}
    >
      {cantina.ativo ? 'Desativar a cantina' : 'Reativar a cantina'}
    </button>
  );
}

/**
 * Criar a cantina, ou mudar o nome e a REGRA de prazo dela.
 *
 * A regra é o que pré-preenche `pedidos_ate` em cada cardápio novo. Ela existe
 * para a cantina não redigitar um instante por dia útil, 200 vezes por ano — e
 * o texto do diálogo diz isso, porque uma regra que ninguém sabe que existe é
 * uma regra que ninguém ajusta.
 */
function DialogoCantina({
  cantina, onFechar,
}: { cantina: CantinaAdmin | null; onFechar: () => void }) {
  const [nome, setNome] = useState(cantina?.nome ?? '');
  const [dias, setDias] = useState(cantina?.prazo_padrao_dias_antes ?? 1);
  const [hora, setHora] = useState((cantina?.prazo_padrao_hora ?? '20:00').slice(0, 5));
  const criar = useCriarCantina();
  const editar = useEditarCantina();
  const emCurso = criar.isPending || editar.isPending;
  const erro = criar.error ?? editar.error;

  function salvar() {
    const corpo = {
      nome: nome.trim(),
      prazo_padrao_dias_antes: dias,
      prazo_padrao_hora: `${hora}:00`,
    };
    if (cantina) editar.mutate({ id: cantina.id, corpo }, { onSuccess: onFechar });
    // A criação manda só o nome e a regra; `POST /administracao/cantinas` já
    // aplica os defaults da 0047 para o que faltar.
    else criar.mutate(corpo, { onSuccess: onFechar });
  }

  return (
    <Dialogo
      titulo={cantina ? `Editar ${cantina.nome}` : 'Nova cantina'}
      subtitulo="O estabelecimento. As contas de acesso são criadas depois, dentro dele."
      onFechar={onFechar}
      rodape={(
        <>
          <button type="button" className="btn btn--fino" onClick={onFechar}>Cancelar</button>
          <button type="button" className="btn" disabled={!nome.trim() || emCurso} onClick={salvar}>
            {emCurso ? 'Salvando…' : cantina ? 'Salvar' : 'Criar'}
          </button>
        </>
      )}
    >
      <Campo label="Nome">
        <input
          className="input"
          value={nome}
          placeholder="Cantina do Ari"
          onChange={(e) => setNome(e.target.value)}
        />
      </Campo>

      <Campo label="O pedido fecha, por padrão">
        <div className="cant-lote__par">
          <select
            className="input"
            value={dias}
            onChange={(e) => setDias(Number(e.target.value))}
          >
            <option value={0}>no próprio dia</option>
            <option value={1}>1 dia antes</option>
            <option value={2}>2 dias antes</option>
            <option value={3}>3 dias antes</option>
          </select>
          <input
            className="input"
            type="time"
            value={hora}
            onChange={(e) => setHora(e.target.value)}
          />
        </div>
      </Campo>
      <p className="cant-sub">
        É só o valor que já vem preenchido em cada cardápio novo — a cantina pode trocar dia a
        dia no editor. Depois do prazo, ninguém acrescenta pedido: nem o aluno, nem a cantina.
      </p>

      {erro && <p className="cant-erro" role="alert">{(erro as Error).message}</p>}
    </Dialogo>
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
      subtitulo="A senha é sorteada e mostrada uma única vez, na tela atrás deste diálogo."
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

// ─── Leituras ─────────────────────────────────────────────────────────────

/** "lançou há 2 horas" · "sem entrar há 40 dias" · "nunca entrou". */
function ultimoAcesso(conta: ContaDeCantina): string {
  if (!conta.ultimo_login_em) return 'nunca entrou';
  const quando = new Date(conta.ultimo_login_em).getTime();
  if (Number.isNaN(quando)) return 'nunca entrou';
  const horas = Math.floor((Date.now() - quando) / 3_600_000);
  if (horas < 1) return 'entrou agora há pouco';
  if (horas < 24) return `entrou há ${horas}h`;
  const dias = Math.floor(horas / 24);
  return `sem entrar há ${dias} dia${dias === 1 ? '' : 's'}`;
}

/** "Ana Beatriz Correia" → "AC". */
function iniciais(nome: string): string {
  const partes = (nome || '?').trim().split(/\s+/).filter(Boolean);
  if (!partes.length) return '?';
  const letras = [partes[0], partes.length > 1 ? partes[partes.length - 1] : ''];
  return letras.map((p) => p.charAt(0).toUpperCase()).join('');
}
