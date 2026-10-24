import { useId, useState } from 'react';

import type { TemaDaFolha } from '../../../dominio/horarioEstudosFolha';
import * as sessao from '../../../servicos/sessao';
import { useTema } from '../../../servicos/tema';
import type { BlocoDeEstudo } from '../../../tipos/horarioEstudos';
import { MENSAGEM_GENERICA, exportarHorario } from '../exportarHorario';
import type { SaidaDoHorario } from '../exportarHorario';
import { Bloco } from './Bloco';
import { Icone } from './Icone';

// "Levar o horário" — PDF, imagem e Excel, no tema DIA ou NOITE (docs/42).
//
// ⚠️ O TEMA DO ARQUIVO É ESCOLHA DE QUEM EXPORTA, e começa no tema que o aluno está
// usando agora — é o que ele espera ver. Mas é uma escolha SÓ do arquivo: trocar aqui
// para "Noite" não escurece o app. Por isso não chama `useTema().trocar`: o estado é
// local, e some quando o bloco desmonta.
//
// ⚠️ O seletor é o do casco (`.alu-tema`, "Dia" / "Noite", com sol e lua), com o MESMO
// CSS — não uma cópia dele. Um segundo desenho para a mesma escolha faria o site ter
// dois jeitos de escolher o tema.
//
// ⚠️ UMA SAÍDA POR VEZ. Gerar o PNG a 2× e o PDF a 3× é trabalho de canvas de alguns
// décimos de segundo num celular, e dois cliques seguidos gerariam dois arquivos sobre
// o mesmo canvas. Enquanto uma sai, as outras ficam desabilitadas — e o botão que está
// trabalhando diz "Gerando…" em vez de parecer morto.

const TEMAS: Array<{ valor: TemaDaFolha; rotulo: string; icone: 'sol' | 'lua' }> = [
  { valor: 'dia', rotulo: 'Dia', icone: 'sol' },
  { valor: 'noite', rotulo: 'Noite', icone: 'lua' },
];

const SAIDAS: Array<{ saida: SaidaDoHorario; rotulo: string }> = [
  { saida: 'pdf', rotulo: 'PDF' },
  { saida: 'png', rotulo: 'Imagem' },
  { saida: 'xlsx', rotulo: 'Excel' },
];

export function ExportarHorario({ blocos }: { blocos: BlocoDeEstudo[] }) {
  const grupo = useId();
  const { tema: temaDoApp } = useTema();
  // Começa no tema em uso; depois é do aluno.
  const [tema, setTema] = useState<TemaDaFolha>(temaDoApp);
  const [fazendo, setFazendo] = useState<SaidaDoHorario | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  async function exportar(saida: SaidaDoHorario) {
    if (fazendo) return;
    setFazendo(saida);
    setErro(null);
    try {
      await exportarHorario({ saida, tema, blocos, nome: sessao.nome() });
    } catch (e) {
      // `ErroDeExportacao` e os de `baixarDaApi` já são frases em português; qualquer
      // outra coisa que escape vira a mensagem genérica, nunca um texto de motor de JS.
      setErro(e instanceof Error && e.message ? e.message : MENSAGEM_GENERICA);
    } finally {
      setFazendo(null);
    }
  }

  return (
    <Bloco olho="Levar o horário" className="alu-hor-saidas">
      <fieldset className="alu-tema-campo">
        <legend className="alu-conta__rotulo">Tema do arquivo</legend>
        <div className="alu-tema">
          {TEMAS.map((op) => (
            <label key={op.valor} className={`alu-tema__opcao${tema === op.valor ? ' is-ativa' : ''}`}>
              <input
                className="alu-so-leitor"
                type="radio"
                name={`${grupo}-tema`}
                value={op.valor}
                checked={tema === op.valor}
                onChange={() => setTema(op.valor)}
              />
              <Icone nome={op.icone} tamanho={18} />
              {op.rotulo}
            </label>
          ))}
        </div>
      </fieldset>

      <div className="alu-hor-saidas__botoes">
        {SAIDAS.map(({ saida, rotulo }) => (
          <button
            key={saida}
            type="button"
            className="alu-hor-saida"
            disabled={fazendo !== null}
            aria-busy={fazendo === saida}
            onClick={() => void exportar(saida)}
          >
            <Icone nome="baixar" tamanho={18} />
            {fazendo === saida ? 'Gerando…' : rotulo}
          </button>
        ))}
      </div>

      <p className="alu-hor-dica">
        O PDF sai numa página só, a imagem serve para compartilhar, e o Excel traz a grade e a
        lista. Todos saem no tema escolhido.
      </p>

      {erro && (
        <p className="alu-erro" role="alert">
          {erro}
        </p>
      )}
    </Bloco>
  );
}
