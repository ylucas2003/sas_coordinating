import { useState } from 'react';
import { NavLink, Navigate, Route, Routes } from 'react-router-dom';

import { Avatar } from '../../componentes/ui/Avatar';
import { useLiga, useProximoSimulado, useSequencia, useXp } from '../../dados/aluno';
import * as sessao from '../../servicos/sessao';
import { Estudar } from './Estudar';
import { EstudarBanco } from './EstudarBanco';
import { EstudarEstatisticas } from './EstudarEstatisticas';
import { EstudarProgresso } from './EstudarProgresso';
import { EstudarLista } from './EstudarLista';
import { EstudarListas } from './EstudarListas';
import { Hoje } from './Hoje';
import { Jornada } from './Jornada';
import { LigaTela } from './Liga';
import { Provas } from './Provas';
import { ProvaFicha } from './ProvaFicha';
import { ExtratoXpTela } from './ExtratoXp';
import { ContagemRegressiva } from './pecas/ContagemRegressiva';
import { Corrente } from './pecas/Corrente';
import { Chama, FichaXp, Icone } from './pecas/Icone';
import type { NomeIcone } from './pecas/Icone';
import { Folha } from './pecas/Folha';
import { TarjaFonte } from './pecas/TarjaFonte';
import { fmtInteiro } from './pecas/formato';
import { useTema } from './pecas/tema';
import { FabTioLeo } from './TioLeo/FabTioLeo';

// O casco da área do aluno.
//
// A barra de navegação tem QUATRO destinos, e a lista sai do que o aluno vem
// fazer, não do modelo de dados (docs/24 §7.1):
//
//   Hoje     o que eu faço agora
//   Estudar  o que eu preciso treinar
//   Provas   como eu fui
//   Jornada  estou evoluindo
//
// O Banco deixou de ser aba e virou o MOTOR de Estudar — "banco de questões" é
// vocabulário interno, não do aluno.
//
// ⚠️ `/treino/:origem` e `/questao/:id` NÃO estão aqui. São rotas de topo, em
// tela cheia, sem barra inferior e sem o Tio Léo — quem as monta é o `App.tsx`.

const DESTINOS: Array<{ para: string; rotulo: string; icone: NomeIcone; fim: boolean }> = [
  { para: '/', rotulo: 'Hoje', icone: 'casa', fim: true },
  { para: '/estudar', rotulo: 'Estudar', icone: 'livro', fim: false },
  { para: '/provas', rotulo: 'Provas', icone: 'prancheta', fim: false },
  { para: '/jornada', rotulo: 'Jornada', icone: 'bandeira', fim: false },
];

function sair() {
  sessao.encerrar();
  window.location.replace('/login');
}

export function CascoAluno() {
  const nome = sessao.nome();
  const primeiro = nome.split(' ')[0] || nome;
  const [conta, setConta] = useState<'fechada' | 'menu'>('fechada');

  const { data: sequencia } = useSequencia();
  const { data: xp } = useXp();

  return (
    <div className="alu-shell">
      {/* A barra de topo do celular tem TRÊS coisas, e é a lista literal do
          desenho (docs/24 §7): sequência, XP e avatar. A saudação NÃO mora
          aqui — quem cumprimenta é o `<h1>` da própria tela, e repetir o nome
          aqui gastava a primeira dobra, que é do herói. O selo à esquerda é só
          a âncora de marca, que no desktop é o topo do rail. */}
      <header className="alu-topo">
        <span className="alu-marca" role="img" aria-label="Colégio Ari de Sá" />

        <span className="alu-topo__indicadores">
          <span className="alu-topo__indicador alu-topo__indicador--sequencia">
            <Chama tamanho={19} />
            {sequencia?.simulados ?? 0}
            <TarjaFonte chave="sequencia" ponto />
          </span>

          <span className="alu-topo__indicador alu-topo__indicador--xp">
            <FichaXp tamanho={21} />
            {fmtInteiro(xp?.total ?? 0)}
            <TarjaFonte chave="xp" ponto />
          </span>
        </span>

        <button type="button" className="alu-topo__conta" onClick={() => setConta('menu')} aria-label="Minha conta">
          <Avatar tipo="aluno" proprio nome={nome} className="alu-avatar" tamanho={34} />
        </button>
      </header>

      <div className="alu-corpo">
        <nav className="alu-rail" aria-label="Seções">
          <div className="alu-rail__topo">
            <span className="alu-marca alu-marca--grande" role="img" aria-label="Colégio Ari de Sá" />
            <span className="alu-rail__marca-sub">Área do estudante</span>
          </div>

          <div className="alu-rail__nav">
            {DESTINOS.map((d) => (
              <NavLink
                key={d.para}
                to={d.para}
                end={d.fim}
                className={({ isActive }) => `alu-rail__item${isActive ? ' is-ativo' : ''}`}
              >
                <Icone nome={d.icone} tamanho={20} />
                {d.rotulo}
              </NavLink>
            ))}
          </div>

          <div className="alu-rail__rodape">
            <Avatar tipo="aluno" proprio nome={nome} className="alu-avatar" tamanho={34} />
            <span className="alu-rail__nome">{primeiro || 'Aluno'}</span>
            <button
              type="button"
              className="alu-folha__botao-icone"
              onClick={() => setConta('menu')}
              aria-label="Minha conta"
            >
              <Icone nome="engrenagem" tamanho={18} />
            </button>
          </div>
        </nav>

        <main className="alu-centro">
          <Routes>
            <Route path="/" element={<Hoje nome={primeiro} />} />
            <Route path="/estudar" element={<Estudar />} />
            <Route path="/estudar/banco" element={<EstudarBanco />} />
            <Route path="/estudar/estatisticas" element={<EstudarEstatisticas />} />
            <Route path="/estudar/progresso" element={<EstudarProgresso />} />
            {/* A antiga "O que mais cai" rodava em mock e mostrava "você acerta
                X%" — a métrica que o desenho de 02/09 tirou de Estatísticas. A
                tela saiu; o caminho fica, porque pode estar em link salvo. */}
            <Route
              path="/estudar/assuntos"
              element={<Navigate to="/estudar/estatisticas" replace />}
            />
            <Route path="/estudar/listas" element={<EstudarListas />} />
            <Route path="/estudar/listas/:id" element={<EstudarLista />} />
            <Route path="/provas" element={<Provas />} />
            <Route path="/provas/:id" element={<ProvaFicha />} />
            <Route path="/provas/:id/extrato" element={<ExtratoXpTela />} />
            <Route path="/jornada" element={<Jornada />} />
            <Route path="/liga" element={<LigaTela />} />
            {/* Os caminhos antigos do casco do aluno seguem valendo: estão em
                link salvo e no e-mail de lembrete da Sprint 1. */}
            <Route path="/simulados" element={<Navigate to="/provas" replace />} />
            <Route path="/simulados/:id" element={<RedirecionaSimulado />} />
            <Route path="/banco/*" element={<Navigate to="/estudar" replace />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>

        <ColunaLateral />
      </div>

      <nav className="alu-barra" aria-label="Seções">
        {DESTINOS.map((d) => (
          <NavLink
            key={d.para}
            to={d.para}
            end={d.fim}
            className={({ isActive }) => `alu-barra__item${isActive ? ' is-ativo' : ''}`}
          >
            {({ isActive }) => (
              <>
                <Icone
                  nome={d.icone}
                  tamanho={22}
                  cor={isActive ? 'var(--alu-dado)' : 'currentColor'}
                />
                {d.rotulo}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      <FabTioLeo />

      {conta === 'menu' && <FolhaDaConta onFechar={() => setConta('fechada')} />}
    </div>
  );
}

/** `/simulados/:id` do casco antigo agora é `/provas/:id`. */
function RedirecionaSimulado() {
  const id = window.location.pathname.split('/').pop();
  return <Navigate to={`/provas/${id}`} replace />;
}

/**
 * A coluna direita do desktop: sequência, XP, contagem regressiva e liga.
 *
 * Some no celular por CSS, e não por JavaScript: os mesmos números já estão no
 * topo e nos blocos da Hoje, e montar dois componentes para escolher um em
 * runtime custaria uma consulta a mais sem nada em troca.
 */
function ColunaLateral() {
  const { data: sequencia } = useSequencia();
  const { data: xp } = useXp();
  const { data: proximo } = useProximoSimulado();
  const { data: liga } = useLiga();

  return (
    <aside className="alu-lateral" aria-label="Seu progresso">
      <div className="alu-widget">
        <TarjaFonte chave="sequencia" />
        <div className="alu-widget__linha">
          <Chama tamanho={30} />
          <span className="alu-magnitude alu-widget__numero">{sequencia?.simulados ?? 0}</span>
        </div>
        <span className="alu-widget__rotulo alu-widget__rotulo--sequencia">Sequência</span>
        {sequencia && <Corrente elos={sequencia.corrente} tamanho={22} />}
        <p className="alu-widget__sub">simulados sem faltar</p>
      </div>

      <div className="alu-widget">
        <TarjaFonte chave="xp" />
        <div className="alu-widget__linha">
          <FichaXp tamanho={30} />
          <span className="alu-magnitude alu-widget__numero">{fmtInteiro(xp?.total ?? 0)}</span>
        </div>
        <span className="alu-widget__rotulo alu-widget__rotulo--xp">XP</span>
        {xp && <p className="alu-widget__sub">+{fmtInteiro(xp.ciclo)} neste ciclo</p>}
      </div>

      <div className="alu-widget">
        <TarjaFonte chave="proximoSimulado" />
        <span className="alu-olho">Próximo simulado</span>
        <ContagemRegressiva proximo={proximo ?? null} compacta />
      </div>

      {liga && (
        <div className="alu-widget">
          <TarjaFonte chave="liga" />
          <span className="alu-olho">{liga.nome}</span>
          <p className="alu-widget__sub">
            {liga.posicoes.find((p) => p.euMesmo)?.posicao ?? '—'}º de {liga.participantes}
          </p>
          <NavLink className="alu-tecla alu-tecla--valor alu-tecla--pequena" to="/liga">
            Ver
          </NavLink>
        </div>
      )}
    </aside>
  );
}

// ─── Conta ───────────────────────────────────────────────────────────────

function FolhaDaConta({ onFechar }: { onFechar: () => void }) {
  const { tema, trocar } = useTema();

  return (
    <Folha aberta titulo="Minha conta" altura="espiada" onFechar={onFechar}>
      {/* DOIS temas, e só dois (docs/24 §7.2).

          `<fieldset>` com rádios de VERDADE, e não dois botões com
          `role="radio"`: o rádio nativo já traz a navegação por seta, o
          anúncio "1 de 2" e o agrupamento pelo `<legend>`, que a versão com
          ARIA teria de reimplementar à mão — e implementar mal. O input fica
          escondido só visualmente; quem desenha o segmento é o `<label>`. */}
      <fieldset className="alu-conta__campo alu-tema-campo">
        <legend className="alu-conta__rotulo">Tema</legend>
        <div className="alu-tema">
          {(
            [
              { valor: 'dia', rotulo: 'Dia', icone: 'sol' },
              { valor: 'noite', rotulo: 'Noite', icone: 'lua' },
            ] as const
          ).map((op) => (
            <label
              key={op.valor}
              className={`alu-tema__opcao${tema === op.valor ? ' is-ativa' : ''}`}
            >
              <input
                className="alu-so-leitor"
                type="radio"
                name="alu-tema"
                value={op.valor}
                checked={tema === op.valor}
                onChange={() => trocar(op.valor)}
              />
              <Icone nome={op.icone} tamanho={18} />
              {op.rotulo}
            </label>
          ))}
        </div>
      </fieldset>

      {/* Não há "Trocar senha" aqui desde 04/09 (docs/35 §11.5): o aluno entra
          só pelo Canvas, e `POST /me/senha` saiu junto. A folha continuava
          aceitando os três campos e respondia "Senha atual incorreta" para
          todo aluno que nunca teve hash — e, para os poucos com hash antigo,
          era pior: dizia "Senha alterada." e gravava uma credencial que não
          autentica em lugar nenhum. A senha que dá acesso é a do Canvas, e o SAS
          não a lê nem a escreve. */}
      <button type="button" className="alu-conta__linha" onClick={sair}>
        <Icone nome="sair" tamanho={18} />
        Sair da conta
      </button>
    </Folha>
  );
}
