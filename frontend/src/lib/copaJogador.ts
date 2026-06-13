import type {
  JogadorMercado,
  OddsJogadorEntry,
  PerformancePorSigla,
  PontuacaoCedida,
} from "@/types/dados";

/** Jogador com pelo menos 1 partida na Copa 2026 (fase de grupos). */
export function temCopa(j: JogadorMercado): boolean {
  return (j.copa_jogos_num ?? 0) > 0;
}

export function mediaGeralCopa(j: JogadorMercado): number | null {
  if (!temCopa(j)) return null;
  return j.copa_media_geral ?? null;
}

export function mediaBaseCopa(j: JogadorMercado): number | null {
  if (!temCopa(j)) return null;
  return j.copa_media_base ?? null;
}

export function xgXaPor90Copa(j: JogadorMercado): number | null {
  if (!temCopa(j) || !j.copa_mins_played) return null;
  const xg = j.copa_xg ?? 0;
  const xa = j.copa_xa ?? 0;
  return ((xg + xa) / j.copa_mins_played) * 90;
}

/**
 * Odds vigentes para exibição:
 * - quem ainda não estreou: odds atuais (próximo jogo);
 * - quem já jogou: só odds do ADV listado no mercado.
 */
export function oddsVigentes(
  j: JogadorMercado,
  odds: OddsJogadorEntry | null | undefined,
): boolean {
  if (!odds) return false;
  const prox = j.proximo_adversario_sigla?.trim().toUpperCase();
  if (!prox) return true;
  const oddsAdv = odds.adversario_sigla?.trim().toUpperCase();
  if (!oddsAdv) return !temCopa(j);
  return oddsAdv === prox;
}

/** @deprecated use oddsVigentes */
export const oddsProximoAdversario = oddsVigentes;

/** Cedido pelo adversário no bucket do jogador (Recorrência — HUB Seleções). */
export function cedidoAdversarioCopa(
  j: JogadorMercado,
  pontuacao: PontuacaoCedida,
): number | null {
  const adv = j.proximo_adversario_sigla?.trim().toUpperCase();
  if (!adv) return null;
  const perf = pontuacao[adv] as PerformancePorSigla | null | undefined;
  if (!perf) return null;
  const bucket = j.bucket_posicao as keyof PerformancePorSigla;
  const valor = perf[bucket]?.cedido?.valor;
  return valor === null || valor === undefined ? null : valor;
}
