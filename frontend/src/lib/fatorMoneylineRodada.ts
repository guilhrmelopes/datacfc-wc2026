import {
  dataNaRodadaCartola,
  rodadaCartolaPorData,
} from "@/lib/rodadaMercado";
import type { EventoOddsArmazenado, OddsArmazenamentoData } from "@/lib/oddsRodada";

/** Expoente suave — evita penalizar zebras de forma extrema. */
export const FATOR_ML_BETA = 0.4;
export const FATOR_ML_MIN = 0.55;
export const FATOR_ML_MAX = 1.08;
/** Ajuste parcial das props individuais pelo contexto do time. */
export const FATOR_ML_GAMMA = 0.5;

export interface ContextoMlRodada {
  pVitPorSigla: Map<string, number>;
  pMediana: number;
}

function mediana(vals: number[]): number {
  if (vals.length === 0) return 0;
  const ordenado = [...vals].sort((a, b) => a - b);
  const meio = Math.floor(ordenado.length / 2);
  return ordenado.length % 2 === 1
    ? ordenado[meio]
    : (ordenado[meio - 1] + ordenado[meio]) / 2;
}

function hojeCalendario(): string {
  return new Date().toLocaleDateString("en-CA", { timeZone: "America/Sao_Paulo" });
}

/** P(vitória) por seleção nos confrontos futuros armazenados (sem filtro de rodada Cartola). */
export function compilarContextoMlProximo(
  armazenamento: OddsArmazenamentoData | null | undefined,
): ContextoMlRodada | null {
  const eventos = armazenamento?.eventos;
  if (!eventos) return null;

  const hoje = hojeCalendario();
  const pVitPorSigla = new Map<string, number>();
  const probsRodada: number[] = [];

  for (const ev of Object.values(eventos) as EventoOddsArmazenado[]) {
    const dataEvento = ev.data?.trim();
    if (!dataEvento || dataEvento < hoje) continue;

    const pHome = ev.p_vit_home;
    const pAway = ev.p_vit_away;
    const sigHome = ev.sigla_mandante?.toUpperCase();
    const sigAway = ev.sigla_visitante?.toUpperCase();
    if (pHome == null || pAway == null || !sigHome || !sigAway) continue;

    pVitPorSigla.set(sigHome, pHome);
    pVitPorSigla.set(sigAway, pAway);
    probsRodada.push(pHome, pAway);
  }

  if (probsRodada.length === 0) return null;
  return { pVitPorSigla, pMediana: mediana(probsRodada) };
}

/** @deprecated use compilarContextoMlProximo — mantido para Recorrência/outros. */
export function compilarContextoMlRodada(
  armazenamento: OddsArmazenamentoData | null | undefined,
  rodada: number,
): ContextoMlRodada | null {
  const eventos = armazenamento?.eventos;
  if (!eventos) return null;

  const pVitPorSigla = new Map<string, number>();
  const probsRodada: number[] = [];

  for (const ev of Object.values(eventos) as EventoOddsArmazenado[]) {
    const dataEvento = ev.data ?? null;
    if (!dataNaRodadaCartola(dataEvento, rodada)) continue;
    if (rodadaCartolaPorData(dataEvento) !== rodada) continue;

    const pHome = ev.p_vit_home;
    const pAway = ev.p_vit_away;
    const sigHome = ev.sigla_mandante?.toUpperCase();
    const sigAway = ev.sigla_visitante?.toUpperCase();
    if (pHome == null || pAway == null || !sigHome || !sigAway) continue;

    pVitPorSigla.set(sigHome, pHome);
    pVitPorSigla.set(sigAway, pAway);
    probsRodada.push(pHome, pAway);
  }

  if (probsRodada.length === 0) return null;
  return { pVitPorSigla, pMediana: mediana(probsRodada) };
}

export function fatorRodadaMl(pVit: number, pMediana: number): number {
  if (pMediana <= 0 || pVit <= 0) return 1;
  const bruto = Math.pow(pVit / pMediana, FATOR_ML_BETA);
  return (
    Math.round(Math.min(FATOR_ML_MAX, Math.max(FATOR_ML_MIN, bruto)) * 1000) /
    1000
  );
}

export function fatorMlSelecao(
  sigla: string | null | undefined,
  ctx: ContextoMlRodada | null | undefined,
): number {
  if (!sigla || !ctx) return 1;
  const pVit = ctx.pVitPorSigla.get(sigla.toUpperCase());
  if (pVit == null) return 1;
  return fatorRodadaMl(pVit, ctx.pMediana);
}

export function pVitSelecaoRodada(
  sigla: string | null | undefined,
  ctx: ContextoMlRodada | null | undefined,
): number | null {
  if (!sigla || !ctx) return null;
  return ctx.pVitPorSigla.get(sigla.toUpperCase()) ?? null;
}
