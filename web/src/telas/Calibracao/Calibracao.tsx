import { useEffect, useState } from 'react';

import { CabecaDeCampo } from '../../componentes/ui/Campo';
import { useGirarBotaoDeImportancia, useParametroDeImportancia } from '../../hooks/banco';
import { useTituloDaTela } from '../../componentes/layout/migalhas';

/**
 * O botão "quanto o passado ainda conta" (docs/34 §5 · D2).
 *
 * `H` é a meia-vida do peso por recência: com `H = 5`, a prova de cinco anos
 * atrás vale metade da do ano passado. Mexer nele REORDENA o ranking de
 * assuntos — e portanto muda o que o sistema diz para o aluno estudar primeiro.
 *
 * Três coisas que esta tela é obrigada a fazer, e as três vêm da decisão de
 * pôr o parâmetro no banco em vez de no código:
 *
 *  1. **Mostrar o efeito antes de gravar.** Um número abstrato ("meia-vida =
 *     3") não diz nada; "a prova de 2021 passa a valer 32% da de 2026" diz. Sem
 *     isso a coordenação gira às cegas.
 *  2. **Deixar claro que grava uma VERSÃO**, não uma edição. É a regra que o
 *     critério já segue: a anterior fica no histórico, porque sem ela ninguém
 *     consegue explicar depois por que o ranking de um mês não bate com o do
 *     outro.
 *  3. **Dizer quando o valor é o de fábrica.** `versao === null` significa que
 *     ninguém girou o botão ainda — e é diferente de "está na versão 1".
 */
export function Calibracao() {
  useTituloDaTela('Calibração');

  const { data, isLoading, isError } = useParametroDeImportancia();
  const girar = useGirarBotaoDeImportancia();

  const [meiaVida, setMeiaVida] = useState('');
  const [janela, setJanela] = useState('');

  // O formulário nasce com o que está em vigor. Depois disso é do usuário —
  // sobrescrever a cada refetch apagaria o que ele estava digitando.
  useEffect(() => {
    if (!data) return;
    setMeiaVida(String(data.meiaVidaAnos));
    setJanela(String(data.janelaTendenciaAnos));
  }, [data]);

  if (isLoading) return <div className="tela"><CabecaDeCampo titulo="Quanto vale cada assunto" para="/administracao" destino="Administração" /><p>Carregando…</p></div>;

  // ⚠️ Falha NUNCA vira tela vazia: sem o parâmetro, o índice continua saindo
  // com o valor de fábrica (o servidor garante isso), e é isso que a mensagem
  // precisa dizer — senão parece que o ranking parou.
  if (isError || !data) {
    return (
      <div className="tela">
        <CabecaDeCampo titulo="Quanto vale cada assunto" para="/administracao" destino="Administração" />
        <div className="card">
          <h1 className="tela-titulo">Calibração do índice de importância</h1>
          <p className="empty-state">
            Não consegui ler a calibração agora. O ranking de assuntos continua
            funcionando com o valor original — o que está indisponível é só a
            edição.
          </p>
        </div>
      </div>
    );
  }

  const H = Number(meiaVida);
  const valido =
    Number.isFinite(H) && H > 0 && H <= data.meiaVidaMaxima &&
    Number.isFinite(Number(janela)) && Number(janela) >= 1;
  const mudou = H !== data.meiaVidaAnos || Number(janela) !== data.janelaTendenciaAnos;

  return (
    <div className="tela">
      <CabecaDeCampo titulo="Quanto vale cada assunto" para="/administracao" destino="Administração" />

      <div className="card">
        <div className="tela-cabecalho">
          <div>
            <h1 className="tela-titulo">Quanto o passado ainda conta</h1>
            <p className="tela-subtitulo">
          O índice de importância responde <em>“o que mais cai”</em> pesando cada
          ano do acervo: prova recente conta mais que prova antiga. A{' '}
          <strong>meia-vida</strong> é o número de anos até uma prova valer
          metade. Mexer nela reordena a lista de assuntos que o aluno vê.
            </p>
          </div>
        </div>

        <div className="calibracao__campo">
          <label htmlFor="meia-vida">Meia-vida (anos)</label>
          <input
            id="meia-vida"
            type="number"
            min={0.5}
            max={data.meiaVidaMaxima}
            step={0.5}
            value={meiaVida}
            onChange={(e) => setMeiaVida(e.target.value)}
          />
        </div>

        {/* O efeito, em números — a trava 1 do comentário acima. */}
        {valido && (
          <table className="data-table calibracao__pesos">
            <caption className="section__subtitle">
              Com meia-vida de {H} anos, comparando com a prova mais recente:
            </caption>
            <thead>
              <tr><th>Prova de</th><th>Passa a valer</th></tr>
            </thead>
            <tbody>
              {[1, 3, 5, 10, 15].map((atras) => (
                <tr key={atras}>
                  <td>{atras} {atras === 1 ? 'ano atrás' : 'anos atrás'}</td>
                  <td>{Math.round(100 * 0.5 ** (atras / H))}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        <div className="calibracao__campo">
          <label htmlFor="janela">Janela da tendência (anos)</label>
          <input
            id="janela"
            type="number"
            min={1}
            max={50}
            step={1}
            value={janela}
            onChange={(e) => setJanela(e.target.value)}
          />
          <p className="section__subtitle">
            A tendência compara a média dos últimos N anos com a dos N
            anteriores — <em>“caía em 6% até 2015, cai em 2% desde 2020”</em>.
            Ela é lida ao lado do índice, nunca dentro dele.
          </p>
        </div>

        <div className="calibracao__acoes">
          <button
            className="btn btn--primary"
            disabled={!valido || !mudou || girar.isPending}
            onClick={() => girar.mutate({ meiaVidaAnos: H, janelaTendenciaAnos: Number(janela) })}
          >
            {girar.isPending ? 'Gravando…' : 'Gravar nova versão'}
          </button>
          <span className="section__subtitle">
            {data.versao === null
              ? 'Em vigor: o valor original, definido quando o índice foi desenhado.'
              : `Em vigor: versão ${data.versao}.`}{' '}
            Gravar não apaga — cria a versão seguinte e guarda esta no histórico.
          </span>
        </div>

        {girar.isError && (
          <p className="agendar__erro">
            Não consegui gravar. O valor em vigor continua o mesmo.
          </p>
        )}
      </div>

      {/* O rastro legível. A auditoria também registra, mas ela é para
          investigação; isto é para a conversa do dia a dia: "por que o ranking
          mudou?" tem de ter resposta na mesma tela. */}
      <div className="card">
        <h2 className="tela-titulo">Histórico</h2>
        {data.historico.length === 0 ? (
          <p className="empty-state">
            Ninguém girou o botão ainda. O índice está no valor com que foi
            desenhado.
          </p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Versão</th><th>Meia-vida</th><th>Janela</th>
                <th>Quando</th><th>Quem</th><th />
              </tr>
            </thead>
            <tbody>
              {data.historico.map((v) => (
                <tr key={v.versao}>
                  <td>{v.versao}</td>
                  <td>{Number(v.meia_vida_anos)} anos</td>
                  <td>{v.janela_tendencia_anos} anos</td>
                  <td>{new Date(v.criado_em).toLocaleDateString('pt-BR')}</td>
                  <td>{v.criado_por ?? '—'}</td>
                  <td>{v.ativo ? <span className="sim-selo-ok">em vigor</span> : null}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
