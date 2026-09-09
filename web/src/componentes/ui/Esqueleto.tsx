/**
 * O vão de uma tela que ainda está chegando pela rede.
 *
 * Existe por causa da divisão do bundle (docs/40 §12.1.4): telas pesadas —
 * o banco de questões, o chat, a leitura de QR — deixaram de vir no arquivo de
 * entrada e passam a ser buscadas no primeiro uso. Entre o clique e a chegada
 * há um instante, e o que preenche esse instante decide se a divisão foi
 * percebida como "mais rápido" ou como "piscou".
 *
 * ⚠️ **Nunca tela branca, e nunca spinner.** O casco já está desenhado — rail,
 * topbar, barra inferior —, então o que falta é só o miolo; um fallback de
 * página inteira apagaria o que já estava certo na tela. É a mesma régua do
 * esqueleto de `CartaoDeCampo` (`campo.css`): reservar o lugar em vez de
 * inventar conteúdo, porque número chutado que depois muda é pior que vão.
 *
 * A frase é a mesma de `.empty-state` que as telas de varredura já usam. Duas
 * palavras diferentes para o mesmo estado ensinariam que são estados
 * diferentes.
 */
export function Esqueleto() {
  return (
    <div className="tela">
      <div className="empty-state" role="status" aria-live="polite">
        Carregando…
      </div>
    </div>
  );
}
