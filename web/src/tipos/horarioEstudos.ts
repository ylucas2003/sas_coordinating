// Espelha `api/app/schemas/horario_estudos.py` (docs/42). Mudou o schema
// Pydantic, mude aqui — é o que faz `diaSemana` virar `dia_semana` no build, e
// não em produção.

/**
 * Um bloco da semana de estudo que o aluno montou. Autodeclarado e privado: não
 * vira XP nem sequência, e a coordenação não lê (docs/42 §0).
 */
export interface BlocoDeEstudo {
  id: string;
  /** ISO: 1 = segunda … 7 = domingo. O `getDay()` do JS é 0 = domingo — a
   *  conversão mora em `dominio/horarioEstudos.ts::diaIso`, e só lá. */
  diaSemana: number;
  /** "19:00". Resolução de minuto, sem segundos. */
  horaInicio: string;
  duracaoMinutos: number;
  /** Texto livre do aluno, até 80 caracteres. */
  rotulo: string;
}

export interface HorarioDeEstudos {
  /** Por dia e hora. Vazio é o estado mais comum. */
  blocos: BlocoDeEstudo[];
}

/** Criar é por LISTA de dias: "seg a sex, 19h, 1h30" é um gesto, e o servidor o
 *  grava como um INSERT só — tudo ou nada. */
export interface NovoBloco {
  diasSemana: number[];
  horaInicio: string;
  duracaoMinutos: number;
  rotulo: string;
}

/** Campo ausente não é mexido. Editar o bloco de um dia não mexe nos outros. */
export interface RemendoDeBloco {
  diaSemana?: number;
  horaInicio?: string;
  duracaoMinutos?: number;
  rotulo?: string;
}
