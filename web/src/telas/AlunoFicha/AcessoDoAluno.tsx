import { useEffect, useState } from 'react';
import { Dialogo } from '../../componentes/dialogos/Dialogo';
import { useRemoverFotoDeAluno } from '../../hooks/mutacoes';
import type { Aluno } from '../../tipos/dominio';

/**
 * O que a coordenação vê e opera do acesso de UM aluno, na ficha dele.
 *
 * O campo de e-mail e o botão "Liberar primeiro acesso" SAÍRAM em 04/09
 * (docs/35 §11.5), com a rota `POST /alunos/{id}/resetar-acesso` que eles
 * chamavam: não existe mais senha de aluno para zerar. Sobrou aqui a única
 * ação que continua de pé — tirar do ar uma foto de perfil imprópria.
 *
 * O botão da foto aparece só quando há foto, em vez de aparecer cinza: é a
 * mesma regra que `telas/Administracao/Administracao.tsx` (~281) aplica à
 * coluna de administrador — botão desabilitado convida a clicar e ensina a
 * esperar recusa da tela.
 */
export function AcessoDoAluno({ aluno }: { aluno: Aluno }) {
  const [status, setStatus] = useState('');
  const [confirmando, setConfirmando] = useState(false);
  const removerFoto = useRemoverFotoDeAluno();

  async function tirarFoto() {
    setConfirmando(false);
    setStatus('');
    try {
      await removerFoto.mutateAsync(aluno.id);
      setStatus('Foto removida.');
    } catch (e) {
      setStatus(`Erro ao remover a foto: ${(e as Error).message}`);
    }
  }

  // Esc cancela — e o rodapé promete isso por escrito. A saída barata tem de
  // existir justamente na ação irreversível: quem abriu por engano precisa de
  // um jeito de sair que não passe perto do botão vermelho.
  //
  // ⚠️ `capture` porque a ficha escuta ←/→ no `window` para andar no recorte,
  // e o mesmo diálogo aberto não pode deixar uma tecla trocar de aluno por
  // baixo dele (`AlunoFicha.tsx`, o guarda do `.dialog-overlay`).
  useEffect(() => {
    if (!confirmando) return;
    function aoTeclar(ev: KeyboardEvent) {
      if (ev.key !== 'Escape') return;
      ev.stopPropagation();
      setConfirmando(false);
    }
    window.addEventListener('keydown', aoTeclar, true);
    return () => window.removeEventListener('keydown', aoTeclar, true);
  }, [confirmando]);

  return (
    <section className="ficha-peca aluno-ficha__nao-imprimir">
      <h2 className="ficha-olho">Acesso do aluno</h2>
      <p className="ficha-peca__nota ficha-peca__nota--bloco">
        O aluno entra <b>só pelo Canvas</b>, e vê as próprias notas contra a mesma régua
        desta tela. Quem não consegue entrar é quem não tem conta ligada no Canvas, e isso
        se resolve lá — não há nada a liberar aqui. Quem tem e quem não tem está em
        Administração › Contas, na seção “Acesso dos alunos”.
      </p>
      {/* O e-mail continua na ficha porque ainda serve para uma coisa: é o
          endereço do lembrete de simulado (lembretes/aplicacoes/aluno_simulado.py).
          Quem o preenche é o sync do Canvas (canvas_sync/sincronizar.py). */}
      <p className="ficha-peca__nota ficha-peca__nota--bloco">
        {`E-mail do Canvas: ${aluno.email || '— não cadastrado'} — usado para o lembrete de simulado, não para entrar.`}
      </p>

      {aluno.temFoto && (
        <button
          type="button"
          className="btn btn--ghost ficha-acesso__botao"
          disabled={removerFoto.isPending}
          onClick={() => setConfirmando(true)}
        >
          Remover a foto de perfil
        </button>
      )}

      {status && <p className="ficha-peca__nota ficha-peca__nota--bloco">{status}</p>}

      {/* A ÚNICA ação destrutiva desta tela, e era a única que não usava a peça
          do sistema: `window.confirm` — o alerta nativo do navegador, com a
          tipografia do sistema operacional, dois botões genéricos e nenhum
          jeito de dizer o que se perde. Num produto que tem diálogo próprio
          com diff e confirmação, ele lia como se a tela tivesse escapado do
          produto (docs/39 §3 · fase 4, defeito 4). */}
      {confirmando && (
        <Dialogo
          titulo="Remover a foto de perfil?"
          subtitulo={aluno.nome}
          onFechar={() => setConfirmando(false)}
          rodape={
            <>
              <span className="ficha-foto__dica">Esc cancela</span>
              <button type="button" className="btn btn--ghost" onClick={() => setConfirmando(false)}>
                Cancelar
              </button>
              <button
                type="button"
                className="btn btn--primary btn--perigo"
                disabled={removerFoto.isPending}
                onClick={tirarFoto}
              >
                Remover · irreversível
              </button>
            </>
          }
        >
          {/* O diff do sistema, com uma linha só: é a peça que toda outra
              escrita deste produto mostra antes de confirmar, e o que ela
              afirma aqui é o estado depois — a foto sai, as iniciais entram.
              Reusar as classes `.dialog__diff-*` em vez de desenhar um par
              novo é o que faz esta confirmação LER como as outras. */}
          <div className="dialog__diff">
            <div className="dialog__diff-linha">
              <span className="dialog__diff-campo">Foto</span>
              <span className="dialog__diff-de">enviada pelo aluno</span>
              <span className="dialog__diff-seta"> → </span>
              <span className="dialog__diff-para">iniciais</span>
            </div>
          </div>

          {/* O raio de explosão em palavras: o que sai, o que fica, e o que o
              aluno pode fazer depois. É a informação que o `confirm` nativo
              não tinha onde colocar. */}
          <p className="section__subtitle">
            O arquivo é apagado do servidor e não volta. No lugar dele o aluno passa a
            aparecer com as iniciais, aqui e na área dele.
          </p>
          <p className="section__subtitle">
            O resto do cadastro não muda, e ele pode enviar outra foto a qualquer momento.
          </p>
        </Dialogo>
      )}
    </section>
  );
}
