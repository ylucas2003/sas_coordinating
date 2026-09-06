import { useSearchParams } from 'react-router-dom';

import { useCantinas } from '../../hooks/cantina';

// O recorte por cantina, na coordenação.
//
// ⚠️ **Some quando há uma cantina só**, que é o estado de hoje. Um seletor com
// uma opção é um controle que não decide nada — ocupa a linha, convida ao
// clique e não muda a tela. Ele aparece no dia em que houver a segunda, sem
// ninguém precisar mexer no código.
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
  if (ativas.length < 2) return null;

  return (
    <label className="cant-seletor">
      <span className="cant-seletor__rotulo">Cantina</span>
      <select
        className="cant-input"
        value={atual}
        onChange={(e) => {
          const proximo = new URLSearchParams(params);
          if (e.target.value) proximo.set('cantina', e.target.value);
          else proximo.delete('cantina');
          // `replace` para o seletor não encher o histórico: voltar depois de
          // trocar três vezes tem de sair da tela, não desfazer as trocas.
          setParams(proximo, { replace: true });
        }}
      >
        <option value="">Todas (a primeira ativa)</option>
        {ativas.map((c) => (
          <option key={c.id} value={c.id}>{c.nome}</option>
        ))}
      </select>
    </label>
  );
}
