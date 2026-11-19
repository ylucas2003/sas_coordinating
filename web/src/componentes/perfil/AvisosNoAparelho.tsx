// "Avisos neste aparelho" — a seção que liga e desliga o push (docs/45 §6.3).
//
// Uma peça só para os dois cascos: no aluno ela mora na folha "Minha conta"
// (`CascoAluno.tsx`), na coordenação abre do rodapé do rail (`Rail.tsx`). O que
// muda por casco é a classe do botão — a tecla do aluno, o `.btn` da coordenação.
//
// O aluno recebe UM evento: a missão do dia (docs/45 §16), e é dela que o texto
// fala — quem ativa precisa saber o que vai receber. A coordenação, por ora, só
// tem o "Mandar um teste". A seção some inteira quando o servidor não tem chave
// VAPID (ou a sessão é da cantina): não existe botão que não funciona.
//
// ⚠️ O iPhone numa aba do Safari não recebe push — regra da Apple, sem contorno
// (docs/45 §1). Ali a seção não oferece "Ativar"; ensina a instalar na Tela de
// Início, que é o maior funil do plano.

import { useId, useState } from 'react';

import {
  useAparelhosComAvisos,
  useAtivarAvisos,
  useConfiguracaoDosAvisos,
  useDesativarAvisos,
  useEsteAparelho,
  useRevogarAparelho,
  useTestarAvisos,
} from '../../hooks/avisosNoAparelho';
import { comoReligar } from '../../dominio/avisosNoAparelho';
import type { AparelhoComAvisos, ResultadoDoTeste } from '../../servicos/api';
import { pedirPermissao } from '../../servicos/avisosNoAparelho';

type Casco = 'aluno' | 'coordenacao';

const BOTOES: Record<Casco, { primario: string; secundario: string }> = {
  aluno: {
    primario: 'alu-tecla alu-tecla--larga',
    secundario: 'alu-tecla alu-tecla--fantasma alu-tecla--pequena',
  },
  coordenacao: { primario: 'btn btn--primary', secundario: 'btn btn--ghost' },
};

// O que a pessoa vai receber, dito ANTES de ela ativar. Sem a hora do aviso de
// propósito: ela mora no crontab (`infra/vps/crontab-sas`), e uma hora escrita
// aqui ficaria mentindo no dia em que a linha mudasse.
const O_QUE_CHEGA: Record<Casco, { convite: string; ativo: string }> = {
  aluno: {
    convite: 'Receba aqui a missão de hoje, todo dia, mesmo com o SAS fechado.',
    ativo: 'Este aparelho recebe a missão de hoje, todo dia.',
  },
  coordenacao: {
    convite: 'Receba um aviso aqui quando houver novidade no SAS, mesmo com ele fechado.',
    ativo: 'Este aparelho recebe os avisos do SAS.',
  },
};

const DATA_CURTA = new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' });

const NOME_DA_PLATAFORMA: Record<AparelhoComAvisos['plataforma'], string> = {
  ios: 'iPhone ou iPad',
  android: 'Android',
  desktop: 'Computador',
  outra: 'Aparelho',
};

function mensagemDoErro(erro: unknown): string {
  return erro instanceof Error && erro.message ? erro.message : 'Não deu certo agora. Tente de novo.';
}

function fraseDoTeste(r: ResultadoDoTeste): string {
  if (r.tentadas === 0) return 'Nenhum aparelho com avisos ativos para testar.';
  const partes: string[] = [];
  if (r.entregues > 0) {
    partes.push(
      r.entregues === 1
        ? 'Teste enviado. Deve chegar em alguns segundos.'
        : `Teste enviado para ${r.entregues} aparelhos. Deve chegar em alguns segundos.`,
    );
  }
  if (r.removidas > 0) {
    partes.push(
      r.removidas === 1
        ? 'Um aparelho que não recebia mais saiu da lista.'
        : `${r.removidas} aparelhos que não recebiam mais saíram da lista.`,
    );
  }
  if (r.falhas > 0) {
    partes.push(
      r.falhas === 1
        ? 'Um aparelho não recebeu agora; tente de novo daqui a pouco.'
        : `${r.falhas} aparelhos não receberam agora; tente de novo daqui a pouco.`,
    );
  }
  return partes.join(' ');
}

/**
 * `comTitulo={false}` quando quem abre já dá o título — o diálogo da coordenação
 * se chama "Avisos neste aparelho", e repetir o rótulo dentro dele seria eco.
 */
export function AvisosNoAparelho({ casco, comTitulo = true }: { casco: Casco; comTitulo?: boolean }) {
  const idTitulo = useId();
  const config = useConfiguracaoDosAvisos();
  const aparelho = useEsteAparelho(config.data);
  const ligado = config.data?.ativo === true;
  const lista = useAparelhosComAvisos(ligado);

  const ativar = useAtivarAvisos();
  const desativar = useDesativarAvisos();
  const testar = useTestarAvisos();
  const revogar = useRevogarAparelho();
  const [mensagem, setMensagem] = useState<string | null>(null);

  // Servidor sem chave, sessão sem push ou consulta que falhou: a seção não
  // existe. Um "Ativar" que não pode funcionar é pior que nenhum.
  if (!ligado || !config.data?.chavePublica) return null;
  const chavePublica = config.data.chavePublica;

  const botoes = BOTOES[casco];
  const ocupado = ativar.isPending || desativar.isPending || testar.isPending || revogar.isPending;
  const leitura = aparelho.data;

  function aoAtivar() {
    setMensagem(null);
    // A permissão é pedida AQUI, ainda dentro do clique (servicos/avisosNoAparelho.ts).
    const permissao = pedirPermissao();
    ativar.mutate(
      { permissao, chavePublica },
      {
        onSuccess: () => setMensagem('Pronto. Este aparelho vai receber os avisos do SAS.'),
        onError: (erro) => setMensagem(mensagemDoErro(erro)),
      },
    );
  }

  function aoDesativar() {
    setMensagem(null);
    desativar.mutate(undefined, {
      onSuccess: () => setMensagem('Avisos desativados neste aparelho.'),
      onError: (erro) => setMensagem(mensagemDoErro(erro)),
    });
  }

  function aoTestar() {
    setMensagem(null);
    testar.mutate(undefined, {
      onSuccess: (r) => setMensagem(fraseDoTeste(r)),
      onError: (erro) => setMensagem(mensagemDoErro(erro)),
    });
  }

  function aoRevogar(id: string) {
    setMensagem(null);
    revogar.mutate(id, { onError: (erro) => setMensagem(mensagemDoErro(erro)) });
  }

  const aparelhos = lista.data?.aparelhos ?? [];

  return (
    <section
      className={`avisos avisos--${casco}`}
      aria-labelledby={comTitulo ? idTitulo : undefined}
      aria-label={comTitulo ? undefined : 'Avisos neste aparelho'}
    >
      {comTitulo && (
        <h3 id={idTitulo} className="avisos__rotulo">
          Avisos neste aparelho
        </h3>
      )}

      {aparelho.isPending && <p className="avisos__texto">Verificando este aparelho…</p>}

      {aparelho.isError && (
        <p className="avisos__texto">Não consegui ler o estado deste aparelho. Feche e abra de novo.</p>
      )}

      {leitura?.estado === 'inativo' && (
        <>
          <p className="avisos__texto">{O_QUE_CHEGA[casco].convite}</p>
          <button type="button" className={botoes.primario} onClick={aoAtivar} disabled={ocupado}>
            {ativar.isPending ? 'Ativando…' : 'Ativar avisos'}
          </button>
        </>
      )}

      {leitura?.estado === 'ativo' && (
        <>
          <p className="avisos__texto">
            <span className="avisos__selo">Ativo</span> {O_QUE_CHEGA[casco].ativo}
          </p>
          <div className="avisos__acoes">
            <button type="button" className={botoes.secundario} onClick={aoTestar} disabled={ocupado}>
              {testar.isPending ? 'Enviando…' : 'Mandar um teste'}
            </button>
            <button type="button" className={botoes.secundario} onClick={aoDesativar} disabled={ocupado}>
              {desativar.isPending ? 'Desativando…' : 'Desativar'}
            </button>
          </div>
        </>
      )}

      {leitura?.estado === 'precisa-instalar' && (
        <>
          <p className="avisos__texto">
            No iPhone, os avisos só chegam com o SAS na <b>Tela de Início</b>. É uma vez só:
          </p>
          <ol className="avisos__passos">
            <li>
              No Safari, toque em <b>Compartilhar</b> (o quadrado com a seta para cima).
            </li>
            <li>
              Escolha <b>Adicionar à Tela de Início</b>.
            </li>
            <li>Abra o SAS pelo ícone novo, entre e volte aqui para ativar.</li>
          </ol>
          <p className="avisos__nota">Precisa do iOS 16.4 ou mais novo.</p>
        </>
      )}

      {leitura?.estado === 'bloqueado' && (
        <>
          <p className="avisos__texto">Os avisos estão bloqueados para o SAS neste navegador.</p>
          <p className="avisos__nota">{comoReligar(leitura.plataforma, leitura.instalado)}</p>
        </>
      )}

      {leitura?.estado === 'sem-suporte' && (
        <p className="avisos__texto">
          Este navegador não recebe avisos. No Android, use o Chrome; no iPhone, o SAS instalado na Tela de
          Início (iOS 16.4 ou mais novo).
        </p>
      )}

      <p className="avisos__mensagem" role="status">
        {mensagem}
      </p>

      {aparelhos.length > 0 && (
        <div className="avisos__lista">
          <h4 className="avisos__subrotulo">Seus aparelhos</h4>
          <ul>
            {aparelhos.map((a) => {
              const este = a.id === leitura?.idNoServidor;
              const nome = a.descricao || NOME_DA_PLATAFORMA[a.plataforma];
              return (
                <li key={a.id} className="avisos__aparelho">
                  <span className="avisos__aparelho-nome">
                    {nome}
                    {este && <span className="avisos__este"> · este aparelho</span>}
                    <span className="avisos__aparelho-data">
                      ativado em {DATA_CURTA.format(new Date(a.criadaEm))}
                    </span>
                  </span>
                  {!este && (
                    <button
                      type="button"
                      className={botoes.secundario}
                      onClick={() => aoRevogar(a.id)}
                      disabled={ocupado}
                      aria-label={`Remover ${nome} da lista de aparelhos`}
                    >
                      Remover
                    </button>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </section>
  );
}
