import { useState } from 'react';

import { useVestibulares } from '../../dados/aluno';
import { useDefinirVestibulares } from '../../hooks/mutacoes';

// O portão do primeiro acesso: contra qual edital este aluno está sendo medido.
//
// ⚠️ Por que ele é OBRIGATÓRIO e bloqueia o app (docs/36 §1.4):
// `vestibular_alvo_aluno` existe desde a migration 0001 e **nunca teve quem
// escrevesse nela** — 0 linhas em 05/09. Sem essa resposta, `GET /me/zona` cai
// na régua da casa para todo mundo, que é o contrário de "cada aluno contra o
// edital que persegue". Um banner dispensável seria respondido por ninguém, e a
// tabela continuaria vazia.
//
// ⚠️ A FOTO não está aqui, e a ausência é deliberada. Ela já é pedida no
// primeiro acesso por `componentes/perfil/LembreteFotoPerfil`, que tem a
// máquina de recorte (cover, zoom, arrasto) e a declaração de autorização —
// coisas que não se duplicam. O onboarding do vestibular roda antes; o diálogo
// da foto aparece na sequência, no mesmo primeiro acesso. Uma segunda tela de
// recorte divergiria da primeira no primeiro conserto.
//
// E a foto continua OPCIONAL enquanto o alvo é obrigatório: recusar uma imagem
// não pode barrar o acesso de um menor ao próprio boletim; não declarar o alvo
// deixa o produto sem régua.

const ALVOS = [
  {
    valor: 'ITA',
    nome: 'ITA',
    comoE: 'Instituto Tecnológico de Aeronáutica',
  },
  {
    valor: 'IME',
    nome: 'IME',
    comoE: 'Instituto Militar de Engenharia',
  },
] as const;

export function Onboarding() {
  const [escolhidos, setEscolhidos] = useState<string[]>([]);
  const definir = useDefinirVestibulares();

  const alternar = (valor: string) =>
    setEscolhidos((atual) =>
      atual.includes(valor) ? atual.filter((v) => v !== valor) : [...atual, valor],
    );

  return (
    <div className="alu-onboarding">
      <div className="alu-onboarding__cartao">
        <span className="alu-olho">Antes de começar</span>
        <h1 className="alu-onboarding__titulo">Você está mirando qual?</h1>
        <p className="alu-onboarding__texto">
          É o que define a sua régua: cada edital corta numa nota diferente, e sem saber o
          seu a gente só teria um número solto para te mostrar.
        </p>

        <div className="alu-onboarding__alvos">
          {ALVOS.map((alvo) => {
            const ativo = escolhidos.includes(alvo.valor);
            return (
              <button
                key={alvo.valor}
                type="button"
                className={`alu-onboarding__alvo${ativo ? ' is-ativo' : ''}`}
                aria-pressed={ativo}
                onClick={() => alternar(alvo.valor)}
              >
                <span className="alu-onboarding__alvo-nome">{alvo.nome}</span>
                <span className="alu-onboarding__alvo-como">{alvo.comoE}</span>
              </button>
            );
          })}
        </div>

        {/* Marcar os dois é comum e não é erro — quem mira ITA e IME é avaliado
            contra os dois, valendo o pior veredito (docs/36 §1.4). */}
        <p className="alu-onboarding__dica">
          Pode marcar os dois. Dá para mudar depois, no seu perfil.
        </p>

        {definir.isError && (
          <p className="alu-onboarding__erro" role="alert">
            Não consegui salvar sua escolha. Tente de novo.
          </p>
        )}

        <button
          type="button"
          className="alu-tecla alu-tecla--larga alu-onboarding__seguir"
          disabled={!escolhidos.length || definir.isPending}
          onClick={() => definir.mutate(escolhidos)}
        >
          {definir.isPending ? 'Salvando…' : 'Continuar'}
        </button>
      </div>
    </div>
  );
}

/**
 * O portão. Enquanto `completo` for false, o aluno não chega às telas.
 *
 * Devolve `null` enquanto carrega de propósito: piscar a Hoje e só então cobrir
 * com o onboarding é pior que meio segundo de nada, ainda mais quando o desvio
 * é obrigatório.
 */
export function PortaoDoOnboarding({ children }: { children: React.ReactNode }) {
  const { data, isPending, isError } = useVestibulares();

  if (isPending) return null;
  // Erro de rede não pode trancar o aluno do lado de fora do próprio boletim:
  // se a pergunta não pôde ser feita, ela fica para a próxima abertura.
  if (isError) return <>{children}</>;
  if (!data?.completo) return <Onboarding />;
  return <>{children}</>;
}
