import { oddsVigentes, temCopa } from "@/lib/copaJogador";
import {
  FATOR_ML_GAMMA,
  fatorMlSelecao,
  type ContextoMlRodada,
} from "@/lib/fatorMoneylineRodada";
import { labelOddsPosicional, sinalOddsPosicional } from "@/lib/oddsPosicional";
import {
  calcularRatingJogador,
  type EscalasRating,
} from "@/lib/ratingJogador";
import type { JogadorMercado, OddsJogadorEntry } from "@/types/dados";

/**
 * SCORE (coluna SCORE) — índice híbrido 0–100 para a rodada (somente após estreia na Copa).
 * 65% Rating + 35% odds posicionais, com ML e status.
 */

export const POTENCIAL_ALPHA = 0.65;

/** @deprecated use sinalOddsPosicional */
export function sinalOddsRodada(
  bucket: string,
  odds: OddsJogadorEntry | null | undefined,
): number | null {
  return sinalOddsPosicional(bucket, odds);
}

export const FATOR_STATUS: Record<number, number> = {
  6: 1.0,
  2: 0.85,
  7: 0.72,
  5: 0,
  3: 0,
};

const FATOR_STATUS_PADRAO = 0.72;

export function ratingBase(
  j: JogadorMercado,
  escalas: EscalasRating,
  _mlCtx?: ContextoMlRodada | null,
  _siglaSelecao?: string | null,
  odds?: OddsJogadorEntry | null,
): number {
  return calcularRatingJogador(j, escalas, null, null, odds);
}

export function fatorStatus(statusId: number): number {
  return FATOR_STATUS[statusId] ?? FATOR_STATUS_PADRAO;
}

export function calcularPotencialBruto(
  j: JogadorMercado,
  odds: OddsJogadorEntry | null | undefined,
  escalas: EscalasRating,
  confiarOdds = false,
  mlCtx?: ContextoMlRodada | null,
  siglaSelecao?: string | null,
): number | null {
  if (!temCopa(j)) return null;

  const sigla = siglaSelecao ?? j.sigla;
  const fatorMl = fatorMlSelecao(sigla, mlCtx);
  const oddsValidas = confiarOdds ? odds : oddsVigentes(j, odds) ? odds : null;
  const r = ratingBase(j, escalas, null, sigla, oddsValidas);
  if (r <= 0) return null;

  const o = sinalOddsPosicional(j.bucket_posicao, oddsValidas);
  if (o !== null) {
    const oAjust = Math.round(o * Math.pow(fatorMl, FATOR_ML_GAMMA) * 10) / 10;
    return Math.round((POTENCIAL_ALPHA * r + (1 - POTENCIAL_ALPHA) * oAjust) * 10) / 10;
  }
  return Math.round(r * 10) / 10;
}

/** SCORE da rodada (ex-Potencial). */
export function calcularPotencialRodada(
  j: JogadorMercado,
  odds: OddsJogadorEntry | null | undefined,
  escalas: EscalasRating,
  confiarOdds = false,
  mlCtx?: ContextoMlRodada | null,
  siglaSelecao?: string | null,
): number | null {
  const bruto = calcularPotencialBruto(
    j,
    odds,
    escalas,
    confiarOdds,
    mlCtx,
    siglaSelecao,
  );
  if (bruto === null) return null;
  const fator = fatorStatus(j.status_id);
  return Math.round(bruto * fator * 10) / 10;
}

export function tooltipPotencialRodada(
  j: JogadorMercado,
  odds: OddsJogadorEntry | null | undefined,
  potencial: number | null,
  escalas: EscalasRating,
  confiarOdds = false,
  mlCtx?: ContextoMlRodada | null,
  siglaSelecao?: string | null,
): string {
  if (!temCopa(j) || potencial === null) {
    return "Sem partidas na Copa 2026";
  }

  const sigla = siglaSelecao ?? j.sigla;
  const fatorMl = fatorMlSelecao(sigla, mlCtx);
  const oddsValidas = confiarOdds ? odds : oddsVigentes(j, odds) ? odds : null;
  const r = ratingBase(j, escalas, null, sigla, oddsValidas);
  const o = sinalOddsPosicional(j.bucket_posicao, oddsValidas);
  const bruto = calcularPotencialBruto(j, odds, escalas, confiarOdds, mlCtx, sigla) ?? 0;
  const fator = fatorStatus(j.status_id);
  const oddsLabel = labelOddsPosicional(j.bucket_posicao);

  let base: string;
  if (o !== null) {
    const oAjust = Math.round(o * Math.pow(fatorMl, FATOR_ML_GAMMA) * 10) / 10;
    if (fatorMl !== 1) {
      base = `${Math.round(POTENCIAL_ALPHA * 100)}% Rating ${r.toFixed(1)} + ${Math.round((1 - POTENCIAL_ALPHA) * 100)}% ${oddsLabel} ${o.toFixed(1)}→${oAjust.toFixed(1)} (ML ×${fatorMl.toFixed(2)})`;
    } else {
      base = `${Math.round(POTENCIAL_ALPHA * 100)}% Rating ${r.toFixed(1)} + ${Math.round((1 - POTENCIAL_ALPHA) * 100)}% ${oddsLabel} ${o.toFixed(1)}`;
    }
  } else {
    base =
      fatorMl !== 1
        ? `Rating ${r.toFixed(1)} (ML ×${fatorMl.toFixed(2)}; sem props na rodada)`
        : `Rating ${r.toFixed(1)} (sem odds na rodada)`;
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
    return `SCORE: ${potencial.toFixed(1)} (${base}; bruto ${bruto.toFixed(1)} × ${Math.round(fator * 100)}% ${status})`;
  }

  return `SCORE: ${potencial.toFixed(1)} (${base})`;
}
