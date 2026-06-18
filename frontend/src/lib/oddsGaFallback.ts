import type { OddsJogadorEntry } from "@/types/dados";

/**
 * P(marcar ou assistir) assumindo independência entre G e A.
 * Entrada/saída em escala 0–100 (mesma das colunas G% e A%).
 */
export function calcularGaPctDeG_e_A(gPct: number, aPct: number): number {
  const pg = gPct / 100;
  const pa = aPct / 100;
  const pga = pg + pa - pg * pa;
  return Math.round(pga * 1000) / 10;
}

export function gaPctEfetivo(odds: OddsJogadorEntry | null | undefined): number | null {
  if (!odds) return null;
  if (odds.ga_pct != null) return odds.ga_pct;
  if (odds.g_pct != null && odds.a_pct != null) {
    return calcularGaPctDeG_e_A(odds.g_pct, odds.a_pct);
  }
  return null;
}

export function gaPctCalculado(odds: OddsJogadorEntry | null | undefined): boolean {
  return (
    odds != null &&
    odds.g_pct != null &&
    odds.a_pct != null &&
    odds.odds_ga == null
  );
}

/** Preenche GA% derivado de G% + A% quando o mercado não traz odd combinada. */
export function enriquecerOddsRodada(
  odds: OddsJogadorEntry | null | undefined,
): OddsJogadorEntry | null {
  if (!odds) return null;
  if (odds.ga_pct != null) return odds;
  const ga = gaPctEfetivo(odds);
  if (ga == null) return odds;
  return { ...odds, ga_pct: ga };
}
