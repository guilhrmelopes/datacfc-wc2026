import type { PerformancePorSigla, PontuacaoCedida } from "@/types/dados";

export function formatarDataExibicao(data: string): string {
  if (!data) return "";
  const [ano, mes, dia] = data.split("-");
  return `${dia}/${mes}/${ano}`;
}

export function formatarDataCurta(data: string): string {
  if (!data) return "";
  const [, mes, dia] = data.split("-");
  return `${dia}/${mes}`;
}

export const OPCOES_FILTRO_RODADA = [
  { id: "1", label: "Rodada 1", rodadaGrupo: 1 },
  { id: "2", label: "Rodada 2", rodadaGrupo: 2 },
  { id: "3", label: "Rodada 3", rodadaGrupo: 3 },
  { id: "r32", label: "16 avos de final", rodadaGrupo: null },
  { id: "r16", label: "Oitavas de final", rodadaGrupo: null },
  { id: "qf", label: "Quartas de final", rodadaGrupo: null },
  { id: "sf", label: "Semifinal", rodadaGrupo: null },
  { id: "f", label: "Final", rodadaGrupo: null },
] as const;

export type FiltroRodadaId = (typeof OPCOES_FILTRO_RODADA)[number]["id"];

export function labelFiltroRodada(filtroId: string): string {
  return OPCOES_FILTRO_RODADA.find((o) => o.id === filtroId)?.label ?? filtroId;
}

export const FILTRO_PARA_FASE_ELIM: Record<string, string> = {
  r32: "1/16",
  r16: "1/8",
  qf: "1/4",
  sf: "1/2",
  f: "final",
};

export function ehFaseEliminatoria(filtroId: string): boolean {
  return filtroId in FILTRO_PARA_FASE_ELIM;
}

export function confrontosDoFiltroRodada<T extends { rodada: number }>(
  confrontos: T[],
  filtroId: string,
): T[] {
  const op = OPCOES_FILTRO_RODADA.find((o) => o.id === filtroId);
  if (!op?.rodadaGrupo) return [];
  return confrontos.filter((c) => c.rodada === op.rodadaGrupo);
}

export function confrontosDoFiltroEliminatoria<
  T extends { fase?: string },
>(confrontos: T[], filtroId: string): T[] {
  const fase = FILTRO_PARA_FASE_ELIM[filtroId];
  if (!fase) return [];
  if (filtroId === "f") {
    return confrontos.filter((c) => c.fase === "final" || c.fase === "bronze");
  }
  return confrontos.filter((c) => c.fase === fase);
}

export function chaveConfronto(mandante: string, visitante: string, data: string): string {
  return `${data}|${mandante}|${visitante}`;
}

export function obterPerformance(
  pontuacaoCedida: PontuacaoCedida,
  sigla: string,
): PerformancePorSigla | null {
  return pontuacaoCedida[sigla.trim().toUpperCase()] ?? null;
}

function valorMetrica(
  perf: PerformancePorSigla | null,
  bucket: string,
  tipo: "cedido" | "conquistado",
): number | null {
  const v = perf?.[bucket]?.[tipo]?.valor;
  return v === null || v === undefined ? null : v;
}

export interface ResumoConfronto {
  conqAta: number | null;
  cedAta: number | null;
}

export function resumoSelecao(
  pontuacaoCedida: PontuacaoCedida,
  sigla: string,
): ResumoConfronto {
  const perf = obterPerformance(pontuacaoCedida, sigla);
  return {
    conqAta: valorMetrica(perf, "ATA", "conquistado"),
    cedAta: valorMetrica(perf, "ATA", "cedido"),
  };
}

export function fmtResumo(v: number | null): string {
  return v === null ? "—" : v.toFixed(1);
}
