import type { ConfrontoAgendado, JogadorMercado, Selecao } from "@/types/dados";

export const RODADAS_CARTOLA_FILTRO = [2, 3] as const;
export type RodadaCartolaFiltro = (typeof RODADAS_CARTOLA_FILTRO)[number];

/** Janelas oficiais da Copa no Cartola FC (fase de grupos). */
export const INTERVALOS_RODADA_CARTOLA: Record<
  RodadaCartolaFiltro,
  { inicio: string; fim: string }
> = {
  2: { inicio: "2026-06-18", fim: "2026-06-23" },
  3: { inicio: "2026-06-24", fim: "2026-06-27" },
};

function hojeCalendario(): string {
  return new Date().toLocaleDateString("en-CA", { timeZone: "America/Sao_Paulo" });
}

export function normalizarDataCalendario(data: string | null | undefined): string | null {
  if (!data) return null;
  const d = data.trim().slice(0, 10);
  return /^\d{4}-\d{2}-\d{2}$/.test(d) ? d : null;
}

/** Classifica confronto pela data (intervalo Cartola), não pelo campo rodada do calendário. */
export function rodadaCartolaPorData(
  data: string | null | undefined,
): RodadaCartolaFiltro | null {
  const d = normalizarDataCalendario(data);
  if (!d) return null;
  for (const r of RODADAS_CARTOLA_FILTRO) {
    const { inicio, fim } = INTERVALOS_RODADA_CARTOLA[r];
    if (d >= inicio && d <= fim) return r;
  }
  return null;
}

export function dataNaRodadaCartola(
  data: string | null | undefined,
  rodada: number,
): boolean {
  return rodadaCartolaPorData(data) === rodada;
}

export function rodadaFiltroInicial(
  rodadaCartolaAtual: number | null | undefined,
): RodadaCartolaFiltro {
  const porData = rodadaCartolaPorData(hojeCalendario());
  if (porData) return porData;
  const hoje = hojeCalendario();
  if (hoje < INTERVALOS_RODADA_CARTOLA[2].inicio) return 2;
  if (hoje > INTERVALOS_RODADA_CARTOLA[3].fim) return 3;
  const r = Number(rodadaCartolaAtual) || 2;
  return r >= 3 ? 3 : 2;
}

export function mapaSelecoes(selecoes: Selecao[]): Map<string, Selecao> {
  return new Map(selecoes.map((s) => [s.selecao, s]));
}

export function confrontoRodada(
  selecao: Selecao | undefined,
  rodada: number,
): ConfrontoAgendado | null {
  if (!selecao) return null;
  const c = (selecao.confrontos_agendados ?? []).find((x) =>
    dataNaRodadaCartola(x.data, rodada),
  );
  return c ?? null;
}

export function jogadorNaRodada(
  j: JogadorMercado,
  mapa: Map<string, Selecao>,
  rodada: number,
): boolean {
  return confrontoRodada(mapa.get(j.selecao), rodada) != null;
}

export interface AdversarioRodada {
  sigla: string;
  escudo: string | null;
  data: string;
}

export function adversarioRodada(
  j: JogadorMercado,
  mapa: Map<string, Selecao>,
  rodada: number,
): AdversarioRodada | null {
  const c = confrontoRodada(mapa.get(j.selecao), rodada);
  if (!c) return null;
  return {
    sigla: c.adversario_sigla,
    escudo: c.adversario_escudo,
    data: c.data,
  };
}
