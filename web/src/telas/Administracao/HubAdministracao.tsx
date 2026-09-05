import { useMemo } from 'react';

import { CartaoDeCampo, EloQuieto } from '../../componentes/ui/Campo';
import { useAuditoria, useCoordenadores, usePainelGravacoes } from '../../hooks/consultas';
import { useCalendarioNaCoordenacao, useDireitos } from '../../hooks/cantina';
import { isoDoDia } from '../../dominio/cantina';
import { useParametroDeImportancia } from '../../hooks/banco';
import { resumoAndamento, situacaoDe } from '../../dominio/gravacoes';

// ADMINISTRAÇÃO — quatro campos, e nada além deles.
//
// Era QUATRO ABAS de ferramentas sem relação nenhuma entre si: contas,
// auditoria, integrações e calibração empilhadas num seletor, que é
// literalmente o desenho que a aba Estudar do aluno substituiu por cards. Foi
// a primeira tela a migrar porque é o caso mais limpo do brief — e porque é
// ela que ensina o padrão ao resto do código.
//
// A divisão é por PERGUNTA (C1). "Contas" vira "Quem tem acesso"; "Integrações"
// vira "O Canvas está de pé?" — que é o que a pessoa quer saber quando abre.
//
// ⚠️ O subtítulo de Integrações é o que mais justifica a regra C2: hoje, para
// descobrir que uma aula travou, é preciso ENTRAR na aba. Com o dado vivo no
// card, a falha aparece na tela de entrada — que é onde uma falha precisa
// aparecer.
//
// ⚠️ O quinto campo é a CANTINA, e o subtítulo dele é o exemplo mais literal
// da C2: a falha que importa — "o cardápio de amanhã ainda não foi lançado", às
// 18h de hoje — aparece na tela de ENTRADA, que é onde uma falha precisa
// aparecer. Sem isso, para descobrir que a cantina esqueceu o dia seguinte
// seria preciso entrar, escolher o mês e procurar (docs/38 §6).
//
// ⚠️ A rota `/administracao` era a tela de Contas e passa a ser este hub;
// Contas mudou para `/administracao/contas`. Quem tiver o link antigo salvo
// cai aqui, a um clique de distância, em vez de num 404.

/** Dias sem entrar a partir dos quais a conta merece ser mencionada. */
const DIAS_PARA_MENCIONAR = 30;

function diasDesde(iso: string | null): number | null {
  if (!iso) return null;
  const quando = new Date(iso).getTime();
  if (Number.isNaN(quando)) return null;
  return Math.floor((Date.now() - quando) / 86_400_000);
}

// Os quatro resumos são HOOKS, e por isso levam o prefixo `use` em vez do
// `usar` que a convenção de português pediria: `use` é contrato do React — é
// o que o linter e o compilador usam para saber que a regra dos hooks se
// aplica —, não preferência de idioma. O mesmo já vale para `useTituloDaTela`
// e `useTema`.

/**
 * "cardápio de amanhã não lançado · 87 alunos com direito"
 *
 * A ordem das duas metades não é estética: a PENDÊNCIA vem primeiro quando
 * existe, porque é a única coisa aqui sobre a qual alguém age hoje. Quando não
 * há pendência, o card relata o estado e fica quieto — é o que separa um hub
 * de um menu.
 */
function useResumoDaCantina() {
  const { data: painel, isLoading: carregandoDireitos, isError: erroDireitos } = useDireitos();
  // Só amanhã, e não o mês: a pergunta do card é sobre o próximo dia letivo.
  const amanha = useMemo(() => {
    const d = new Date();
    d.setDate(d.getDate() + 1);
    return isoDoDia(d);
  }, []);
  const { data: dias, isLoading: carregandoDias, isError: erroDias } = useCalendarioNaCoordenacao(amanha, amanha);

  const texto = useMemo(() => {
    if (!painel && !dias) return null;
    const partes: string[] = [];
    // "Publicado" é aberto OU fechado: os dois são cardápio que existe para o
    // aluno. Rascunho não conta — ele não aparece para ninguém.
    const publicados = (dias ?? []).filter(
      (d) => d.estado === 'aberto' || d.estado === 'fechado' || d.estado === 'sem-refeicao',
    ).length;
    if (dias && publicados === 0) partes.push('cardápio de amanhã não lançado');
    if (painel?.comDireito) partes.push(`${painel.comDireito} alunos com direito`);
    return partes.length ? partes.join(' · ') : null;
  }, [painel, dias]);

  // Falha de consulta NÃO vira "0": um número errado é pior que nenhum.
  return {
    texto: erroDireitos || erroDias ? null : texto,
    carregando: carregandoDireitos || carregandoDias,
  };
}

/** "3 coordenadores · 1 sem entrar há 40 dias" */
function useResumoDeContas() {
  const { data: coordenadores, isLoading, isError } = useCoordenadores();
  const texto = useMemo(() => {
    if (!coordenadores) return null;
    const ativos = coordenadores.filter((c) => c.ativo);
    if (ativos.length === 0) return null;
    const partes = [`${ativos.length} ${ativos.length === 1 ? 'conta ativa' : 'contas ativas'}`];
    // Nunca ter entrado e ter parado de entrar são coisas diferentes, e as duas
    // interessam — mas a segunda é a que costuma indicar conta esquecida.
    const parados = ativos.filter((c) => {
      const d = diasDesde(c.ultimo_login_em);
      return d != null && d >= DIAS_PARA_MENCIONAR;
    });
    const nunca = ativos.filter((c) => !c.ultimo_login_em);
    if (parados.length) {
      const pior = Math.max(...parados.map((c) => diasDesde(c.ultimo_login_em) ?? 0));
      partes.push(`${parados.length} sem entrar há ${pior} dias`);
    } else if (nunca.length) {
      partes.push(`${nunca.length} ${nunca.length === 1 ? 'nunca entrou' : 'nunca entraram'}`);
    }
    return partes.join(' · ');
  }, [coordenadores]);
  // Falha de consulta NÃO vira "0 contas": um número errado é pior que nenhum.
  return { texto: isError ? null : texto, carregando: isLoading };
}

/** "34 eventos hoje · 2 alterações de nota" */
function useResumoDeAuditoria() {
  // Meia-noite local: o calendário escolar é em data local, não em instante UTC.
  const desde = useMemo(() => {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    return d.toISOString();
  }, []);
  const { data, isLoading, isError } = useAuditoria({ desde, limite: 200 });
  const texto = useMemo(() => {
    if (!data) return null;
    const eventos = data.eventos ?? [];
    if (eventos.length === 0) return null;
    const notas = eventos.filter((e) => e.canal === 'nota').length;
    const partes = [`${eventos.length} ${eventos.length === 1 ? 'evento hoje' : 'eventos hoje'}`];
    if (notas) partes.push(`${notas} ${notas === 1 ? 'alteração de nota' : 'alterações de nota'}`);
    return partes.join(' · ');
  }, [data]);
  return { texto: isError ? null : texto, carregando: isLoading };
}

/** "2 aulas com erro" · o erro vem antes do andamento. */
function useResumoDeIntegracoes() {
  const { data, isLoading, isError } = usePainelGravacoes();
  const texto = useMemo(() => {
    if (!data) return null;
    const aulas = data.aulas ?? [];
    if (aulas.length === 0) return null;
    const comErro = aulas.filter((a) => situacaoDe(a) === 'erro').length;
    // O erro antes do andamento, pelo mesmo motivo da tela de Integrações: uma
    // aula travada é o que a coordenação precisa ver do corredor, mesmo com a
    // fila andando.
    if (comErro) return `${comErro} ${comErro === 1 ? 'aula com erro' : 'aulas com erro'}`;
    const andamento = resumoAndamento(aulas);
    if (andamento) return andamento;
    const publicadas = aulas.filter((a) => situacaoDe(a) === 'publicado').length;
    return `${publicadas} ${publicadas === 1 ? 'aula no canal' : 'aulas no canal'}`;
  }, [data]);
  return { texto: isError ? null : texto, carregando: isLoading };
}

/** "meia-vida 1,5 ano · reordena o que o aluno vê" */
function useResumoDeCalibracao() {
  const { data, isLoading, isError } = useParametroDeImportancia();
  const texto = useMemo(() => {
    if (!data) return null;
    const anos = data.meiaVidaAnos;
    const rotulo = `${anos.toFixed(1).replace('.', ',')} ${anos === 1 ? 'ano' : 'anos'}`;
    return `meia-vida ${rotulo} · reordena o que o aluno vê`;
  }, [data]);
  return { texto: isError ? null : texto, carregando: isLoading };
}

export function HubAdministracao() {
  const cantina = useResumoDaCantina();
  const contas = useResumoDeContas();
  const auditoria = useResumoDeAuditoria();
  const integracoes = useResumoDeIntegracoes();
  const calibracao = useResumoDeCalibracao();

  return (
    <div className="tela">
      <div className="tela-cabecalho">
        <div>
          <h1 className="tela-titulo">Administração</h1>
          <p className="tela-subtitulo">
            As ferramentas de manutenção do sistema. Cada uma responde a uma pergunta.
          </p>
        </div>
      </div>

      <div className="campo-grade">
        {/* Vai para o CALENDÁRIO, e não para a tela de contas: a resposta à
            pergunta do card é o mês lançado, não a lista de quem lança. As
            contas e o direito ficam a um link de lá — e o caminho existe nos
            dois sentidos, senão uma das duas telas fica órfã. */}
        <CartaoDeCampo
          olho="Cantina"
          titulo="A cantina está em dia?"
          para="/cantina"
          carregando={cantina.carregando}
          subtitulo={cantina.texto}
          vazio="Nenhuma cantina cadastrada ainda."
          glifo={
            <>
              <path d="M16 20v14a8 8 0 0 0 16 0V20" />
              <path d="M24 20v34" />
              <path d="M48 54V20c-6 0-9 5-9 12s3 10 9 10" />
            </>
          }
        />

        <CartaoDeCampo
          olho="Contas"
          titulo="Quem tem acesso"
          para="/administracao/contas"
          carregando={contas.carregando}
          subtitulo={contas.texto}
          vazio="Nenhuma conta de coordenação cadastrada ainda."
          glifo={
            <>
              <circle cx="27" cy="24" r="9" />
              <path d="M12 54c0-8.3 6.7-15 15-15s15 6.7 15 15" />
              <path d="M46 26h12M52 20v12" />
            </>
          }
        />

        <CartaoDeCampo
          olho="Auditoria"
          titulo="O que aconteceu"
          para="/auditoria"
          carregando={auditoria.carregando}
          subtitulo={auditoria.texto}
          vazio="Nenhum evento hoje. O registro guarda tudo desde o começo."
          glifo={
            <>
              <path d="M16 12h27l11 11v35H16z" />
              <path d="M43 12v11h11" />
              <path d="M24 36h22M24 45h14" />
            </>
          }
        />

        <CartaoDeCampo
          olho="Integrações"
          titulo="O Canvas está de pé?"
          para="/integracoes"
          carregando={integracoes.carregando}
          subtitulo={integracoes.texto}
          vazio="Nenhuma aula sincronizada ainda."
          glifo={
            <>
              <path d="M28 42a10 10 0 0 1 0-14l7-7a10 10 0 0 1 14 14l-3 3" />
              <path d="M42 28a10 10 0 0 1 0 14l-7 7a10 10 0 0 1-14-14l3-3" />
            </>
          }
        />

        <CartaoDeCampo
          olho="Calibração"
          titulo="Quanto vale cada assunto"
          para="/calibracao"
          carregando={calibracao.carregando}
          subtitulo={calibracao.texto}
          vazio="O índice de importância ainda não foi ajustado."
          glifo={
            <>
              <path d="M12 50h46" />
              <path d="M20 50V32M32 50V20M44 50V38M56 50V26" />
              <circle cx="32" cy="20" r="3.5" />
            </>
          }
        />
      </div>

      {/*
        C5 · O elo quieto. A importação por planilha foi aposentada em
        03/09/2026 (docs/32 §2.4), mas a rota continua existindo para explicar
        o que mudou. Ela é elo quieto e NUNCA um quinto card: oferecer o card
        seria oferecer um caminho de escrita que o produto não tem mais.

        `semContagem` porque aqui o elo leva a uma explicação, não a uma lista
        — não há o que contar, e a regra de sumir quando vazio não se aplica.
      */}
      <div className="campo-elos">
        <EloQuieto
          para="/importar"
          texto="Importação por planilha"
          contagem={null}
          semContagem
        />
        <span className="campo-elo-nota">aposentada — a rota explica o que mudou</span>
      </div>
    </div>
  );
}
