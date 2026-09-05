import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import {
  deInputLocal, instrucaoDoBloco, paraInputLocal, ROTULO_DA_REFEICAO, ROTULO_DO_ESTADO,
  rotuloDoDia,
} from '../../dominio/cantina';
import {
  useCalendarioDaCantina, useCardapio, useCopiarCardapio, useCriarCardapio,
  usePublicarCardapio, useSalvarCardapio,
} from '../../hooks/cantina';
import { ErroApi } from '../../servicos/http';
import type { CorpoCardapio } from '../../servicos/api';
import type { Refeicao } from '../../tipos/cantina';

// O EDITOR de um dia — blocos, opções, quantas o aluno escolhe, e o prazo.
//
// O formato vem da planilha que a cantina já usa: linhas agrupadas em blocos
// (Guarnição, Vegetariano, Proteínas, Salada), uma coluna por dia. O que a
// planilha não tinha, e o produto precisa, é **quantas opções de cada bloco o
// aluno pode escolher** — é o par de campos ao lado do nome do bloco.
//
// ⚠️ **Copiar de outro dia não é conveniência: é o que decide se a ferramenta é
// usada.** Na planilha real, segunda e terça são quase idênticas. Sem copiar,
// são ~15 linhas digitadas por dia, cinco dias por semana — e a cantina
// abandona na terceira semana (docs/38 §2.2).
//
// ⚠️ O prazo copiado seria o prazo VENCIDO da origem, então quem recalcula é o
// servidor, pela regra da casa, para a data nova. A tela não manda prazo no
// `copiar-de` de propósito.

/** O estado local do editor. Espelha `CorpoCardapio`, com `id` opcional: o que
    tem id existe no banco, o que não tem nasce neste formulário. */
interface OpcaoEditavel { id?: string; nome: string; disponivel: boolean }
interface BlocoEditavel {
  id?: string;
  nome: string;
  escolhas_minimas: number;
  escolhas_maximas: number;
  opcoes: OpcaoEditavel[];
}

/** Os quatro blocos da planilha da cantina, para o dia em branco não começar
    numa folha vazia. São um PONTO DE PARTIDA — todos renomeáveis e removíveis. */
const BLOCOS_SUGERIDOS: BlocoEditavel[] = [
  { nome: 'Guarnição', escolhas_minimas: 0, escolhas_maximas: 2, opcoes: [] },
  { nome: 'Vegetariano', escolhas_minimas: 0, escolhas_maximas: 1, opcoes: [] },
  { nome: 'Proteínas', escolhas_minimas: 1, escolhas_maximas: 1, opcoes: [] },
  { nome: 'Salada', escolhas_minimas: 0, escolhas_maximas: 1, opcoes: [] },
];

export function CardapioDoDia() {
  const { data = '', refeicao = 'almoco' } = useParams<{ data: string; refeicao: Refeicao }>();

  // O dia inteiro numa consulta: é como a tela descobre se o cardápio já
  // existe, e o id dele quando existe.
  const { data: doDia = [], isLoading } = useCalendarioDaCantina(data, data);
  const existente = doDia.find((d) => d.refeicao === refeicao);

  const criar = useCriarCardapio();

  if (isLoading) return <p className="cant-vazio">Carregando…</p>;

  if (!existente) {
    return (
      <div className="cant-tela">
        <Cabeca data={data} refeicao={refeicao} estado="sem-cardapio" />
        <div className="cant-vazio">
          <p>Ainda não há cardápio para {ROTULO_DA_REFEICAO[refeicao].toLowerCase()} deste dia.</p>
          <button
            type="button"
            className="cant-tecla cant-tecla--principal"
            disabled={criar.isPending}
            onClick={() => criar.mutate({ data, refeicao })}
          >
            {criar.isPending ? 'Criando…' : 'Criar cardápio'}
          </button>
          {criar.isError && <p className="cant-erro" role="alert">{mensagem(criar.error)}</p>}
        </div>
      </div>
    );
  }

  return <Editor cardapioId={existente.id} data={data} refeicao={refeicao} />;
}

function Editor({
  cardapioId, data, refeicao,
}: { cardapioId: string; data: string; refeicao: Refeicao }) {
  const { data: cardapio } = useCardapio(cardapioId);
  const salvar = useSalvarCardapio();
  const publicar = usePublicarCardapio();
  const copiar = useCopiarCardapio();

  const [blocos, setBlocos] = useState<BlocoEditavel[]>([]);
  const [prazo, setPrazo] = useState('');
  const [semRefeicao, setSemRefeicao] = useState(false);
  const [sujo, setSujo] = useState(false);

  // Recarrega o formulário quando o cardápio chega ou muda no servidor. O
  // `sujo` protege o que está sendo digitado: uma revalidação em segundo plano
  // não pode apagar o bloco que a cantina acabou de escrever.
  useEffect(() => {
    if (!cardapio || sujo) return;
    setBlocos(
      cardapio.blocos.length
        ? cardapio.blocos.map((b) => ({
            id: b.id,
            nome: b.nome,
            escolhas_minimas: b.escolhas_minimas,
            escolhas_maximas: b.escolhas_maximas,
            opcoes: b.opcoes.map((o) => ({ id: o.id, nome: o.nome, disponivel: o.disponivel })),
          }))
        : BLOCOS_SUGERIDOS.map((b) => ({ ...b, opcoes: [] })),
    );
    setPrazo(paraInputLocal(cardapio.pedidos_ate));
    setSemRefeicao(cardapio.sem_refeicao);
  }, [cardapio, sujo]);

  // Candidatos a cópia: os 21 dias anteriores da MESMA refeição. Almoço e janta
  // são cardápios diferentes (docs/38 §8.0.8), então oferecer a janta como
  // origem de um almoço seria oferecer a comida errada.
  const inicioDaJanela = useMemo(() => {
    const d = new Date(`${data}T00:00`);
    d.setDate(d.getDate() - 21);
    return d.toISOString().slice(0, 10);
  }, [data]);
  const { data: anteriores = [] } = useCalendarioDaCantina(inicioDaJanela, data);
  const origens = anteriores.filter(
    (d) => d.refeicao === refeicao && d.id !== cardapioId && d.estado !== 'sem-refeicao',
  );

  function alterar(indice: number, patch: Partial<BlocoEditavel>) {
    setSujo(true);
    setBlocos((atual) => atual.map((b, i) => (i === indice ? { ...b, ...patch } : b)));
  }

  function corpo(): CorpoCardapio {
    return {
      pedidos_ate: deInputLocal(prazo),
      sem_refeicao: semRefeicao,
      blocos: blocos
        // Bloco sem nome não vai para o banco: seria uma linha invisível na
        // tela do aluno, sem jeito de apagar depois.
        .filter((b) => b.nome.trim())
        .map((b) => ({
          id: b.id,
          nome: b.nome.trim(),
          escolhas_minimas: b.escolhas_minimas,
          escolhas_maximas: Math.max(b.escolhas_maximas, b.escolhas_minimas),
          opcoes: b.opcoes
            .filter((o) => o.nome.trim())
            .map((o) => ({ id: o.id, nome: o.nome.trim(), disponivel: o.disponivel })),
        })),
    };
  }

  if (!cardapio) return <p className="cant-vazio">Carregando…</p>;

  const publicado = cardapio.estado === 'aberto' || cardapio.estado === 'fechado';
  const erro = salvar.error ?? publicar.error ?? copiar.error;

  return (
    <div className="cant-tela">
      <Cabeca data={data} refeicao={refeicao} estado={cardapio.estado} />

      {publicado && (
        <p className="cant-aviso">
          Este cardápio já está publicado. Renomear ou remover uma opção que alguém já pediu é
          recusado — se acabou, marque como <b>indisponível</b>.
          {' '}
          <Link to={`/cardapios/${data}/${refeicao}/pedidos`}>Ver os pedidos</Link>
        </p>
      )}

      <section className="cant-secao">
        <label className="cant-campo">
          <span className="cant-campo__rotulo">O aluno pode pedir até</span>
          <input
            type="datetime-local"
            className="cant-input"
            value={prazo}
            onChange={(e) => { setSujo(true); setPrazo(e.target.value); }}
          />
          {/* Diz de onde veio o valor. Sem isso, a cantina não sabe se o campo
              foi preenchido por ela ou pela regra da casa — e não descobre que
              existe uma regra. */}
          <span className="cant-campo__ajuda">
            Preenchido pela regra da cantina; troque à vontade. Depois deste
            instante ninguém acrescenta pedido — nem a cantina.
          </span>
        </label>

        <label className="cant-checkbox">
          <input
            type="checkbox"
            checked={semRefeicao}
            onChange={(e) => { setSujo(true); setSemRefeicao(e.target.checked); }}
          />
          {/* Diferente de "ainda não lancei", e a diferença importa: sem ela o
              alarme da coordenação ("cardápio de amanhã não lançado") mentiria
              todo fim de semana. */}
          <span>Não haverá {ROTULO_DA_REFEICAO[refeicao].toLowerCase()} neste dia</span>
        </label>
      </section>

      {!semRefeicao && (
        <>
          {!cardapio.blocos.length && origens.length > 0 && (
            <section className="cant-secao cant-secao--copiar">
              <h2 className="cant-secao__titulo">Começar a partir de outro dia</h2>
              <p className="cant-secao__ajuda">
                Traz blocos e opções. O prazo é recalculado para esta data — nunca copiado.
              </p>
              <div className="cant-copiar">
                {origens.slice(-6).reverse().map((o) => (
                  <button
                    key={o.id}
                    type="button"
                    className="cant-tecla"
                    disabled={copiar.isPending}
                    onClick={() => copiar.mutate({ id: cardapioId, origemId: o.id })}
                  >
                    {rotuloDoDia(o.data)}
                  </button>
                ))}
              </div>
            </section>
          )}

          <section className="cant-blocos">
            {blocos.map((bloco, i) => (
              <BlocoEditor
                // O `id` do banco quando existe; o índice para o bloco recém
                // criado, que ainda não tem um.
                key={bloco.id ?? `novo-${i}`}
                bloco={bloco}
                onAlterar={(patch) => alterar(i, patch)}
                onRemover={() => { setSujo(true); setBlocos((a) => a.filter((_, j) => j !== i)); }}
              />
            ))}

            <button
              type="button"
              className="cant-tecla"
              onClick={() => {
                setSujo(true);
                setBlocos((a) => [
                  ...a,
                  { nome: '', escolhas_minimas: 0, escolhas_maximas: 1, opcoes: [] },
                ]);
              }}
            >
              + Bloco
            </button>
          </section>
        </>
      )}

      {erro && <p className="cant-erro" role="alert">{mensagem(erro)}</p>}

      <footer className="cant-acoes">
        <button
          type="button"
          className="cant-tecla"
          disabled={salvar.isPending}
          onClick={() => salvar.mutate({ id: cardapioId, corpo: corpo() }, {
            onSuccess: () => setSujo(false),
          })}
        >
          {salvar.isPending ? 'Salvando…' : 'Salvar'}
        </button>

        {!publicado && (
          // Salva ANTES de publicar: publicar o que está na tela, e não o que
          // foi salvo por último, é o que a cantina espera do botão.
          <button
            type="button"
            className="cant-tecla cant-tecla--principal"
            disabled={salvar.isPending || publicar.isPending}
            onClick={() =>
              salvar.mutate({ id: cardapioId, corpo: corpo() }, {
                onSuccess: () => { setSujo(false); publicar.mutate(cardapioId); },
              })}
          >
            {publicar.isPending ? 'Publicando…' : 'Publicar'}
          </button>
        )}
      </footer>
    </div>
  );
}

function BlocoEditor({
  bloco, onAlterar, onRemover,
}: {
  bloco: BlocoEditavel;
  onAlterar: (patch: Partial<BlocoEditavel>) => void;
  onRemover: () => void;
}) {
  function alterarOpcao(indice: number, patch: Partial<OpcaoEditavel>) {
    onAlterar({ opcoes: bloco.opcoes.map((o, i) => (i === indice ? { ...o, ...patch } : o)) });
  }

  return (
    <section className="cant-bloco">
      <header className="cant-bloco__cabeca">
        <input
          className="cant-input cant-input--titulo"
          value={bloco.nome}
          placeholder="Nome do bloco"
          onChange={(e) => onAlterar({ nome: e.target.value })}
        />
        <label className="cant-mini">
          mín.
          <input
            type="number"
            min={0}
            className="cant-input cant-input--numero"
            value={bloco.escolhas_minimas}
            onChange={(e) => onAlterar({ escolhas_minimas: Math.max(0, Number(e.target.value)) })}
          />
        </label>
        <label className="cant-mini">
          máx.
          <input
            type="number"
            min={0}
            className="cant-input cant-input--numero"
            value={bloco.escolhas_maximas}
            onChange={(e) => onAlterar({ escolhas_maximas: Math.max(0, Number(e.target.value)) })}
          />
        </label>
        <button type="button" className="cant-tecla cant-tecla--fina" onClick={onRemover}>
          Remover bloco
        </button>
      </header>

      {/* A leitura em linguagem de gente do par mín./máx. — é o que o aluno vai
          ver, e mostrá-lo aqui evita publicar "escolha de 0 a 0" sem perceber. */}
      <p className="cant-bloco__instrucao">{instrucaoDoBloco({
        ...bloco, id: '', ordem: 0, opcoes: [],
      })}</p>

      <ul className="cant-opcoes">
        {bloco.opcoes.map((opcao, i) => (
          <li key={opcao.id ?? `nova-${i}`} className="cant-opcao">
            <input
              className="cant-input"
              value={opcao.nome}
              placeholder="Nome do prato"
              onChange={(e) => alterarOpcao(i, { nome: e.target.value })}
            />
            <label className="cant-mini">
              <input
                type="checkbox"
                checked={opcao.disponivel}
                onChange={(e) => alterarOpcao(i, { disponivel: e.target.checked })}
              />
              disponível
            </label>
            <button
              type="button"
              className="cant-tecla cant-tecla--fina"
              onClick={() => onAlterar({ opcoes: bloco.opcoes.filter((_, j) => j !== i) })}
            >
              Remover
            </button>
          </li>
        ))}
      </ul>

      <button
        type="button"
        className="cant-tecla cant-tecla--fina"
        onClick={() => onAlterar({ opcoes: [...bloco.opcoes, { nome: '', disponivel: true }] })}
      >
        + Opção
      </button>
    </section>
  );
}

function Cabeca({
  data, refeicao, estado,
}: { data: string; refeicao: Refeicao; estado: keyof typeof ROTULO_DO_ESTADO }) {
  return (
    <header className="cant-cabeca">
      <div>
        {/* O chevron de volta na MESMA linha do título — a regra C4 do padrão
            de campo, que vale aqui como vale nas telas da coordenação. */}
        <Link className="cant-voltar" to="/cardapios" aria-label="Voltar aos cardápios">‹</Link>
        <h1 className="cant-titulo">
          {ROTULO_DA_REFEICAO[refeicao]} · {rotuloDoDia(data)}
        </h1>
        <p className="cant-sub">{ROTULO_DO_ESTADO[estado]}</p>
      </div>
    </header>
  );
}

/** O 409 e o 422 do servidor são frases prontas para quem lê — as únicas
    mensagens da tela que explicam uma regra do produto, e por isso passam
    inteiras em vez de virar "não foi possível salvar". */
function mensagem(e: unknown): string {
  if (e instanceof ErroApi && !/→ \d{3}$/.test(e.message)) return e.message;
  return 'Não consegui salvar. Tente de novo.';
}
