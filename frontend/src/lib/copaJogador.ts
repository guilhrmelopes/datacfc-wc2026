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

/** Hoje no fuso do calendário (America/Sao_Paulo), formato YYYY-MM-DD. */
function hojeCalendario(): string {
  return new Date().toLocaleDateString("en-CA", { timeZone: "America/Sao_Paulo" });
}

/**
 * Odds vigentes para exibição (calendário WC2026 como âncora):
 * - odds compiladas trazem data_confronto; oculta partidas já passadas;
 * - alinha adversário + data quando o mercado Cartola estiver sincronizado;
 * - se data_confronto >= hoje, exibe (confronto atual por seleção no armazenamento).
 */
export function oddsVigentes(
  j: JogadorMercado,
  odds: OddsJogadorEntry | null | undefined,
): boolean {
  if (!odds) return false;
  const dataOdds = odds.data_confronto?.trim();
  const prox = j.proximo_adversario_sigla?.trim().toUpperCase();
  const proxData = j.proximo_adversario_data?.trim();
  const oddsAdv = odds.adversario_sigla?.trim().toUpperCase();

  if (dataOdds) {
    if (dataOdds < hojeCalendario()) return false;
    if (proxData && prox && oddsAdv) {
      return dataOdds === proxData && oddsAdv === prox;
    }
    return Boolean(oddsAdv);
  }

  if (!prox) return true;
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
