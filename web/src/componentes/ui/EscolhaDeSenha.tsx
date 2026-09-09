import { useId, useState } from 'react';

/**
 * "Gerar uma" ou "Definir esta" — a escolha de senha das duas telas de conta
 * (docs/40 §12.7).
 *
 * ⚠️ **Isto existe porque "ver a senha" não é possível.** O pedido foi
 * conseguir dizer à cantina qual é a senha dela; a resposta não pode ser
 * mostrar a senha guardada, porque não há senha guardada — o hash é PBKDF2 de
 * mão única, e passar a guardar texto legível exporia contas que alcançam
 * nome, turma e restrição alimentar de menores. Quem DEFINE, sabe: é a mesma
 * necessidade, resolvida sem trocar de regime.
 *
 * ⚠️ **As regras daqui são cortesia, não defesa.** A validação de verdade é do
 * servidor (`app/senha_definida.py`), e quem manda `curl` não passa por este
 * componente. O que ele faz é evitar a viagem até o 422 — e por isso o texto
 * das regras é o mesmo dos dois lados: duas redações da mesma regra viram duas
 * regras na cabeça de quem lê.
 */

/** O mesmo piso de `app/senha_definida.py`. Mudou lá, muda aqui. */
export const MINIMO_DE_CARACTERES = 12;

export interface EscolhaDeSenha {
  /** O que vai no corpo: `null` = "sorteie uma". */
  senha: string | null;
  /** Falso enquanto a senha digitada não serve — o botão de salvar espera. */
  pronta: boolean;
}

export function useEscolhaDeSenha(): [EscolhaDeSenha, React.ReactNode] {
  const id = useId();
  const [definir, setDefinir] = useState(false);
  const [texto, setTexto] = useState('');
  const [visivel, setVisivel] = useState(false);

  const curta = texto.trim().length < MINIMO_DE_CARACTERES;
  const escolha: EscolhaDeSenha = definir
    ? { senha: texto.trim(), pronta: !curta }
    : { senha: null, pronta: true };

  const campo = (
    <fieldset className="senha-escolha">
      <legend className="senha-escolha__legenda">Senha</legend>

      <label className="senha-escolha__opcao" htmlFor={`${id}-gerar`}>
        <input
          id={`${id}-gerar`} type="radio" name={`${id}-modo`}
          checked={!definir} onChange={() => setDefinir(false)}
        />
        <span>
          Gerar uma
          {/* A frase que já estava no subtítulo do diálogo, e ela continua
              valendo: a senha sorteada aparece uma vez e some. */}
          <small className="senha-escolha__ajuda">
            Aparece uma única vez depois de salvar.
          </small>
        </span>
      </label>

      <label className="senha-escolha__opcao" htmlFor={`${id}-definir`}>
        <input
          id={`${id}-definir`} type="radio" name={`${id}-modo`}
          checked={definir} onChange={() => setDefinir(true)}
        />
        <span>
          Definir esta
          <small className="senha-escolha__ajuda">
            Você fica sabendo qual é — é o jeito de poder passá-la adiante.
          </small>
        </span>
      </label>

      {definir && (
        <div className="senha-escolha__campo">
          <input
            className="input"
            type={visivel ? 'text' : 'password'}
            value={texto}
            autoComplete="new-password"
            onChange={(e) => setTexto(e.target.value)}
            aria-label="Senha"
            aria-invalid={curta || undefined}
          />
          {/* "Mostrar" e não um olho: é o mesmo controle do formulário de
              login (`Login/FormularioSenha.tsx`), e trocar o desenho aqui
              faria a mesma ação ter duas caras no mesmo produto. */}
          <button
            type="button" className="btn btn--fino"
            onClick={() => setVisivel((v) => !v)}
          >
            {visivel ? 'Ocultar' : 'Mostrar'}
          </button>
        </div>
      )}

      {definir && (
        <p className={`senha-escolha__regra${curta ? ' senha-escolha__regra--falha' : ''}`}>
          {/* O contador aparece SEMPRE que o campo está aberto, e não só no
              erro: saber quanto falta enquanto digita é diferente de descobrir
              que faltava depois de tentar salvar. */}
          Pelo menos {MINIMO_DE_CARACTERES} caracteres
          {texto.trim() ? ` · ${texto.trim().length}` : ''}
          {'. '}
          Não pode conter o e-mail da conta.
        </p>
      )}
    </fieldset>
  );

  return [escolha, campo];
}
