import { useQuery } from '@tanstack/react-query';

import { CabecaDeCampo } from '../../componentes/ui/Campo';
import * as api from '../../servicos/api';
import { formatarDataHora, toneStatus } from '../../dominio/importacao';
import type { UploadHistorico } from '../../dominio/importacao';

// A entrada por planilha foi aposentada (docs/32 §2.4).
//
// Esta tela era o formulário de upload: XHR com barra de progresso, polling de
// `GET /uploads/{id}` e os eventos "ETAPA N/10" do pipeline. Saiu inteira, e o
// `POST /uploads` responde 410. O motivo não é a planilha ser ruim — é ela ser
// um SEGUNDO ESCRITOR sem arbitragem: `nota.pontuacao` tem a disputa resolvida
// pela `0024`, mas `nota.presente` não tem par nenhum, e quem escrevesse por
// último venceria em silêncio.
//
// A medição que decidiu: em 30/08/2026, `SELECT count(*) FROM upload` em
// produção deu **zero**. As 102.143 notas entraram todas pelo sync do Canvas.
//
// A rota `/importar` fica de pé — está em link salvo e em documento — mas agora
// explica em vez de aceitar. E o histórico continua, porque é auditoria: se um
// dia alguém tiver importado algo, a tela tem de continuar sabendo dizer.

export function Importar() {
  const historico = useQuery({
    queryKey: ['uploads'],
    queryFn: () => api.listarUploads() as Promise<UploadHistorico[]>,
  });

  return (
    <div className="tela">
      <CabecaDeCampo titulo="Importação por planilha" para="/administracao" destino="Administração" />

      <div className="tela-cabecalho">
        <div>
          <h1 className="tela-titulo">Importação de planilha</h1>
          <p className="tela-subtitulo">
            Aposentada em 03/09/2026. Quem traz nota para o SAS é o sync do Canvas.
          </p>
        </div>
      </div>

      <section className="card">
        <div className="section">
          <h2 className="section__title">Por que ela saiu</h2>
          <p className="section__subtitle">
            A planilha foi como o projeto nasceu, e a rota de upload existia desde então — mas
            nunca foi usada: em toda a vida do sistema, <b>nenhuma planilha foi importada em
            produção</b>. As mais de cem mil notas entraram pelo sync do Canvas, que roda a cada
            cinco minutos.
          </p>
          <p className="section__subtitle">
            Enquanto a porta ficava aberta, ela era um segundo caminho de escrita sobre os mesmos
            dados — e, para o campo de presença, sem regra de desempate: uma importação podia
            desfazer, sem aviso, um aluno que o coordenador tinha marcado como ausente. Fechar a
            porta resolve isso melhor do que arbitrar quem ganha.
          </p>
        </div>

        <div className="section">
          <h2 className="section__title">Como as notas entram hoje</h2>
          <p className="section__subtitle">
            Pelo <b>Canvas</b>, sozinho. O simulado é agendado no SAS, vira Assignment lá, e as
            notas voltam no sync. Para acompanhar o que entrou e quando, use a{' '}
            <b>Auditoria</b>; para o estado da ligação com o Canvas, as <b>Integrações</b>.
          </p>
        </div>

        <div className="section">
          <h2 className="section__title">E se for preciso uma carga histórica</h2>
          <p className="section__subtitle">
            O pipeline não foi apagado — apenas saiu do caminho de quem clica. Ele roda como
            script, fora da requisição, e quem tem acesso ao servidor executa:
          </p>
          <pre className="section__subtitle">
            <code>./.venv/bin/python scripts/importar_planilha.py notas.xlsx</code>
          </pre>
          <p className="section__subtitle">
            É também o plano B se o Canvas ficar fora do ar.
          </p>
        </div>
      </section>

      <div className="tela-cabecalho">
        <div>
          <h2 className="tela-titulo">Histórico</h2>
          <p className="tela-subtitulo">Importações registradas — leitura, para auditoria.</p>
        </div>
      </div>

      <section className="card">
        <Historico consulta={historico} />
      </section>
    </div>
  );
}

function Historico({
  consulta,
}: {
  consulta: { data?: UploadHistorico[]; isError: boolean; isPending: boolean };
}) {
  if (consulta.isError) {
    return (
      <div className="empty-state">
        Não consegui carregar o histórico de importações.
        <div className="empty-state__hint">Backend offline? Confira se o uvicorn está rodando.</div>
      </div>
    );
  }
  if (consulta.isPending) return <div className="empty-state">Carregando…</div>;
  if (!consulta.data?.length) {
    return (
      <div className="empty-state">
        Nenhuma planilha foi importada.
        <div className="empty-state__hint">
          Era o esperado: todas as notas do sistema vieram do Canvas.
        </div>
      </div>
    );
  }

  return (
    <table className="data-table">
      <thead>
        <tr>
          <th>Arquivo</th>
          <th>Status</th>
          <th>Linhas aceitas</th>
          <th>Data</th>
        </tr>
      </thead>
      <tbody>
        {consulta.data.map((u) => (
          <tr key={u.id}>
            <td>{u.arquivo_origem}</td>
            <td><span className={`tag ${toneStatus(u.status)}`}>{u.status}</span></td>
            <td>{u.linhas_aceitas == null ? '—' : String(u.linhas_aceitas)}</td>
            <td>{formatarDataHora(u.criado_em)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
