import type { JogadorMercado, OddsJogadorEntry } from "@/types/dados";

/** Peso do Rating histórico (eliminatórias) vs sinal de odds da rodada. */
export const POTENCIAL_ALPHA = 0.65;

/**
 * Sinal de odds 0–100 por posição (Rodada 1):
 * - GOL: SG%
 * - ZAG: 65% SG% + 35% GA%
 * - LAT: 55% SG% + 45% GA%
 * - MEI / ATA: GA%
 */
export function sinalOddsRodada(
  bucket: string,
  odds: OddsJogadorEntry | null | undefined,
): number | null {
  const ga = odds?.ga_pct ?? null;
  const sg = odds?.sg_pct ?? null;

  switch (bucket) {
    case "GOL":
      return sg;
    case "ZAG":
      if (sg !== null && ga !== null) return 0.65 * sg + 0.35 * ga;
      return sg ?? ga;
    case "LAT":
      if (sg !== null && ga !== null) return 0.55 * sg + 0.45 * ga;
      return sg ?? ga;
    case "MEI":
    case "ATA":
      return ga;
    default:
      return ga ?? sg;
  }
}

/** Rating histórico com fallbacks para garantir índice em todo elenco. */
export function ratingBase(j: JogadorMercado): number {
  if (j.rating_recomendacao > 0) return j.rating_recomendacao;

  if (j.media_geral != null && j.media_geral > 0) {
    return Math.min(100, Math.round((j.media_geral / 12) * 1000) / 10);
  }

  const jogos = Math.max(j.jogos_num, 1);
  let pts = j.goals * 8 + j.goal_assist * 5;
  if (j.bucket_posicao === "GOL" || j.bucket_posicao === "LAT" || j.bucket_posicao === "ZAG") {
    pts += j.clean_sheet * 5;
  }
  const proxy = (pts / jogos / 12) * 100;
  return Math.min(100, Math.max(1, Math.round(proxy * 10) / 10));
}

/**
 * Potencial para Rodada 1 (0–100):
 * P = α × Rating + (1 − α) × O  quando há odds;
 * P = Rating (ou proxy) quando não há odds.
 */
export function calcularPotencialRodada(
  j: JogadorMercado,
  odds: OddsJogadorEntry | null | undefined,
): number {
  const r = ratingBase(j);
  const o = sinalOddsRodada(j.bucket_posicao, odds);
  if (o !== null) {
    return Math.round((POTENCIAL_ALPHA * r + (1 - POTENCIAL_ALPHA) * o) * 10) / 10;
  }
  return Math.round(r * 10) / 10;
}

export function tooltipPotencialRodada(
  j: JogadorMercado,
  odds: OddsJogadorEntry | null | undefined,
  potencial: number,
): string {
  const r = ratingBase(j);
  const o = sinalOddsRodada(j.bucket_posicao, odds);
  if (o !== null) {
    return `Potencial para Rodada: ${potencial.toFixed(1)} (${Math.round(POTENCIAL_ALPHA * 100)}% Rating ${r.toFixed(1)} + ${Math.round((1 - POTENCIAL_ALPHA) * 100)}% odds ${o.toFixed(1)})`;
  }
  return `Potencial para Rodada: ${potencial.toFixed(1)} (Rating ${r.toFixed(1)} — sem odds na rodada)`;
}
