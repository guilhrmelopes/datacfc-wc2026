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
  return mg !== null && mg !== undefined ? mg : null;
}

export function mediaBaseCopa(j: JogadorMercado): number | null {
  if (!temCopa(j)) return null;
  const mb = j.copa_media_base;
  return mb !== null && mb !== undefined ? mb : null;
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

function datasAlinhadas(a: string, b: string, toleranciaDias = 2): boolean {
  if (a === b) return true;
  const pa = a.split("-").map(Number);
  const pb = b.split("-").map(Number);
  if (pa.length !== 3 || pb.length !== 3 || pa.some(Number.isNaN) || pb.some(Number.isNaN)) {
    return false;
  }
  const da = Date.UTC(pa[0], pa[1] - 1, pa[2]);
  const db = Date.UTC(pb[0], pb[1] - 1, pb[2]);
  return Math.abs(da - db) <= toleranciaDias * 86_400_000;
}

/**
 * Odds vigentes para exibição (calendário WC2026 como âncora):
 * - odds compiladas trazem data_confronto; oculta partidas já passadas;
 * - alinha adversário (data com tolerância de ±2 dias entre FotMob e OddsNotifier);
 * - se data_confronto >= hoje, exibe (confronto atual por seleção no armazenamento).
 */
export function oddsVigentes(
  j: JogadorMercado,
  odds: OddsJogadorEntry | null | undefined,
): boolean {
  if (j.ativo_playoffs === false) return false;
  if (!odds) return false;
  const dataOdds = odds.data_confronto?.trim();
  const prox = j.proximo_adversario_sigla?.trim().toUpperCase();
  const proxData = j.proximo_adversario_data?.trim();
  const oddsAdv = odds.adversario_sigla?.trim().toUpperCase();

  if (dataOdds) {
    if (dataOdds < hojeCalendario()) return false;
    if (prox && oddsAdv) {
      if (oddsAdv !== prox) return false;
      if (proxData) return datasAlinhadas(dataOdds, proxData);
      return true;
    }
    return Boolean(oddsAdv);
  }

  if (!prox) return !temCopa(j);
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
  if (valor === null || valor === undefined) return null;
  return valor;
}
