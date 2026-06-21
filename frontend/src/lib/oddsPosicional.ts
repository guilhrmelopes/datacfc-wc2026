import { gaPctEfetivo } from "@/lib/oddsGaFallback";
import type { OddsJogadorEntry } from "@/types/dados";

/**
 * Sinal de odds 0–100 por posição — única definição para Rating e SCORE.
 * GOL: SG% · MEI/ATA: G% + A% · LAT/ZAG: média de G%, A% e SG%.
 */
export function sinalOddsPosicional(
  bucket: string,
  odds: OddsJogadorEntry | null | undefined,
): number | null {
  if (!odds) return null;
  const g = odds.g_pct ?? null;
  const a = odds.a_pct ?? null;
  const sg = odds.sg_pct ?? null;

  if (bucket === "GOL") return sg;

  if (bucket === "MEI" || bucket === "ATA") {
    if (g !== null && a !== null) {
      return Math.round((0.55 * g + 0.45 * a) * 10) / 10;
    }
    return g ?? a ?? gaPctEfetivo(odds);
  }

  if (bucket === "LAT" || bucket === "ZAG") {
    const partes = [g, a, sg].filter((v): v is number => v !== null);
    if (partes.length === 0) return sg ?? gaPctEfetivo(odds);
    return Math.round((partes.reduce((s, v) => s + v, 0) / partes.length) * 10) / 10;
  }

  return gaPctEfetivo(odds) ?? sg;
}

/** Descrição legível para tooltips. */
export function labelOddsPosicional(bucket: string): string {
  if (bucket === "GOL") return "SG%";
  if (bucket === "MEI" || bucket === "ATA") return "G% + A%";
  if (bucket === "LAT" || bucket === "ZAG") return "G%, A% e SG%";
  return "odds";
}
