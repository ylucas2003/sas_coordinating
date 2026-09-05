import { useNavigate } from 'react-router-dom';

import type * as api from '../../servicos/api';
import * as sessao from '../../servicos/sessao';
import { FormularioSenha } from './FormularioSenha';
import { Porta } from './Porta';

// A porta da cantina — `/login-cantina`.
//
// URL própria e não um terceiro modo de `/login`, e a razão é de produto: quem
// trabalha na cantina recebe UM endereço da coordenação e o salva. Uma terceira
// aba na porta do aluno cobraria de 900 alunos a existência de um público de
// duas pessoas, e o brief é explícito em não dar peso igual a coisas de peso
// diferente.
//
// Reusa a `Porta` inteira — cena, marca e manchete. Não porque dá menos
// trabalho, mas porque a cantina faz parte do mesmo produto: uma tela de login
// desenhada à parte diria que ela é um puxadinho, que foi exatamente o defeito
// que o `.lp` institucional da coordenação tinha antes de morrer (Porta.tsx).
//
// ⚠️ O SSO do Canvas não entra aqui de propósito. A cantina não tem conta no
// Canvas do colégio, e o botão levaria ao `?canvas=sem-conta` — uma recusa
// correta explicada de um jeito que não serviria para quem tem conta.

export function LoginCantina() {
  const navegar = useNavigate();

  function entrar(dados: api.RespostaAutenticacao) {
    sessao.iniciar(dados);
    // Para a raiz, como as outras portas: quem decide qual casco montar é o
    // `RotaProtegida` do App, a partir do tipo da sessão. Mandar direto para
    // `/cardapios` daqui duplicaria essa decisão em dois lugares.
    navegar('/', { replace: true });
  }

  return (
    <Porta
      modo="cantina"
      ssoCanvas={false}
      avisoCanvas={null}
      formulario={(
        <FormularioSenha
          tipo="cantina"
          onEntrar={entrar}
          exemploEmail="cantina@aridesa.com.br"
          ajuda="Esqueceu a senha? Peça ao administrador do SAS para redefinir."
        />
      )}
    />
  );
}
