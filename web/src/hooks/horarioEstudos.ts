// Hooks do horário de estudos (docs/42).
//
// Leitura e escrita no mesmo arquivo, como `hooks/cantina.ts`: a superfície é
// pequena e de um assunto só, e separar em `consultas`/`mutacoes` faria a
// invalidação atravessar arquivos para nada.

import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import * as api from '../servicos/api';
import type { NovoBloco, RemendoDeBloco } from '../tipos/horarioEstudos';

export const chavesHorarioEstudos = {
  semana: ['me', 'horario-estudos'] as const,
};

/**
 * A semana inteira do aluno.
 *
 * `staleTime: 0` como o resto do `/me`: é dado do próprio aluno, que pode ter
 * mexido em outro aparelho. Falha de consulta NÃO é "semana vazia" — as telas
 * leem `isError` antes de `blocos.length === 0`.
 */
export function useHorarioDeEstudos() {
  return useQuery({
    queryKey: chavesHorarioEstudos.semana,
    queryFn: api.horarioEstudosMe,
    staleTime: 0,
  });
}

/** Criar, editar e apagar mudam a mesma coisa — a semana —, então invalidam a mesma chave. */
function useAposMudarASemana() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: chavesHorarioEstudos.semana });
}

export function useCriarBlocos() {
  const invalidar = useAposMudarASemana();
  return useMutation({
    mutationFn: (bloco: NovoBloco) => api.criarBlocosDeEstudo(bloco),
    onSuccess: invalidar,
  });
}

export function useAtualizarBloco() {
  const invalidar = useAposMudarASemana();
  return useMutation({
    mutationFn: ({ id, remendo }: { id: string; remendo: RemendoDeBloco }) =>
      api.atualizarBlocoDeEstudo(id, remendo),
    onSuccess: invalidar,
  });
}

export function useApagarBloco() {
  const invalidar = useAposMudarASemana();
  return useMutation({
    mutationFn: (id: string) => api.apagarBlocoDeEstudo(id),
    onSuccess: invalidar,
  });
}

/**
 * O relógio da tela, com resolução de minuto.
 *
 * "Próximo bloco" depende da hora, e uma tela aberta às 17:59 que não se
 * atualiza continuaria dizendo "daqui a 1 min" às 19:30. O intervalo é de 30 s
 * e não de 60 para o rótulo virar no minuto certo, e não até um minuto atrasado.
 *
 * É o relógio do APARELHO, de propósito: o colégio e os alunos estão num fuso só
 * (docs/42 §6, item 4).
 */
export function useAgora(intervaloMs = 30_000): Date {
  const [agora, setAgora] = useState(() => new Date());
  useEffect(() => {
    const id = window.setInterval(() => setAgora(new Date()), intervaloMs);
    return () => window.clearInterval(id);
  }, [intervaloMs]);
  return agora;
}
