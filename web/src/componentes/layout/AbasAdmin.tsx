import { NavLink } from 'react-router-dom';

/**
 * Abas da Administração.
 *
 * Contas, Auditoria e Integrações saíram do menu principal e viraram abas
 * daqui: são as tarefas de manutenção do sistema, feitas por quem administra e
 * não por quem acompanha turma. No rail elas competiam por atenção com as
 * telas de uso diário.
 *
 * "Importar planilha" saiu da fila em 03/09/2026, quando a entrada por planilha
 * foi aposentada (docs/32 §2.4). A rota `/importar` continua existindo e
 * explica o que mudou — mas oferecer a aba seria oferecer um caminho de escrita
 * que o produto deixou de ter.
 *
 * "Calibração" entrou em 04/09/2026 com o índice de importância (docs/34 §5 ·
 * D2): é o primeiro número de calibração que a coordenação edita sem deploy, e
 * mexer nele reordena o ranking de assuntos que o aluno vê.
 *
 * São `NavLink` e não estado porque continuam sendo rotas próprias — cada uma
 * tem URL, histórico e link direto.
 */

const ABAS = [
  { para: '/administracao', label: 'Contas' },
  { para: '/auditoria', label: 'Auditoria' },
  { para: '/integracoes', label: 'Integrações' },
  { para: '/calibracao', label: 'Calibração' },
];

export function AbasAdmin() {
  return (
    <div className="abas">
      {ABAS.map((a) => (
        <NavLink
          key={a.para}
          to={a.para}
          end
          className={({ isActive }) => `aba${isActive ? ' is-active' : ''}`}
        >
          {a.label}
        </NavLink>
      ))}
    </div>
  );
}
