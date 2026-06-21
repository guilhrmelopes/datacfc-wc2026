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
  const mg = j.copa_media_geral;
  if (mg !== null && mg !== undefined) return mg;
  const jogos = j.copa_jogos_num ?? 0;
  if (jogos > 0) return round2((j.copa_pontos_total ?? 0) / jogos);
  return null;
}

export function mediaBaseCopa(j: JogadorMercado): number | null {
  if (!temCopa(j)) return null;
  const mb = j.copa_media_base;
  if (mb !== null && mb !== undefined) return mb;
  const mg = mediaGeralCopa(j);
  return mg !== null ? mg : 0;
}

function round2(n: number): number {
  return Math.round(n * 100) / 100;
}

export function jogosCopa(j: JogadorMercado): number {
  return j.copa_jogos_num ?? 0;
}

/** Média por jogo (total acumulado ÷ J). */
export function scoutPorJogoCopa(
  j: JogadorMercado,
  total: number | null | undefined,
): number | null {
  if (!temCopa(j)) return null;
  const jogos = jogosCopa(j);
  if (jogos <= 0) return null;
  return round2((total ?? 0) / jogos);
}

export function minutosPorJogoCopa(j: JogadorMercado): number | null {
  return scoutPorJogoCopa(j, j.copa_mins_played);
}

export function xgPor90Copa(j: JogadorMercado): number | null {
  if (!temCopa(j)) return null;
  const mins = j.copa_mins_played ?? 0;
  if (mins <= 0) return 0;
  return round2(((j.copa_xg ?? 0) / mins) * 90);
}

export function xaPor90Copa(j: JogadorMercado): number | null {
  if (!temCopa(j)) return null;
  const mins = j.copa_mins_played ?? 0;
  if (mins <= 0) return 0;
  return round2(((j.copa_xa ?? 0) / mins) * 90);
}

export function dePctPor90Copa(j: JogadorMercado): number | null {
  if (!temCopa(j) || j.bucket_posicao !== "GOL") return null;
  if (j.copa_de_pct != null) return j.copa_de_pct;
  const mins = j.copa_mins_played ?? 0;
  if (mins <= 0) return 0;
  return round2(((j.copa_de ?? 0) / mins) * 90);
}

export function xgXaPor90Copa(j: JogadorMercado): number | null {
  if (!temCopa(j)) return null;
  const mins = j.copa_mins_played ?? 0;
  if (mins <= 0) return 0;
  const xg = j.copa_xg ?? 0;
  const xa = j.copa_xa ?? 0;
  return round2(((xg + xa) / mins) * 90);
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
  adversarioSigla?: string | null,
): number | null {
  const adv = (adversarioSigla ?? j.proximo_adversario_sigla)?.trim().toUpperCase();
  if (!adv) return null;
  const perf = pontuacao[adv] as PerformancePorSigla | null | undefined;
  if (!perf) return null;
  const bucket = j.bucket_posicao as keyof PerformancePorSigla;
  const celula = perf[bucket]?.cedido;
  const valor = celula?.valor;
  if (valor === null || valor === undefined) return 0;
  return valor;
}
