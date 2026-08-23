import { NavLink } from 'react-router-dom';

/**
 * Abas da Administração.
 *
 * Contas, Auditoria e Importar saíram do menu principal e viraram abas daqui:
 * são as três tarefas de manutenção do sistema, feitas por quem administra e
 * não por quem acompanha turma. No rail elas competiam por atenção com as
 * telas de uso diário.
 *
 * São `NavLink` e não estado porque continuam sendo rotas próprias — cada uma
 * tem URL, histórico e link direto.
 */

const ABAS = [
  { para: '/administracao', label: 'Contas' },
  { para: '/auditoria', label: 'Auditoria' },
  { para: '/importar', label: 'Importar planilha' },
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
