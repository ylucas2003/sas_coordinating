import { useMemo, useState } from 'react';

import { CabecaDeCampo } from '../../componentes/ui/Campo';
import { useCustosDaCantina } from '../../hooks/cantina';
import { useTituloDaTela } from '../../componentes/layout/migalhas';
import { enderecoDoRelatorio } from '../../servicos/api';
import { janelaDoMes, NavegadorDeMes, nomeDoMes } from './GradeDeCardapios';
import { SeletorDeCantina, useCantinaSelecionada } from './SeletorDeCantina';
import type { LinhaDeCusto } from '../../tipos/cantina';

/**
 * Quanto a cantina custou — o quarto card do hub (docs/40 §12.11.4).
 *
 * ⚠️ **Isto é leitura, não cobrança.** Não há fatura, "quem pagou" nem
 * conciliação: a fronteira do docs/38 §8.1.5 segue de pé. O recorte por ALUNO é
 * o que mais se aproxima dela — e no dia em que alguém pedir "manda a conta do
 * aluno", a resposta deixa de ser um relatório e vira outro produto.
 *
 * **Quem vê:** qualquer coordenador. Cadastrar o valor continua sendo do
 * administrador, em `/cantina/acesso` — ver quanto custou não é o mesmo que
 * decidir quanto custa, e é a mesma divisão de `/cantina/direitos`.
 *
 * ⚠️ **Sem biblioteca de gráfico**, como todo o resto do produto: não há uma no
 * `package.json`, e acrescentá-la aqui pesaria no bundle que a §12.1.4 acabou
 * de cortar. Nada de CDN (CLAUDE.md, armadilha 7). As barras são `div` com
 * largura em porcentagem — mais leve que SVG para barra horizontal, e o texto
 * dentro delas continua sendo texto, que o leitor de tela lê e o Ctrl+F acha.
 */

type Recorte = 'porDia' | 'porTurma' | 'porAluno' | 'porCantina';

const RECORTES: Array<{ valor: Recorte; rotulo: string }> = [
  { valor: 'porDia', rotulo: 'Por dia' },
  { valor: 'porTurma', rotulo: 'Por turma' },
  { valor: 'porAluno', rotulo: 'Por aluno' },
  { valor: 'porCantina', rotulo: 'Por cantina' },
];

export function CustosDaCantina() {
  useTituloDaTela('Custos');
  const hoje = useMemo(() => new Date(), []);
  const [mes, setMes] = useState(() => ({ ano: hoje.getFullYear(), mes: hoje.getMonth() }));
  const [recorte, setRecorte] = useState<Recorte>('porDia');
  const cantina = useCantinaSelecionada();

  const [de, ate] = useMemo(() => janelaDoMes(mes.ano, mes.mes), [mes]);
  const { data, isLoading, isError } = useCustosDaCantina(de, ate, cantina);

  const linhas = data?.[recorte] ?? [];

  return (
    <div className="tela">
      <CabecaDeCampo
        titulo="Quanto a cantina custou"
        para="/cantina"
        destino="a cantina"
        acoes={
          <a
            className="btn btn--fino"
            href={enderecoDoRelatorio(de, ate, cantina)}
            // ⚠️ `<a download>` e não um `fetch`: o arquivo já vem pronto do
            // servidor, com nome no `Content-Disposition`. Passá-lo por
            // JavaScript só para recolocá-lo num blob gastaria memória e
            // perderia o nome.
            download
          >
            Baixar planilha (.xlsx)
          </a>
        }
      />

      <div className="cant-escolha-do-dia">
        <NavegadorDeMes
          ano={mes.ano}
          mes={mes.mes}
          // `onAndar` recebe o PASSO, não a data: é o contrato do calendário,
          // e a normalização de dezembro→janeiro fica num lugar só.
          onAndar={(passo) => setMes((atual) => {
            const d = new Date(atual.ano, atual.mes + passo, 1);
            return { ano: d.getFullYear(), mes: d.getMonth() };
          })}
        />
        <SeletorDeCantina />
      </div>

      {isLoading && <p className="cant-vazio">Carregando…</p>}
      {isError && <p className="cant-vazio">Não deu para ler os custos agora.</p>}

      {data && (
        <>
          <p className="cant-intro">
            {nomeDoMes(mes.mes)} · <b>{moeda(data.total)}</b> · {data.refeicoes}{' '}
            {data.refeicoes === 1 ? 'refeição' : 'refeições'}
          </p>

          {/* ⚠️ O buraco vira PERGUNTA, e não zero silencioso. Um relatório que
              soma zero por falta de preço faz a coordenação fechar a conta
              errada e nunca saber (docs/40 §12.11.2). */}
          {data.semValor > 0 && (
            <p className="cant-aviso">
              {data.semValor} {data.semValor === 1 ? 'refeição não tem' : 'refeições não têm'}{' '}
              valor registrado, e {data.semValor === 1 ? 'ela não entra' : 'elas não entram'} na
              soma. O preço de cada refeição é cadastrado em <b>Administrar cantinas</b>.
            </p>
          )}

          <div className="cant-abas">
            {RECORTES.map((r) => (
              <button
                key={r.valor}
                type="button"
                className={`cant-aba${r.valor === recorte ? ' cant-aba--ativa' : ''}`}
                onClick={() => setRecorte(r.valor)}
              >
                {r.rotulo}
              </button>
            ))}
          </div>

          <Barras linhas={linhas} />

          <div className="cant-grade-rolagem">
            <table className="data-table">
              <thead>
                <tr>
                  <th>{RECORTES.find((r) => r.valor === recorte)?.rotulo.replace('Por ', '')}</th>
                  <th>Refeições</th>
                  <th>Total</th>
                </tr>
              </thead>
              <tbody>
                {linhas.map((linha) => (
                  <tr key={linha.rotulo}>
                    <td data-rotulo="Recorte" data-titulo>{linha.rotulo}</td>
                    <td data-rotulo="Refeições">{linha.refeicoes}</td>
                    <td data-rotulo="Total">{moeda(linha.total)}</td>
                  </tr>
                ))}
                {!linhas.length && (
                  <tr><td colSpan={3} className="cant-vazio">Nada neste recorte.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

/**
 * O gráfico de barras — `div` com largura em porcentagem, sem SVG e sem
 * biblioteca.
 *
 * ⚠️ Sem semáforo e sem escala de cor: é o mesmo papel de dado em todas as
 * barras, e a diferença que interessa é o COMPRIMENTO (docs/03 histórico,
 * docs/37). Pintar a maior de vermelho diria que gastar mais é errado, o que a
 * tela não sabe.
 */
function Barras({ linhas }: { linhas: LinhaDeCusto[] }) {
  // Um teto de barras: acima disso o desenho vira listra e a tabela abaixo
  // responde melhor. Não é paginação — é reconhecer que "por aluno" com 900
  // linhas não é pergunta de gráfico.
  const TETO = 24;
  const mostradas = linhas.slice(0, TETO);
  const maior = Math.max(...mostradas.map((l) => l.total), 0);

  if (!mostradas.length || maior <= 0) return null;

  return (
    <div className="cant-barras" role="img" aria-label="Custo por recorte">
      {mostradas.map((linha) => (
        <div className="cant-barras__linha" key={linha.rotulo}>
          <span className="cant-barras__rotulo">{linha.rotulo}</span>
          <span className="cant-barras__trilho">
            <span
              className="cant-barras__barra"
              style={{ width: `${Math.round((linha.total / maior) * 100)}%` }}
            />
          </span>
          <span className="cant-barras__valor">{moeda(linha.total)}</span>
        </div>
      ))}
      {linhas.length > TETO && (
        <p className="cant-sub">
          As {TETO} maiores. A tabela abaixo tem as {linhas.length}.
        </p>
      )}
    </div>
  );
}

function moeda(valor: number): string {
  return valor.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}
