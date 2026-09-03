import { Link } from 'react-router-dom';

import { Icone } from './Icone';

// O cabeçalho dos três campos de Estudar — Banco, Estatísticas, Meu progresso.
//
// O `‹` fica NA MESMA LINHA do título, dentro de um quadrado de 44px, e não
// numa linha de texto acima ("← Estudar"). Três razões, e a primeira é a que
// decidiu:
//
//  1. O desenho é assim, nas três telas e nos dois artboards. O elo de texto
//     acima empurrava o título para baixo da dobra a 390px, e o título é a
//     coisa que diz ao aluno onde ele está.
//  2. Alvo de toque: o quadrado tem `--alu-toque` de lado; o elo de texto tinha
//     a altura da linha e a largura da palavra.
//  3. O `‹` é chevron, não seta. A seta promete "desfazer"; o chevron diz
//     "subir um nível", que é o que ele de fato faz.
//
// O `aria-label` nomeia o destino em vez de dizer "voltar": quem navega por
// leitor de tela ouve para onde vai, não que está recuando.

interface Props {
  titulo: string;
  /** Para onde o `‹` sobe. Default: o menu de Estudar. */
  para?: string;
  /** Como o destino se chama, para o leitor de tela. */
  destino?: string;
}

export function CabecaDoCampo({ titulo, para = '/estudar', destino = 'Estudar' }: Props) {
  return (
    <header className="alu-cabeca">
      <Link className="alu-cabeca__voltar" to={para} aria-label={`Voltar para ${destino}`}>
        <Icone nome="chevron_esquerda" tamanho={20} />
      </Link>
      <h1 className="alu-titulo-tela alu-cabeca__titulo">{titulo}</h1>
    </header>
  );
}
