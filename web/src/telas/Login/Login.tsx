import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';

import * as api from '../../servicos/api';
import * as sessao from '../../servicos/sessao';
import { FormularioSenha } from './FormularioSenha';
import { Porta } from './Porta';
import type { Modo } from './Porta';

// Tela de login: duas portas, UM casco.
//
// ⚠️ O `.lp` institucional MORREU em 05/09/2026. Até então, clicar em "Sou da
// coordenação" trocava a PÁGINA INTEIRA por outro desenho — coluna dupla,
// logos, selo de 108 anos, manchete própria — e a coordenação parecia outro
// produto a um clique de distância. Foram apagados `PainelDireito.tsx`,
// `modos.ts` e as 625 linhas de `login.css`.
//
// Agora as duas portas são a mesma `Porta`, e só o painel da direita troca de
// conteúdo. A coordenação herda a cena, a marca e o cobogó — que é exatamente
// o que o brief pedia ao dizer que o login da coordenação é "a mesma fachada,
// outro ângulo". Antes isso era uma treliça desenhada à parte no painel velho;
// agora não precisa existir, porque a fachada já está lá.
//
// A porta é o CASCO e não conhece sessão nem API: o formulário entra como slot.
//
// ⚠️ O botão "Entrar com o Canvas" é só da porta do ALUNO. A coordenação não
// entra por lá — clicar levaria ao `?canvas=sem-conta`, que é uma recusa
// correta explicada de um jeito que não serviria para quem tem conta
// (docs/35 §11.6).

export function Login() {
  const navegar = useNavigate();
  const [params] = useSearchParams();
  // Canvas como identidade (docs/18 §4.2). O botão da porta do aluno só existe
  // se o servidor tiver a Developer Key; sem ela, ninguém entra por lá — e a
  // porta diz isso, em vez de ficar sem nada.
  const [ssoCanvas, setSsoCanvas] = useState(false);
  useEffect(() => {
    api.ssoCanvasDisponivel().then((r) => setSsoCanvas(r.disponivel)).catch(() => setSsoCanvas(false));
  }, []);

  // Motivos que o Canvas devolve quando a CHAVE está errada — não o usuário.
  // Aparecem porque o conserto é de quem administra, não de quem clicou.
  const MOTIVO_CANVAS: Record<string, string> = {
    unauthorized_client: 'a Developer Key do SAS está desligada no Canvas (Admin → Developer Keys → ON).',
    invalid_scope: 'a Developer Key não permite o escopo que o SAS pede.',
    invalid_request: 'a redirect URI configurada no Canvas não bate com a do servidor.',
  };
  const motivo = params.get('motivo') ?? '';
  const avisoCanvas = {
    cancelado: null,
    recusado: `O Canvas recusou o login: ${MOTIVO_CANVAS[motivo] ?? motivo}`,
    // Sem "ou entre com matrícula e senha": essa saída não existe mais.
    falhou: 'O Canvas não confirmou o login. Tente de novo em alguns instantes.',
    // A recusa certa (o SAS decide quem entra), dita de um jeito que ensina o
    // que fazer. Quem cria aluno é o sync do Canvas, a partir da matrícula no
    // curso de simulados — e é isso que a mensagem manda conferir.
    //
    // ⚠️ Sem ecoar o e-mail na mensagem, embora ele fosse o texto mais útil
    // possível: ele viajaria na query string, e query string entra em
    // histórico de navegador e em log de acesso do nginx.
    'sem-conta':
      'Sua conta do Canvas não está na lista de alunos do SAS. A lista vem da sua matrícula no '
      + 'curso de simulados do ITA/IME no Canvas: matrícula nova leva alguns minutos para chegar '
      + 'aqui. Se a sua já está lá, fale com a coordenação.',
  }[params.get('canvas') ?? ''] ?? null;

  const [modo, setModo] = useState<Modo>('aluno');

  function entrar(dados: api.RespostaAutenticacao) {
    sessao.iniciar(dados);
    navegar('/', { replace: true });
  }

  return (
    <Porta
      modo={modo}
      ssoCanvas={ssoCanvas}
      avisoCanvas={avisoCanvas}
      onTrocarModo={setModo}
      formulario={(
        <FormularioSenha
          tipo="coordenador"
          onEntrar={entrar}
          exemploEmail="nome@aridesa.com.br"
          /* Não há "primeiro acesso" nem "esqueci a senha": a senha da
             coordenação é redefinida pelo administrador, em
             /administracao/contas, e entregue pelo canal do colégio
             (docs/35 §11.7). */
          ajuda="Esqueceu a senha? Peça ao administrador do SAS para redefinir."
          aposErro={(
            /* DUAS PORTAS, e elas são diferentes: a coordenação entra por
               e-mail e senha; o aluno entra SÓ pelo Canvas. Quem errar de
               porta precisa saber para onde ir — senão tenta a mesma senha
               três vezes e conclui que a conta foi bloqueada. Só aparece
               DEPOIS de uma falha: antes dela seria ruído na porta certa. */
            <button type="button" className="porta__link" onClick={() => setModo('aluno')}>
              É aluno? A entrada de aluno é pelo Canvas.
            </button>
          )}
        />
      )}
    />
  );
}
