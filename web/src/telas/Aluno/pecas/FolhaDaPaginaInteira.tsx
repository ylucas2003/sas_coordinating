import { useCallback, useState } from 'react';

import { Folha } from './Folha';

// "Por que a prova vem inteira" — a explicação do acervo histórico.
//
// O acervo anterior a 2019 é servido como a PÁGINA INTEIRA do caderno, e não
// como o recorte da questão: o recorte por heurística de bbox produzia crops
// vazios ou que capturavam a questão vizinha (docs/23 §12.1), e a transcrição
// de texto gerou dez rodadas de correção e ainda voltou em produção. A decisão
// está na migration 0033.
//
// Isso é ótimo para a confiabilidade e péssimo para quem não foi avisado: o
// aluno abre "Trigonometria · ITA 2011" e vê três questões, duas delas de outro
// assunto. Sem esta folha ele conclui que o filtro está quebrado.
//
// ⚠️ Aparece UMA vez, na primeira lista que traz questão em modo página — não
// ao entrar na aba. Onboarding fora de contexto é onboarding que ninguém lê. O
// "?" da tarja reabre para sempre, porque quem pulou da primeira vez precisa
// de um caminho de volta.

/**
 * O "não mostrar de novo" mora no `localStorage`, e não no banco.
 *
 * É preferência de leitura, não dado do aluno: não vale uma coluna, uma
 * migration nem uma ida ao servidor no caminho crítico da tela. O preço é que
 * ela é por aparelho — quem trocar de celular vê a explicação outra vez, o que
 * é o erro barato dos dois.
 *
 * ⚠️ `localStorage` levanta exceção em modo privativo de alguns navegadores.
 * Falhar aqui derrubaria a lista de questões inteira por causa de um aviso, e
 * por isso toda leitura e escrita é protegida — sem valor guardado, a folha
 * aparece de novo, que é o comportamento seguro.
 */
const CHAVE = 'sas:aluno:pagina-inteira-explicada';

function jaExplicado(): boolean {
  try {
    return window.localStorage.getItem(CHAVE) === '1';
  } catch {
    return false;
  }
}

export function usePaginaInteiraExplicada() {
  const [aberta, setAberta] = useState(false);
  const [visto, setVisto] = useState(jaExplicado);

  /** Chamada quando a lista traz a primeira questão em modo página. */
  const explicarSePrimeiraVez = useCallback(() => {
    if (jaExplicado()) return;
    setAberta(true);
  }, []);

  const reabrir = useCallback(() => setAberta(true), []);

  const fechar = useCallback((naoMostrarDeNovo: boolean) => {
    setAberta(false);
    if (!naoMostrarDeNovo) return;
    setVisto(true);
    try {
      window.localStorage.setItem(CHAVE, '1');
    } catch {
      // Sem armazenamento a folha volta na próxima abertura. É chato, não é bug.
    }
  }, []);

  return { aberta, visto, explicarSePrimeiraVez, reabrir, fechar };
}

interface Props {
  aberta: boolean;
  onFechar: (naoMostrarDeNovo: boolean) => void;
}

export function FolhaDaPaginaInteira({ aberta, onFechar }: Props) {
  return (
    <Folha
      aberta={aberta}
      titulo="Por que a prova vem inteira"
      altura="meio"
      onFechar={() => onFechar(false)}
      className="alu-folha-pagina"
    >
      <div className="alu-onb">
        {/* A página do caderno com a questão 23 destacada entre as vizinhas. É a
            explicação inteira num desenho: o aluno reconhece a forma antes de
            ler a frase. */}
        <svg
          className="alu-onb__desenho"
          viewBox="0 0 300 200"
          role="img"
          aria-label="Uma página do caderno de prova com três questões, e a do meio destacada"
        >
          <rect x="34" y="6" width="232" height="188" rx="8" fill="none" stroke="var(--alu-borda)" />
          <line x1="150" y1="22" x2="150" y2="178" stroke="var(--alu-borda)" />

          <rect x="46" y="22" width="90" height="42" rx="5" fill="none" stroke="var(--alu-borda)" />
          <text x="54" y="40" fontSize="13" fontWeight="700" fill="var(--alu-texto-2)">22</text>
          <path d="M54 48h74M54 55h56" stroke="var(--alu-borda)" strokeWidth="3" strokeLinecap="round" />

          <rect
            x="46"
            y="70"
            width="90"
            height="52"
            rx="5"
            fill="color-mix(in srgb, var(--alu-dado) 18%, transparent)"
            stroke="var(--alu-dado)"
            strokeWidth="1.5"
          />
          <text x="54" y="88" fontSize="14" fontWeight="800" fill="var(--alu-dado)">23</text>
          <path d="M54 96h74M54 104h74M54 112h48" stroke="var(--alu-dado)" strokeWidth="3" strokeLinecap="round" />

          <rect x="46" y="128" width="90" height="42" rx="5" fill="none" stroke="var(--alu-borda)" />
          <text x="54" y="146" fontSize="13" fontWeight="700" fill="var(--alu-texto-2)">24</text>
          <path d="M54 154h74M54 161h56" stroke="var(--alu-borda)" strokeWidth="3" strokeLinecap="round" />

          <path
            d="M164 30h90M164 40h78M164 50h90M164 60h64M164 78h90M164 88h84M164 98h52M164 116h90M164 126h74M164 144h90M164 154h66"
            stroke="var(--alu-borda)"
            strokeWidth="3"
            strokeLinecap="round"
          />
          <path d="M18 96q0-30 28-30" fill="none" stroke="var(--alu-dado)" strokeWidth="1.5" />
          <circle cx="18" cy="96" r="4" fill="var(--alu-dado)" />
        </svg>

        <h3 className="alu-onb__titulo">
          Classificamos por assunto.
          <br />O recorte vem depois.
        </h3>
        <p className="alu-onb__texto">
          As provas mais antigas aparecem como a página inteira do caderno — a questão que
          você procura está ali, junto de outras. Todo cartão avisa qual número procurar.
        </p>

        <button type="button" className="alu-tecla alu-tecla--larga" onClick={() => onFechar(true)}>
          Entendi
        </button>
        <button
          type="button"
          className="alu-tecla alu-tecla--fantasma alu-tecla--larga"
          onClick={() => onFechar(false)}
        >
          Ver de novo depois
        </button>
      </div>
    </Folha>
  );
}
