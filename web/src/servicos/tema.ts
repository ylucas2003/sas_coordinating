import { useCallback, useSyncExternalStore } from 'react';

// O tema do SAS inteiro. DOIS, e só dois: dia e noite (docs/24 §7.2).
//
// Mora em `servicos/` e não mais em `telas/Aluno/pecas/` porque desde o tema
// escuro da coordenação ele serve os DOIS produtos. E tinha de servir: o tema
// é um atributo só na raiz (`data-tema`), então dois módulos com estado
// próprio brigariam pelo mesmo atributo.
//
// ⚠️ Este arquivo já teve um terceiro estado, 'sistema', e ele causava dois
// defeitos que só aparecem usando:
//
//   1. A escolha NÃO PERSISTIA. `useTema()` era chamado só dentro da folha
//      "Minha conta", e o `useEffect` dela removia `data-tema` no desmonte —
//      então fechar a folha desfazia o que o aluno acabara de escolher. O
//      cleanup existia para não deixar o atributo cravado ao sair da área do
//      aluno. ⚠️ A justificativa de então — "a coordenação tem alias próprio e
//      não é alcançada por `--alu-*`" — DEIXOU DE VALER: aquele alias morreu e
//      a coordenação lê os mesmos papéis, que este atributo governa nos dois.
//   2. Com três opções, duas delas podiam parecer a mesma coisa na tela
//      ("sistema" e "noite" num aparelho escuro), e o aluno tocava sem ver
//      nada mudar.
//
// Agora o tema é estado de MÓDULO, não de componente: quem monta a folha só
// assina o valor. É por isso que fechar a folha não pode mais desfazer nada.

export type Tema = 'dia' | 'noite';

const CHAVE = 'sas_tema';
/** A chave de quando o tema era só do aluno. Lida uma vez, para quem já tinha
    escolhido não perder a escolha ao abrir depois desta versão. */
const CHAVE_ANTIGA = 'sas_tema_aluno';

/**
 * O tema de quem nunca escolheu. **Claro, em todo o produto** (docs/40 §12.10).
 *
 * Era `preferidoPeloSistema()`, e o efeito prático disso é que quem decidia o
 * tema do SAS era a configuração do Chrome de quem abrisse: a coordenação
 * aparecia escura sem ninguém ter pedido escuro, e duas pessoas na mesma sala
 * viam produtos diferentes.
 *
 * ⚠️ Isto muda a ÁREA DO ALUNO, que foi desenhada com o escuro em mente
 * (docs/24 §7.2) — é o casco que se usa à noite, no celular. A decisão de 09/09
 * pesou esse custo: vale mais um produto com UM padrão do que um padrão que
 * depende do aparelho de quem abre. O remédio, se aparecer reclamação, já está
 * na tela: o botão existe nos três cascos e a escolha persiste.
 */
const TEMA_PADRAO: Tema = 'dia';

/**
 * A preferência do aparelho. **Não é mais chamada** — ver `TEMA_PADRAO`.
 *
 * Continua escrita de propósito: é o que permite voltar atrás em uma linha, e
 * apagá-la esconderia que a escolha existiu. Se algum dia o padrão voltar a
 * seguir o sistema, é esta função que volta para dentro de `lido()`.
 */
export function preferidoPeloSistema(): Tema {
  return typeof matchMedia === 'function' && matchMedia('(prefers-color-scheme: dark)').matches
    ? 'noite'
    : 'dia';
}

function lido(): Tema {
  try {
    const v = localStorage.getItem(CHAVE) ?? localStorage.getItem(CHAVE_ANTIGA);
    if (v === 'dia' || v === 'noite') return v;
  } catch {
    // Navegação privada e "bloquear dados de site" fazem o acessor LANÇAR, não
    // devolver null. Cair no padrão é o comportamento certo — e agora o padrão
    // é o mesmo para todo mundo, então este caminho deixou de ser uma segunda
    // resposta possível.
  }
  return TEMA_PADRAO;
}

let atual: Tema = lido();
const assinantes = new Set<() => void>();

function aplicar(tema: Tema): void {
  document.documentElement.setAttribute('data-tema', tema);
}

/**
 * Estampa o atributo assim que o módulo é importado, ANTES do primeiro render.
 *
 * É o que evita o piscão: sem isto a página nasceria com o tema da media query
 * e trocaria no primeiro efeito, e num aparelho claro com "noite" escolhido o
 * aluno veria um flash branco a cada abertura. Efeito no escopo do módulo é
 * incomum de propósito — é a única coisa que roda cedo o bastante.
 */
if (typeof document !== 'undefined') aplicar(atual);

export function trocarTema(novo: Tema): void {
  if (novo === atual) return;
  atual = novo;
  aplicar(novo);
  try {
    localStorage.setItem(CHAVE, novo);
  } catch {
    // Sem persistência a escolha vale só para esta visita. É melhor que
    // derrubar a tela por causa de uma preferência.
  }
  for (const avisar of assinantes) avisar();
}

function assinar(avisar: () => void): () => void {
  assinantes.add(avisar);
  return () => assinantes.delete(avisar);
}

export function useTema(): { tema: Tema; trocar: (t: Tema) => void; alternar: () => void } {
  // `useSyncExternalStore` e não `useState`: o tema é de módulo, e vários
  // componentes o leem ao mesmo tempo (a folha da conta e, no futuro, um botão
  // no casco). Com estado local os dois sairiam do ar em relação um ao outro.
  const tema = useSyncExternalStore(
    assinar,
    () => atual,
    () => 'dia' as Tema,
  );

  const alternar = useCallback(() => trocarTema(atual === 'dia' ? 'noite' : 'dia'), []);

  return { tema, trocar: trocarTema, alternar };
}
