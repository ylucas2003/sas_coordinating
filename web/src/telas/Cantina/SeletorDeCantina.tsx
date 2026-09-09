import { useSearchParams } from 'react-router-dom';

import { useCantinas } from '../../hooks/cantina';

// O recorte por cantina, na coordenação.
//
// ⚠️ **Aparece SEMPRE, inclusive com uma cantina só** — e isto reverte a regra
// que estava escrita aqui até 09/09: *"um seletor com uma opção é um controle
// que não decide nada"*.
//
// A reversão tem motivo, e ele não contradiz o argumento antigo: com uma
// cantina o seletor não **decide**, mas **informa**. "De qual cantina é este
// cardápio?" é pergunta que o coordenador faz mesmo havendo uma só — e a
// resposta anterior era ele não ver nada e o servidor escolher a primeira
// ativa em silêncio (`_cantina_padrao`, routes/cantina.py). Escolha invisível
// não é simplicidade; é o coordenador ler um número sem saber de quem ele é.
//
// A urgência veio de fora: "Food", que a planilha da coordenação registrava
// como um LOCAL, é o nome de uma segunda cantina (docs/40 §12.12). O seletor
// deixou de ser preparação para o futuro.
//
// A escolha mora na URL (`?cantina=`) e não em estado local, pelo mesmo motivo
// que `?aba=` mora lá em `/provas`: o coordenador manda o link do dia para
// alguém, e o recorte tem de ir junto — senão o outro abre a cantina errada e
// os dois discutem números diferentes.

/** Lê o recorte atual. Devolve `undefined` quando não há escolha explícita. */
export function useCantinaSelecionada(): string | undefined {
  const [params] = useSearchParams();
  return params.get('cantina') ?? undefined;
}

export function SeletorDeCantina() {
  const { data: cantinas = [] } = useCantinas();
  const [params, setParams] = useSearchParams();
  const atual = params.get('cantina') ?? '';

  const ativas = cantinas.filter((c) => c.ativo);
  // Sem cantina nenhuma não há o que recortar — e um seletor vazio é pior que
  // seletor nenhum. Com UMA, ele aparece: ver de quem é o cardápio é o ponto.
  if (!ativas.length) return null;

  return (
    <label className="cant-seletor">
      <span className="cant-seletor__rotulo">Cantina</span>
      <select
        className="cant-input"
        // Com UMA cantina não há opção vazia, então o valor tem de apontar
        // para ela — senão o `select` fica controlado por um valor que não
        // existe na lista, e o React desiste de casar os dois. A URL segue
        // limpa até alguém escolher de verdade: o que muda é só o que a tela
        // mostra, que é o ponto deste seletor.
        value={atual || (ativas.length === 1 ? ativas[0].id : '')}
        onChange={(e) => {
          const proximo = new URLSearchParams(params);
          if (e.target.value) proximo.set('cantina', e.target.value);
          else proximo.delete('cantina');
          // `replace` para o seletor não encher o histórico: voltar depois de
          // trocar três vezes tem de sair da tela, não desfazer as trocas.
          setParams(proximo, { replace: true });
        }}
      >
        {/* ⚠️ A opção vazia só existe quando há mais de uma cantina. Com uma
            só, "Todas (a primeira ativa)" seria um rótulo que descreve um
            mecanismo interno em vez de nomear a coisa que a pessoa está
            olhando — que é justamente o que o seletor passou a existir para
            corrigir. */}
        {ativas.length > 1 && <option value="">Todas (a primeira ativa)</option>}
        {ativas.map((c) => (
          <option key={c.id} value={c.id}>{c.nome}</option>
        ))}
      </select>
    </label>
  );
}
