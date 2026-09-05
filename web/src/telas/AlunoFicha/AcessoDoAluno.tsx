import { useState } from 'react';
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
  const removerFoto = useRemoverFotoDeAluno();

  async function tirarFoto() {
    const confirmado = window.confirm(
      `Remover a foto de perfil de ${aluno.nome}? Ele pode enviar outra a qualquer momento.`,
    );
    if (!confirmado) return;
    setStatus('');
    try {
      await removerFoto.mutateAsync(aluno.id);
      setStatus('Foto removida.');
    } catch (e) {
      setStatus(`Erro ao remover a foto: ${(e as Error).message}`);
    }
  }

  return (
    <section className="card aluno-ficha__nao-imprimir">
      <div className="section">
        <div className="section__title">Acesso do aluno</div>
        <div className="section__subtitle">
          O aluno entra <b>só pelo Canvas</b>. Quem não consegue entrar é quem não tem conta
          ligada no Canvas, e isso se resolve lá — não há nada a liberar aqui. Quem tem e quem
          não tem está em Administração › Contas, na seção “Acesso dos alunos”.
        </div>
        {/* O e-mail continua na ficha porque ainda serve para uma coisa: é o
            endereço do lembrete de simulado (lembretes/aplicacoes/aluno_simulado.py).
            Quem o preenche é o sync do Canvas (canvas_sync/sincronizar.py). */}
        <div className="section__subtitle">
          {`E-mail do Canvas: ${aluno.email || '— não cadastrado'} — usado para o lembrete de simulado, não para entrar.`}
        </div>
        {aluno.temFoto && (
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <button className="btn btn--ghost" disabled={removerFoto.isPending} onClick={tirarFoto}>
              Remover foto de perfil
            </button>
          </div>
        )}
        {status && <div className="section__subtitle" style={{ marginTop: 8 }}>{status}</div>}
      </div>
    </section>
  );
}
