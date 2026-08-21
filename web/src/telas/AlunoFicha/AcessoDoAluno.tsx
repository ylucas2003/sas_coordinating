import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import * as api from '../../servicos/api';
import type { Aluno } from '../../tipos/dominio';

/**
 * O aluno cria a própria senha validando matrícula + e-mail do Canvas. Aqui a
 * coordenação corrige o e-mail e libera um novo primeiro acesso (zera a senha)
 * quando o aluno perde o acesso ou está sem e-mail cadastrado.
 */
export function AcessoDoAluno({ aluno }: { aluno: Aluno }) {
  const [email, setEmail] = useState('');
  const [status, setStatus] = useState('');

  const resetar = useMutation({
    mutationFn: (corpo: { email?: string }) =>
      api.resetarAcessoAluno(aluno.id, corpo) as Promise<{ email?: string }>,
  });

  async function liberar() {
    const confirmado = window.confirm(
      'Zerar a senha deste aluno? Ele precisará criar uma nova pelo "Primeiro acesso" na tela de login.',
    );
    if (!confirmado) return;

    setStatus('');
    try {
      const corpo = email.trim() ? { email: email.trim() } : {};
      const resp = await resetar.mutateAsync(corpo);
      setStatus(
        `Acesso liberado. E-mail para validação: ${resp.email || '— (sem e-mail; corrija acima)'}.`,
      );
    } catch (e) {
      setStatus(`Erro ao liberar acesso: ${(e as Error).message}`);
    }
  }

  return (
    <section className="card aluno-ficha__nao-imprimir">
      <div className="section">
        <div className="section__title">Acesso do aluno</div>
        <div className="section__subtitle">
          {`E-mail do Canvas: ${aluno.email || '— não cadastrado'}. O aluno usa matrícula + este e-mail para criar a senha na tela de login.`}
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <input
            className="dialog__input"
            type="email"
            style={{ maxWidth: 320 }}
            placeholder={aluno.email || 'e-mail não cadastrado — informe para corrigir'}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <button className="btn" disabled={resetar.isPending} onClick={liberar}>
            Liberar primeiro acesso
          </button>
        </div>
        {status && <div className="section__subtitle" style={{ marginTop: 8 }}>{status}</div>}
      </div>
    </section>
  );
}
