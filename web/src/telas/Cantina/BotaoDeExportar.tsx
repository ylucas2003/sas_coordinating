import { useMemo, useState } from 'react';

import { Dialogo } from '../../componentes/dialogos/Dialogo';
import { gradeDoMes, isoDoDia } from '../../dominio/cantina';
import {
  type Atalho, clicarNoDia, type ModoDePeriodo, type Periodo, periodoDoAtalho,
  problemaDoPeriodo, ROTULO_DO_ATALHO, rotuloDoPeriodo, type Selecao,
} from '../../dominio/periodo';
import { nomeDoMes } from './GradeDeCardapios';

/**
 * O "Exportar" de toda tela de cantina (decisão de 14/09).
 *
 * ⚠️ **O arquivo se chama `BotaoDeExportar`, e não `Exportar`, por causa do
 * sistema de arquivos.** Ao lado dele mora `exportar.ts` (os geradores de CSV e
 * PDF), e no macOS — onde o projeto é desenvolvido — maiúscula e minúscula são
 * o MESMO nome: `import './Exportar'` resolvia para `exportar.ts`, e o
 * TypeScript acusava que o componente não existia. No Linux do servidor os dois
 * conviveriam, o que só tornaria o defeito mais difícil de reproduzir.
 *
 * ⚠️ **Um botão COM RÓTULO, no canto superior direito, dentro da tela.** Antes
 * havia uma seta solta no card do hub, e o usuário tinha de adivinhar que
 * aquilo baixava alguma coisa — e, depois de entrar na tela, não havia botão
 * nenhum. As setas saíram; este componente é o único lugar de exportar.
 *
 * Ele abre um painel com as duas perguntas que toda exportação tem: **em que
 * formato** e **de quando**. A segunda muda de forma conforme a primeira —
 * `ModoDePeriodo` em `dominio/periodo.ts`:
 *
 *   nenhum     lista sem data (alunos com direito, contas): não há calendário;
 *   dia        formato de um dia só (a imagem do cardápio, a folha do balcão);
 *   intervalo  planilha e relatório, com atalhos e dois cliques no calendário.
 *
 * ⚠️ `executar` roda DENTRO do clique em "Exportar". Os PDFs abrem janela com
 * `window.open`, e o navegador só permite isso em resposta direta a um gesto:
 * quem precisar buscar dado antes tem de abrir a janela primeiro.
 */

export interface SaidaDeExportacao {
  chave: string;
  rotulo: string;
  descricao: string;
  periodo: ModoDePeriodo;
  executar: (periodo: Periodo) => Promise<void> | void;
  /** Motivo de não estar disponível agora. Aparece por extenso, nunca cinza mudo. */
  indisponivel?: string;
}

const ATALHOS: Atalho[] = ['hoje', 'semana', 'mes', 'mesPassado'];

export function Exportar({
  saidas, oQue, periodoInicial,
}: {
  saidas: SaidaDeExportacao[];
  /** "os pedidos", "o cardápio" — completa o título do painel. */
  oQue: string;
  /** O período que a TELA está mostrando — é por onde o painel começa. */
  periodoInicial?: Periodo;
}) {
  const [aberto, setAberto] = useState(false);

  return (
    <>
      <button type="button" className="cant-exportar-botao" onClick={() => setAberto(true)}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
          strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M12 4v11" />
          <path d="M7.5 10.5 12 15l4.5-4.5" />
          <path d="M5 19h14" />
        </svg>
        Exportar
      </button>
      {aberto && (
        <PainelDeExportacao
          saidas={saidas}
          oQue={oQue}
          periodoInicial={periodoInicial}
          onFechar={() => setAberto(false)}
        />
      )}
    </>
  );
}

function PainelDeExportacao({
  saidas, oQue, periodoInicial, onFechar,
}: {
  saidas: SaidaDeExportacao[];
  oQue: string;
  periodoInicial?: Periodo;
  onFechar: () => void;
}) {
  const disponiveis = saidas.filter((s) => !s.indisponivel);
  const [chave, setChave] = useState(disponiveis[0]?.chave ?? saidas[0]?.chave);
  const saida = saidas.find((s) => s.chave === chave) ?? saidas[0];
  const modo = saida?.periodo ?? 'nenhum';

  const inicial = periodoInicial ?? periodoDoAtalho('hoje');
  const [selecao, setSelecao] = useState<Selecao>({ ...inicial, esperandoFim: false });
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  // Formato de UM dia com um intervalo escolhido: fica o primeiro dia. Recusar
  // em silêncio obrigaria a pessoa a descobrir sozinha que tem de desmarcar.
  // Exceção: enquanto a pessoa não tocou no calendário, o período é o da TELA
  // (o mês inteiro), e o "primeiro dia" seria o dia 1 — quem abre a imagem do
  // cardápio quer o de hoje.
  const hoje = isoDoDia(new Date());
  const naoTocou = selecao.de === inicial.de && selecao.ate === inicial.ate;
  const dia = naoTocou && hoje >= inicial.de && hoje <= inicial.ate ? hoje : selecao.de;
  const periodo: Periodo = modo === 'dia'
    ? { de: dia, ate: dia }
    : { de: selecao.de, ate: selecao.ate };
  const problema = selecao.esperandoFim ? 'Escolha o último dia.' : problemaDoPeriodo(periodo, modo);

  async function exportar() {
    if (!saida || problema) return;
    setOcupado(true);
    setErro(null);
    try {
      await saida.executar(periodo);
      onFechar();
    } catch (e) {
      setErro((e as Error).message || 'Não deu para gerar o arquivo.');
    } finally {
      setOcupado(false);
    }
  }

  return (
    <Dialogo
      largo
      titulo={`Exportar ${oQue}`}
      subtitulo={modo === 'nenhum' ? 'Escolha o formato.' : 'Escolha o formato e o período.'}
      onFechar={onFechar}
      rodape={(
        <>
          <button type="button" className="btn btn--fino" onClick={onFechar}>Cancelar</button>
          <button
            type="button"
            className="btn btn--primary"
            disabled={!saida || !!saida.indisponivel || !!problema || ocupado}
            onClick={exportar}
          >
            {ocupado ? 'Gerando…' : 'Exportar'}
          </button>
        </>
      )}
    >
      <div className={`cant-exportacao${modo === 'nenhum' ? '' : ' cant-exportacao--com-periodo'}`}>
        <fieldset className="cant-exportacao__formatos">
          <legend className="cant-exportacao__legenda">Formato</legend>
          {saidas.map((s) => (
            <label
              key={s.chave}
              className={`cant-formato${s.chave === chave ? ' cant-formato--ativo' : ''}${s.indisponivel ? ' cant-formato--inerte' : ''}`}
            >
              <input
                type="radio"
                name="formato-de-exportacao"
                checked={s.chave === chave}
                disabled={!!s.indisponivel}
                onChange={() => setChave(s.chave)}
              />
              <span>
                <span className="cant-formato__rotulo">{s.rotulo}</span>
                <span className="cant-formato__descricao">{s.indisponivel ?? s.descricao}</span>
              </span>
            </label>
          ))}
        </fieldset>

        {modo !== 'nenhum' && (
          <div className="cant-exportacao__periodo">
            <span className="cant-exportacao__legenda">
              {modo === 'dia' ? 'Dia' : 'Período'}
            </span>
            {modo === 'intervalo' && (
              <div className="cant-exportacao__atalhos">
                {ATALHOS.map((a) => (
                  <button
                    key={a}
                    type="button"
                    className="pill"
                    onClick={() => setSelecao({ ...periodoDoAtalho(a), esperandoFim: false })}
                  >
                    {ROTULO_DO_ATALHO[a]}
                  </button>
                ))}
              </div>
            )}
            <CalendarioDePeriodo
              selecao={modo === 'dia' ? { ...selecao, de: dia, ate: dia } : selecao}
              onClicar={(iso) => setSelecao((atual) => clicarNoDia(atual, iso, modo))}
            />
            <p className={`cant-exportacao__escolhido${problema ? ' cant-exportacao__escolhido--falta' : ''}`}>
              {problema ?? rotuloDoPeriodo(periodo)}
            </p>
          </div>
        )}
      </div>

      {erro && <p className="cant-erro" role="alert">{erro}</p>}
    </Dialogo>
  );
}

const DIAS_CURTOS = ['D', 'S', 'T', 'Q', 'Q', 'S', 'S'];

/**
 * O calendário do painel — no desenho da plataforma, sem biblioteca.
 *
 * O `<input type="date">` do navegador não serve aqui por dois motivos: ele
 * não escolhe INTERVALO, e cada navegador o desenha de um jeito — no iOS ele
 * vira roleta. A grade reaproveita `gradeDoMes`, a mesma do calendário de
 * cardápios, e por isso as duas nunca discordam de em que dia da semana cai o
 * dia 1.
 */
function CalendarioDePeriodo({
  selecao, onClicar,
}: {
  selecao: Selecao;
  onClicar: (iso: string) => void;
}) {
  const [vista, setVista] = useState(() => {
    const [ano, mes] = selecao.ate.split('-').map(Number);
    return { ano, mes: mes - 1 };
  });
  const casas = useMemo(() => gradeDoMes(vista.ano, vista.mes), [vista]);
  const hoje = isoDoDia(new Date());

  function andar(passo: number) {
    setVista((v) => {
      const d = new Date(v.ano, v.mes + passo, 1);
      return { ano: d.getFullYear(), mes: d.getMonth() };
    });
  }

  return (
    <div className="cant-cal">
      <div className="cant-cal__topo">
        <button type="button" className="cant-cal__seta" onClick={() => andar(-1)} aria-label="Mês anterior">‹</button>
        <span className="cant-cal__mes">{nomeDoMes(vista.mes)} de {vista.ano}</span>
        <button type="button" className="cant-cal__seta" onClick={() => andar(1)} aria-label="Próximo mês">›</button>
      </div>
      {/* Sem role="grid": uma grade ARIA promete navegação por setas entre
          células, e isto não a implementa. Os dias são botões com
          aria-pressed, que o leitor de tela anuncia do jeito certo. */}
      <div className="cant-cal__grade">
        {DIAS_CURTOS.map((d, i) => (
          // biome-ignore lint/suspicious/noArrayIndexKey: as letras se repetem (S, Q); a posição É a identidade.
          <span key={`cab-${i}`} className="cant-cal__semana" aria-hidden="true">{d}</span>
        ))}
        {casas.map((iso, i) => {
          if (!iso) {
            // biome-ignore lint/suspicious/noArrayIndexKey: casa vazia antes do dia 1; não tem outra identidade.
            return <span key={`vazio-${i}`} className="cant-cal__vazio" />;
          }
          const dentro = iso >= selecao.de && iso <= selecao.ate;
          const ponta = iso === selecao.de || iso === selecao.ate;
          return (
            <button
              key={iso}
              type="button"
              className={[
                'cant-cal__dia',
                dentro ? 'cant-cal__dia--dentro' : '',
                ponta ? 'cant-cal__dia--ponta' : '',
                iso === hoje ? 'cant-cal__dia--hoje' : '',
              ].filter(Boolean).join(' ')}
              aria-pressed={dentro}
              onClick={() => onClicar(iso)}
            >
              {Number(iso.slice(8))}
            </button>
          );
        })}
      </div>
    </div>
  );
}
