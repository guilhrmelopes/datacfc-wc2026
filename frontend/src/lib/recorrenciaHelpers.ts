import type { PerformancePorSigla, PontuacaoCedida } from "@/types/dados";

export function formatarDataExibicao(data: string): string {
  if (!data) return "";
  const [ano, mes, dia] = data.split("-");
  return `${dia}/${mes}/${ano}`;
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
