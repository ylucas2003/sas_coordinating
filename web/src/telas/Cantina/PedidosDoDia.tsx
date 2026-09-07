import { useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import {
  contagemPorModo, escolhasDaLinha, fraseDaQuebra, marcaDoModo,
  presencialDoCardapio, quebraDaContagem,
  ROTULO_DA_REFEICAO, ROTULO_DO_ESTADO, rotuloDaContagem, rotuloDoDia,
} from '../../dominio/cantina';
import {
  useCalendarioDaCantina, useContagem, useMinhaCantina, usePedidosDoCardapio,
} from '../../hooks/cantina';
import type { ContagemDeOpcao, Refeicao } from '../../tipos/cantina';
import { BotoesDeExportar } from './BotoesDeExportar';

// OS PEDIDOS DE UM DIA — e são DUAS leituras, porque são dois momentos.
//
//   · a CONTAGEM ("47 arroz, 31 feijão, 12 proteína de soja") é o que se lê de
//     manhã, para cozinhar;
//   · a LISTA POR ALUNO é o que se lê no balcão, ao meio-dia.
//
// Uma tela só com a lista obrigaria a cantina a contar no papel — que é
// exatamente o trabalho que este produto existe para tirar dela (docs/38 §5).
//
// ⚠️ **É tudo o que a cantina vê do aluno**: nome, turma e restrição alimentar.
// Nenhuma consulta desta tela toca nota, simulado ou ficha. São dados de
// menores, e a própria lista de pedidos já é informação sensível por tabela
// interposta — a escolha vegetariana insinua religião ou saúde (docs/38 §8.2.2).

type Aba = 'contagem' | 'lista';

export function PedidosDoDia() {
  const { data = '', refeicao = 'almoco' } = useParams<{ data: string; refeicao: Refeicao }>();
  const [aba, setAba] = useState<Aba>('contagem');

  const { data: doDia = [] } = useCalendarioDaCantina(data, data);
  const cardapio = doDia.find((d) => d.refeicao === refeicao);

  const { data: contagem } = useContagem(cardapio?.id);
  const { data: pedidos = [], isLoading } = usePedidosDoCardapio(cardapio?.id);
  const { data: minha } = useMinhaCantina();
  const valor = refeicao === 'almoco' ? minha?.valor_almoco : minha?.valor_janta;

  const porBloco = useMemo(() => agruparPorBloco(contagem?.opcoes ?? []), [contagem]);
  const comRestricao = pedidos.filter((p) => p.restricaoAlimentar).length;
  // O placar do servidor, com a lista como resto honesto — e `null` quando
  // ninguém pega na hora: um "0 e 0" fixo apareceria em toda cantina que nunca
  // ligou a feature, e ainda sequestrava o "Nenhum pedido ainda" abaixo, que
  // deixava de aparecer num dia sem pedido nenhum.
  const presencial = presencialDoCardapio(contagem?.presencial, pedidos);
  // A contagem sai da LISTA e não do calendário: é a fonte que esta tela já tem
  // aberta, e é o mesmo número que o cabeçalho sempre mostrou (docs/40 §10.1).
  const doDiaPorModo = useMemo(() => contagemPorModo(pedidos), [pedidos]);
  const quebra = quebraDaContagem(doDiaPorModo);

  if (!cardapio) {
    return <p className="cant-vazio">Não há cardápio para este dia.</p>;
  }

  const final = cardapio.estado === 'fechado';

  return (
    <div className="cant-tela">
      <header className="cant-cabeca">
        <div>
          <Link className="cant-voltar" to={`/cardapios/${data}/${refeicao}`} aria-label="Voltar ao cardápio">‹</Link>
          <h1 className="cant-titulo">
            Pedidos · {ROTULO_DA_REFEICAO[refeicao]} de {rotuloDoDia(data)}
          </h1>
          <p className="cant-sub">
            {/* "N pedidos" deixou de ser verdade no dia em que alguém come sem
                ter pedido — e a aba "O que cozinhar", ao lado, soma só quem
                pediu. A quebra aparece só quando existe presencial. */}
            {pedidos.length} {rotuloDaContagem(doDiaPorModo)}
            {quebra && ` · ${fraseDaQuebra(quebra)}`}
            {' · '}
            {/* A frase muda com o estado porque a pergunta muda: antes do prazo
                o número ainda anda, depois dele é o que vai para o fogão. */}
            {final ? 'contagem final' : `ainda ${ROTULO_DO_ESTADO[cardapio.estado].toLowerCase()}`}
            {comRestricao > 0 && ` · ${comRestricao} com restrição alimentar`}
          </p>
        </div>

        <div className="cant-cabeca__acoes">
          <BotoesDeExportar
            dia={{
              data, refeicao, pedidos,
              // A exportação leva as linhas por OPÇÃO, que é o que a planilha
              // do balcão sempre teve. O presencial não entra nelas de
              // propósito (docs/40 §10.1): ele não tem prato para somar, e
              // uma linha "presencial 3" no meio de "arroz 47" seria lida como
              // mais um prato.
              contagem: contagem?.opcoes ?? [],
              cantina: minha?.nome ?? null,
              valor: valor ?? null,
              // A cantina LEVA o texto da restrição: é o que muda o que sai do
              // balcão, e a folha impressa é justamente para o balcão.
              incluirRestricao: true,
            }}
          />
        </div>
      </header>

      <div className="cant-barra-abas">
        <div className="cant-abas" role="tablist">
          <button
            type="button" role="tab" aria-selected={aba === 'contagem'}
            className={`cant-aba${aba === 'contagem' ? ' cant-aba--ativa' : ''}`}
            onClick={() => setAba('contagem')}
          >
            O que cozinhar
          </button>
          <button
            type="button" role="tab" aria-selected={aba === 'lista'}
            className={`cant-aba${aba === 'lista' ? ' cant-aba--ativa' : ''}`}
            onClick={() => setAba('lista')}
          >
            O que servir
          </button>
        </div>

        {/* A soma do dia, quando a coordenação informou o preço. Fica ao lado
            das abas e não no cabeçalho porque é consequência dos pedidos, não
            identidade da tela. */}
        {valor != null && (
          <span className="cant-total">
            {pedidos.length} × {moeda(valor)} = <b>{moeda(valor * pedidos.length)}</b>
          </span>
        )}
      </div>

      {isLoading && <p className="cant-vazio">Carregando…</p>}

      {!isLoading && aba === 'contagem' && (
        <div className="cant-contagem">
          {porBloco.map(([bloco, linhas]) => (
            <section key={bloco} className="cant-bloco cant-bloco--leitura">
              <h2 className="cant-bloco__titulo">{bloco}</h2>
              <ul className="cant-contagem__lista">
                {linhas.map((linha) => (
                  <li
                    key={linha.opcao_id}
                    className={`cant-contagem__linha${linha.disponivel ? '' : ' cant-contagem__linha--fora'}`}
                  >
                    <span className="cant-contagem__nome">
                      {linha.opcao}
                      {!linha.disponivel && <span className="cant-tarja">acabou</span>}
                    </span>
                    {/* O número em magnitude: é o que se lê de longe, com a
                        mão na panela. */}
                    <span className="cant-contagem__numero">{linha.quantos}</span>
                  </li>
                ))}
              </ul>
            </section>
          ))}
          {/* ⚠️ LINHA À PARTE, e não uma opção a mais na contagem (docs/40 §7).
              Retirada na hora não escolhe prato: somá-la ao "47 arroz"
              inventaria um arroz que ninguém pediu, e é justamente esse número
              que vai para o fogão. Some no dia em que ninguém pega na hora — e
              some também contra servidor que não manda o bloco, porque aí a
              lista já respondeu a mesma pergunta. */}
          {presencial && (
            <section className="cant-bloco cant-bloco--leitura">
              <h2 className="cant-bloco__titulo">
                Retirada na hora
                <span className="cant-bloco__instrucao">sem prato escolhido</span>
              </h2>
              <ul className="cant-contagem__lista">
                <li className="cant-contagem__linha">
                  <span className="cant-contagem__nome">Já retiraram</span>
                  <span className="cant-contagem__numero">{presencial.retirados}</span>
                </li>
                <li className="cant-contagem__linha">
                  <span className="cant-contagem__nome">Códigos gerados, ainda não lidos</span>
                  <span className="cant-contagem__numero">{presencial.pendentes}</span>
                </li>
              </ul>
            </section>
          )}

          {!porBloco.length && !presencial && <p className="cant-vazio">Nenhum pedido ainda.</p>}
        </div>
      )}

      {!isLoading && aba === 'lista' && (
        <ul className="cant-lista">
          {pedidos.map((pedido) => (
            <li key={pedido.alunoId} className="cant-lista__linha">
              <div className="cant-lista__aluno">
                <b>{pedido.nome ?? '—'}</b>
                {pedido.turma && <span className="cant-lista__turma">{pedido.turma}</span>}
                {/* A marca de modo, para o balcão saber se procura um prato ou
                    espera um código (docs/40 §7). Ela não é semáforo: é
                    contorno e palavra, como o resto dos estados desta folha. */}
                {pedido.modo === 'presencial' && (
                  <span className="cant-tarja">{marcaDoModo(pedido)}</span>
                )}
              </div>
              {/* Sai de `escolhasDaLinha`, e não de um ternário aqui: esta é a
                  MESMA célula que a folha impressa e a tela da coordenação
                  mostram. Era a única das três escrita à mão — e a única sem
                  teste —, então mudar a frase no domínio corrigia duas
                  superfícies e deixava para trás justamente a que fica aberta
                  no balcão. */}
              <div className="cant-lista__escolhas">
                {escolhasDaLinha(pedido) || '—'}
              </div>
              {/* A restrição fica em destaque, e não numa coluna qualquer: é a
                  informação que muda o que sai do balcão. */}
              {pedido.restricaoAlimentar && (
                <div className="cant-lista__restricao">⚠ {pedido.restricaoAlimentar}</div>
              )}
            </li>
          ))}
          {!pedidos.length && <p className="cant-vazio">Nenhum pedido ainda.</p>}
        </ul>
      )}
    </div>
  );
}

/** Agrupa preservando a ordem do cardápio — que já vem ordenada do servidor. */
function agruparPorBloco(contagem: ContagemDeOpcao[]): Array<[string, ContagemDeOpcao[]]> {
  const mapa = new Map<string, ContagemDeOpcao[]>();
  for (const linha of contagem) {
    const atual = mapa.get(linha.bloco);
    if (atual) atual.push(linha);
    else mapa.set(linha.bloco, [linha]);
  }
  return [...mapa.entries()];
}

/** Reais com vírgula. `Intl` e não `toFixed`: o separador de milhar aparece
    quando o total passa de mil, que é o caso de um mês inteiro. */
function moeda(valor: number): string {
  return valor.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}
