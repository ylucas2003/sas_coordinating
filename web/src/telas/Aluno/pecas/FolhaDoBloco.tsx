import { useEffect, useId, useRef, useState } from 'react';
import type { FormEvent } from 'react';

import {
  DIAS_DA_SEMANA,
  TAMANHO_MAXIMO_DO_ROTULO,
  alternarDia,
  duracaoPorExtenso,
  duracoesDisponiveis,
  minutosDe,
  problemaDoRascunho,
  rascunhoDe,
  rascunhoNovo,
  terminaAs,
} from '../../../dominio/horarioEstudos';
import type { Rascunho } from '../../../dominio/horarioEstudos';
import { useApagarBloco, useAtualizarBloco, useCriarBlocos } from '../../../hooks/horarioEstudos';
import { ErroApi } from '../../../servicos/http';
import type { BlocoDeEstudo } from '../../../tipos/horarioEstudos';
import { Folha } from './Folha';
import { Icone } from './Icone';

// A folha de "Novo bloco" — o bloco lido como UMA FRASE, de cima para baixo:
//
//   TODA   seg ter qua qui sex
//   ÀS     19:00
//   POR    1h30
//   ESTUDAR  Termodinâmica
//
// Em vez de um formulário de quatro campos soltos, porque a frase é o gesto que
// o plano quer facilitar: "segunda a sexta, 19h, 1h30" é UM bloco criado em cinco
// dias, e ler a ordem do dia à duração como uma sentença mostra isso sem
// explicar (docs/42 §3, §4.2).
//
// Os mesmos campos servem para EDITAR, com duas diferenças: o dia passa a ser
// de escolha única (um bloco existente é de UM dia — editar o de quarta não mexe
// no de segunda), e aparece o "Apagar bloco".
//
// ⚠️ O ERRO DO SERVIDOR É MOSTRADO COMO CHEGA. `problemaDoRascunho` adianta o
// aviso para o aluno não esperar uma ida e volta por um erro que já se via, mas
// quem decide é o servidor — e a frase dele (409 de sobreposição, 422 de valor)
// já vem em português, escrita para esta tela.
//
// ⚠️ "APAGAR" NÃO É VERMELHO. A cor ALERTA do produto é da etiqueta de distância
// e do que está abaixo do corte; apagar um bloco do próprio horário não é nada
// disso. É um botão quieto, com confirmação em duas etapas.

interface Props {
  /** `null` = bloco novo; senão, o bloco em edição. */
  bloco: BlocoDeEstudo | null;
  /** O dia em que o aluno tocou no "+", para um bloco novo. */
  diaInicial: number;
  /** A semana inteira, para avisar de sobreposição antes de enviar. */
  existentes: BlocoDeEstudo[];
  onFechar: () => void;
}

function mensagemDoErro(erro: unknown): string {
  if (erro instanceof ErroApi && erro.message) return erro.message;
  return 'Não deu para salvar agora. Tente de novo.';
}

export function FolhaDoBloco({ bloco, diaInicial, existentes, onFechar }: Props) {
  const idDoFormulario = useId();
  const editando = bloco !== null;
  const [rascunho, setRascunho] = useState<Rascunho>(() =>
    bloco ? rascunhoDe(bloco) : rascunhoNovo(diaInicial),
  );
  // O aviso de "falta preencher" só aparece depois da primeira tentativa de
  // salvar: mostrá-lo antes xinga o aluno por um campo que ele nem chegou a tocar.
  const [tentou, setTentou] = useState(false);
  const [erroDoServidor, setErroDoServidor] = useState<string | null>(null);
  const [confirmandoApagar, setConfirmandoApagar] = useState(false);
  const blocoDeApagar = useRef<HTMLDivElement>(null);

  // O corpo da folha rola por dentro e o rodapé é fixo: no celular a confirmação
  // nascia meio escondida sob o "Salvar bloco", e o aluno tinha de adivinhar que
  // havia mais para rolar. `nearest` só rola o necessário — nada, se já cabe.
  useEffect(() => {
    if (confirmandoApagar) blocoDeApagar.current?.scrollIntoView({ block: 'nearest' });
  }, [confirmandoApagar]);

  const criar = useCriarBlocos();
  const atualizar = useAtualizarBloco();
  const apagar = useApagarBloco();
  const ocupado = criar.isPending || atualizar.isPending || apagar.isPending;

  const problema = problemaDoRascunho(rascunho, existentes, bloco?.id);
  const termina = terminaAs(rascunho.hora, rascunho.duracao);
  // Conflito e meia-noite se mostram ao vivo (a causa é o que o aluno acabou de
  // mexer); "falta preencher" espera a tentativa.
  const avisoAoVivo =
    problema && (problema.includes('já tem') || problema.includes('meia-noite')) ? problema : null;
  const aviso = erroDoServidor ?? (tentou ? problema : avisoAoVivo);

  function mudar(parte: Partial<Rascunho>) {
    setRascunho((atual) => ({ ...atual, ...parte }));
    setErroDoServidor(null);
  }

  function escolherDia(dia: number) {
    mudar({ dias: editando ? [dia] : alternarDia(rascunho.dias, dia) });
  }

  function salvar(ev: FormEvent) {
    ev.preventDefault();
    if (ocupado) return;
    setTentou(true);
    if (problema) return;

    const comum = {
      horaInicio: rascunho.hora,
      duracaoMinutos: rascunho.duracao,
      rotulo: rascunho.rotulo.trim(),
    };
    const aoFalhar = (erro: unknown) => setErroDoServidor(mensagemDoErro(erro));

    if (bloco) {
      atualizar.mutate(
        { id: bloco.id, remendo: { ...comum, diaSemana: rascunho.dias[0] } },
        { onSuccess: onFechar, onError: aoFalhar },
      );
    } else {
      criar.mutate(
        { ...comum, diasSemana: rascunho.dias },
        { onSuccess: onFechar, onError: aoFalhar },
      );
    }
  }

  function apagarOBloco() {
    if (!bloco || ocupado) return;
    apagar.mutate(bloco.id, {
      onSuccess: onFechar,
      onError: (erro) => setErroDoServidor(mensagemDoErro(erro)),
    });
  }

  const quantosDias = rascunho.dias.length;
  const rotuloDoBotao = editando
    ? 'Salvar bloco'
    : quantosDias > 1
      ? `Criar ${quantosDias} blocos`
      : 'Salvar bloco';

  return (
    <Folha
      aberta
      altura="cheio"
      titulo={editando ? 'Editar bloco' : 'Novo bloco'}
      onFechar={onFechar}
      rodape={
        <div className="alu-hor-rodape">
          <button
            type="submit"
            form={idDoFormulario}
            className="alu-tecla alu-tecla--larga"
            disabled={ocupado}
          >
            {ocupado ? 'Salvando…' : rotuloDoBotao}
          </button>
          <button type="button" className="alu-hor-quieto" onClick={onFechar} disabled={ocupado}>
            Cancelar
          </button>
        </div>
      }
    >
      <form id={idDoFormulario} className="alu-hor-form" onSubmit={salvar} noValidate>
        <fieldset className="alu-hor-campo">
          <legend className="alu-olho">{editando ? 'Dia' : 'Toda'}</legend>
          <div className="alu-hor-chips alu-hor-chips--dias">
            {DIAS_DA_SEMANA.map((dia) => {
              const ativo = rascunho.dias.includes(dia.numero);
              return (
                <button
                  key={dia.numero}
                  type="button"
                  className={`alu-hor-chip${ativo ? ' is-ativo' : ''}`}
                  aria-pressed={ativo}
                  aria-label={dia.nome}
                  onClick={() => escolherDia(dia.numero)}
                >
                  {dia.curto}
                </button>
              );
            })}
          </div>
        </fieldset>

        <div className="alu-hor-campo">
          <label className="alu-olho" htmlFor={`${idDoFormulario}-hora`}>
            Às
          </label>
          <input
            id={`${idDoFormulario}-hora`}
            className="alu-hor-hora"
            type="time"
            value={rascunho.hora}
            onChange={(ev) => mudar({ hora: ev.target.value })}
            aria-invalid={minutosDe(rascunho.hora) == null && tentou}
          />
        </div>

        <fieldset className="alu-hor-campo">
          <legend className="alu-olho">Por</legend>
          <div className="alu-hor-chips">
            {duracoesDisponiveis(bloco?.duracaoMinutos).map((minutos) => {
              const ativo = rascunho.duracao === minutos;
              return (
                <button
                  key={minutos}
                  type="button"
                  className={`alu-hor-chip alu-hor-chip--larga${ativo ? ' is-ativo' : ''}`}
                  aria-pressed={ativo}
                  onClick={() => mudar({ duracao: minutos })}
                >
                  {duracaoPorExtenso(minutos)}
                </button>
              );
            })}
          </div>
        </fieldset>

        <div className="alu-hor-campo">
          <label className="alu-olho" htmlFor={`${idDoFormulario}-rotulo`}>
            Estudar
          </label>
          <input
            id={`${idDoFormulario}-rotulo`}
            className="alu-hor-rotulo"
            type="text"
            value={rascunho.rotulo}
            maxLength={TAMANHO_MAXIMO_DO_ROTULO}
            placeholder="O que você vai estudar?"
            enterKeyHint="done"
            autoComplete="off"
            onChange={(ev) => mudar({ rotulo: ev.target.value })}
            aria-invalid={tentou && !rascunho.rotulo.trim()}
          />
          {/* O fim do bloco é a conta que o aluno faria de cabeça — mostrá-la
              evita um 20:30 digitado errado. Some quando não há conta a fazer. */}
          <p className="alu-hor-dica">
            {termina ? `Termina às ${termina}` : ' '}
          </p>
        </div>

        {aviso && (
          <p className="alu-erro" role="alert">
            {aviso}
          </p>
        )}

        {editando && (
          <div className="alu-hor-apagar" ref={blocoDeApagar}>
            {confirmandoApagar ? (
              <>
                <p className="alu-vazio">
                  Apagar “{bloco.rotulo}” desse dia? Os outros dias não mudam.
                </p>
                <div className="alu-hor-apagar__botoes">
                  <button
                    type="button"
                    className="alu-tecla alu-tecla--fantasma alu-tecla--pequena"
                    onClick={apagarOBloco}
                    disabled={ocupado}
                  >
                    <Icone nome="lixeira" tamanho={16} />
                    Apagar
                  </button>
                  <button
                    type="button"
                    className="alu-hor-quieto"
                    onClick={() => setConfirmandoApagar(false)}
                    disabled={ocupado}
                  >
                    Manter
                  </button>
                </div>
              </>
            ) : (
              <button
                type="button"
                className="alu-hor-quieto"
                onClick={() => setConfirmandoApagar(true)}
                disabled={ocupado}
              >
                Apagar bloco
              </button>
            )}
          </div>
        )}
      </form>
    </Folha>
  );
}
