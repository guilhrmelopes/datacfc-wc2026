import { temCopa } from "@/lib/copaJogador";
import { calcularRatingJogador, type EscalasRating } from "@/lib/ratingJogador";
import type { JogadorMercado, OddsJogadorEntry } from "@/types/dados";

/**
 * Potencial para Rodada (coluna ⓘ) — índice híbrido 0–100 (somente após estreia na Copa).
 */

export const POTENCIAL_ALPHA = 0.65;

export const PESOS_ODDS: Record<
  string,
  { sg: number; ga: number; descricao: string }
> = {
  GOL: { sg: 1, ga: 0, descricao: "SG% (clean sheet)" },
  ZAG: { sg: 0.65, ga: 0.35, descricao: "65% SG% + 35% GA%" },
  LAT: { sg: 0.55, ga: 0.45, descricao: "55% SG% + 45% GA%" },
  MEI: { sg: 0, ga: 1, descricao: "GA% (marcar ou assistir)" },
  ATA: { sg: 0, ga: 1, descricao: "GA% (marcar ou assistir)" },
};

export const FATOR_STATUS: Record<number, number> = {
  6: 1.0,
  2: 0.85,
  7: 0.72,
  5: 0,
  3: 0,
};

const FATOR_STATUS_PADRAO = 0.72;

export function sinalOddsRodada(
  bucket: string,
  odds: OddsJogadorEntry | null | undefined,
): number | null {
  const ga = odds?.ga_pct ?? null;
  const sg = odds?.sg_pct ?? null;
  const pesos = PESOS_ODDS[bucket];

  if (!pesos) return ga ?? sg;

  if (pesos.ga === 0) return sg;
  if (pesos.sg === 0) return ga;

  if (sg !== null && ga !== null) {
    return pesos.sg * sg + pesos.ga * ga;
  }
  return sg ?? ga;
}

export function ratingBase(j: JogadorMercado, escalas: EscalasRating): number {
  return calcularRatingJogador(j, escalas);
}

export function fatorStatus(statusId: number): number {
  return FATOR_STATUS[statusId] ?? FATOR_STATUS_PADRAO;
}

export function calcularPotencialBruto(
  j: JogadorMercado,
  odds: OddsJogadorEntry | null | undefined,
  escalas: EscalasRating,
): number | null {
  if (!temCopa(j)) return null;

  const r = ratingBase(j, escalas);
  if (r <= 0) return null;

  const o = sinalOddsRodada(j.bucket_posicao, odds);
  if (o !== null) {
    return Math.round((POTENCIAL_ALPHA * r + (1 - POTENCIAL_ALPHA) * o) * 10) / 10;
  }
  return Math.round(r * 10) / 10;
}

export function calcularPotencialRodada(
  j: JogadorMercado,
  odds: OddsJogadorEntry | null | undefined,
  escalas: EscalasRating,
): number | null {
  const bruto = calcularPotencialBruto(j, odds, escalas);
  if (bruto === null) return null;
  const fator = fatorStatus(j.status_id);
  return Math.round(bruto * fator * 10) / 10;
}

export function tooltipPotencialRodada(
  j: JogadorMercado,
  odds: OddsJogadorEntry | null | undefined,
  potencial: number | null,
  escalas: EscalasRating,
): string {
  if (!temCopa(j) || potencial === null) {
    return "Sem partidas na Copa 2026";
  }

  const r = ratingBase(j, escalas);
  const o = sinalOddsRodada(j.bucket_posicao, odds);
  const bruto = calcularPotencialBruto(j, odds, escalas) ?? 0;
  const fator = fatorStatus(j.status_id);
  const pesos = PESOS_ODDS[j.bucket_posicao];

  let base: string;
  if (o !== null) {
    const oddsLabel = pesos?.descricao ?? "odds";
    base = `${Math.round(POTENCIAL_ALPHA * 100)}% Rating ${r.toFixed(1)} + ${Math.round((1 - POTENCIAL_ALPHA) * 100)}% ${oddsLabel} ${o.toFixed(1)}`;
  } else {
    base = `Rating ${r.toFixed(1)} (sem odds na rodada)`;
  }

  if (fator < 1) {
    const status =
      j.status_id === 2
        ? "Dúvida"
        : j.status_id === 7
          ? "Nulo"
          : j.status_id === 5
            ? "Suspenso"
            : j.status_id === 3
              ? "Lesionado"
              : "Indisponível";
    return `Potencial: ${potencial.toFixed(1)} (${base}; bruto ${bruto.toFixed(1)} × ${Math.round(fator * 100)}% ${status})`;
  }

  return `Potencial para Rodada: ${potencial.toFixed(1)} (${base})`;
}
