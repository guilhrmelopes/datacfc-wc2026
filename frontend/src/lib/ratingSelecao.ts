import type { Selecao } from "@/types/dados";
import { valorNumericoOuNull } from "@/lib/exibirValor";

export function estreouCopa(s: Selecao): boolean {
  return s.competicao === "Copa 2026" && (s.metricas_coletivas.J ?? 0) > 0;
}

function percentil(valor: number, amostra: number[]): number {
  const vals = [...amostra].sort((a, b) => a - b);
  if (!vals.length) return 0;
  const abaixo = vals.filter((v) => v < valor).length;
  const iguais = vals.filter((v) => v === valor).length;
  const pct = ((abaixo + iguais * 0.5) / vals.length) * 100;
  return Math.round(Math.max(1, Math.min(100, pct)) * 10) / 10;
}

const METRICAS_RATING: (keyof Selecao["metricas_coletivas"])[] = [
  "goals_team_match",
  "possession_percentage_team",
  "expected_goals_team",
  "clean_sheet_team",
  "total_tackle_team",
];

const METRICAS_MENOR_MELHOR: Set<keyof Selecao["metricas_coletivas"]> = new Set([
  "goals_conceded_team_match",
  "expected_goals_conceded_team",
  "total_yel_card_team",
  "total_red_card_team",
]);

/**
 * Rating 0–100 da seleção na Copa (percentil médio das métricas coletivas).
 * Hosts e demais times passam a ter rating após estrear, sem depender do ELO das eliminatórias.
 */
export function calcularRatingSelecaoCopa(s: Selecao, pool: Selecao[]): number | null {
  if (!estreouCopa(s)) return null;

  const estrearam = pool.filter(estreouCopa);
  if (estrearam.length === 0) return null;

  const percentis: number[] = [];

  for (const campo of METRICAS_RATING) {
    const valor = valorNumericoOuNull(s.metricas_coletivas[campo]);
    if (valor === null) continue;
    const amostra = estrearam
      .map((x) => valorNumericoOuNull(x.metricas_coletivas[campo]))
      .filter((v): v is number => v !== null);
    if (amostra.length === 0) continue;
    percentis.push(percentil(valor, amostra));
  }

  for (const campo of METRICAS_MENOR_MELHOR) {
    const valor = valorNumericoOuNull(s.metricas_coletivas[campo]);
    if (valor === null) continue;
    const amostra = estrearam
      .map((x) => valorNumericoOuNull(x.metricas_coletivas[campo]))
      .filter((v): v is number => v !== null);
    if (amostra.length === 0) continue;
    percentis.push(100 - percentil(valor, amostra));
  }

  if (percentis.length === 0) return null;
  const media = percentis.reduce((a, b) => a + b, 0) / percentis.length;
  return Math.round(media * 10) / 10;
}

/** Rating Copa (scouts) ou Elo eloratings.net antes da estreia. */
export function ratingSelecaoExibicao(s: Selecao, pool: Selecao[]): number | null {
  return calcularRatingSelecaoCopa(s, pool) ?? s.rating_elo_100 ?? null;
}
