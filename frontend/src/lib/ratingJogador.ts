import { mediaGeralCopa, temCopa } from "@/lib/copaJogador";
import {
  fatorMlSelecao,
  pVitSelecaoRodada,
  type ContextoMlRodada,
} from "@/lib/fatorMoneylineRodada";
import { calcularRatingSelecaoCopa } from "@/lib/ratingSelecao";
import type { JogadorMercado, OddsJogadorEntry, Selecao } from "@/types/dados";

export interface ConfrontoCopa {
  mandante: string;
  visitante: string;
  match_id: string;
  finalizada: boolean;
}

export interface ContextoRating {
  nivelPorSigla: Map<string, number>;
  adversariosPorSelecao: Map<string, string[]>;
}

/** @deprecated alias — use ContextoRating */
export type EscalasRating = ContextoRating;

const NIVEL_NEUTRO = 50;
/** Ajuste máximo ±30% conforme força média dos adversários (0 → −30%, 100 → +30%). */
const PONDERACAO_MAX = 0.3;
/** Teto de rating acima do nível Elo da seleção (exceções raras podem extrapolar um pouco). */
const MARGEM_SOBRE_SELECAO = 15;
const EXCECAO_MG = 6.5;
const EXCECAO_EXTRA = 8;

/** Rating 0–100 a partir da MG por jogo (escala Cartola absoluta). */
function mgParaRating(mg: number): number {
  if (mg < 0) {
    return Math.round(Math.max(1, 25 + mg * 3) * 10) / 10;
  }
  if (mg <= 2.5) {
    return Math.round((25 + (mg / 2.5) * 20) * 10) / 10;
  }
  if (mg <= 3.99) {
    return Math.round((45 + ((mg - 2.5) / 1.49) * 12) * 10) / 10;
  }
  if (mg <= 5.5) {
    return Math.round((57 + ((mg - 3.99) / 1.51) * 13) * 10) / 10;
  }
  if (mg <= 10) {
    return Math.round((70 + ((mg - 5.5) / 4.5) * 20) * 10) / 10;
  }
  return Math.round(Math.min(100, 90 + (mg - 10) * 1.5) * 10) / 10;
}

function nivelSelecao(s: Selecao, pool: Selecao[]): number {
  if (s.rating_elo_100 != null) return s.rating_elo_100;
  return calcularRatingSelecaoCopa(s, pool) ?? NIVEL_NEUTRO;
}

function aplicarTetoSelecao(
  historico: number,
  j: JogadorMercado,
  nivelSel: number,
): number {
  const mg = mediaGeralCopa(j);
  const excecao = mg !== null && mg >= EXCECAO_MG;
  const teto = Math.min(100, nivelSel + MARGEM_SOBRE_SELECAO);
  if (historico <= teto) return historico;
  if (excecao) {
    return Math.min(historico, teto + EXCECAO_EXTRA);
  }
  return teto;
}

export function construirContextoRating(
  selecoes: Selecao[],
  confrontos: ConfrontoCopa[],
  partidasProcessadas: string[],
): ContextoRating {
  const siglaPorSelecao = new Map(selecoes.map((s) => [s.selecao, s.sigla]));
  const nivelPorSigla = new Map<string, number>();
  for (const s of selecoes) {
    nivelPorSigla.set(s.sigla, nivelSelecao(s, selecoes));
  }

  const processadas = new Set(partidasProcessadas);
  const adversariosPorSelecao = new Map<string, string[]>(
    selecoes.map((s) => [s.selecao, []]),
  );

  for (const c of confrontos) {
    if (!c.finalizada || !processadas.has(c.match_id)) continue;
    const advMandante = siglaPorSelecao.get(c.visitante);
    const advVisitante = siglaPorSelecao.get(c.mandante);
    if (advMandante) {
      adversariosPorSelecao.get(c.mandante)?.push(advMandante);
    }
    if (advVisitante) {
      adversariosPorSelecao.get(c.visitante)?.push(advVisitante);
    }
  }

  return { nivelPorSigla, adversariosPorSelecao };
}

/** Compatibilidade com chamadas antigas (sem calendário → sem ponderação). */
export function construirEscalasRating(
  selecoes: Selecao[],
  confrontos: ConfrontoCopa[] = [],
  partidasProcessadas: string[] = [],
): ContextoRating {
  return construirContextoRating(selecoes, confrontos, partidasProcessadas);
}

function mediaNivelAdversarios(j: JogadorMercado, ctx: ContextoRating): number | null {
  const siglas = ctx.adversariosPorSelecao.get(j.selecao) ?? [];
  if (siglas.length === 0) return null;
  const soma = siglas.reduce(
    (acc, sig) => acc + (ctx.nivelPorSigla.get(sig) ?? NIVEL_NEUTRO),
    0,
  );
  return soma / siglas.length;
}

function fatorPonderacaoAdversarios(mediaNivel: number): number {
  return 1 + PONDERACAO_MAX * ((mediaNivel - NIVEL_NEUTRO) / NIVEL_NEUTRO);
}

/** Odds 0–100 para compor Performance (60% MG + 25% odds + 15% seleção). */
function sinalOddsPerformance(
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
    return g ?? a ?? null;
  }

  if (bucket === "LAT" || bucket === "ZAG") {
    const partes = [g, a, sg].filter((v): v is number => v !== null);
    if (partes.length === 0) return null;
    return Math.round((partes.reduce((s, v) => s + v, 0) / partes.length) * 10) / 10;
  }

  return null;
}

/** 60% MG + 25% odds posicionais + 15% Elo da seleção (escala 0–100). */
function performanceScore(
  j: JogadorMercado,
  ctx: ContextoRating,
  odds?: OddsJogadorEntry | null,
): number | null {
  const mg = mediaGeralCopa(j);
  if (mg === null) return null;

  const mgScore = mgParaRating(mg);
  const oddsScore = sinalOddsPerformance(j.bucket_posicao, odds);
  const selScore = ctx.nivelPorSigla.get(j.sigla) ?? NIVEL_NEUTRO;

  let score = 0.6 * mgScore + 0.15 * selScore;
  if (oddsScore !== null) {
    score += 0.25 * oddsScore;
  }
  return Math.round(score * 10) / 10;
}

/** Rating histórico na Copa (performance + adversários já jogados), sem moneyline da rodada. */
export function calcularRatingHistorico(
  j: JogadorMercado,
  ctx: ContextoRating,
  odds?: OddsJogadorEntry | null,
): number {
  if (!temCopa(j)) return 0;
  const base = performanceScore(j, ctx, odds);
  if (base === null) return 0;

  const mediaAdv = mediaNivelAdversarios(j, ctx);
  if (mediaAdv === null) {
    const nivelSel = ctx.nivelPorSigla.get(j.sigla) ?? NIVEL_NEUTRO;
    return aplicarTetoSelecao(base, j, nivelSel);
  }

  const ponderado = base * fatorPonderacaoAdversarios(mediaAdv);
  const historico = Math.round(Math.min(100, Math.max(1, ponderado)) * 10) / 10;
  const nivelSel = ctx.nivelPorSigla.get(j.sigla) ?? NIVEL_NEUTRO;
  return aplicarTetoSelecao(historico, j, nivelSel);
}

export function calcularRatingJogador(
  j: JogadorMercado,
  ctx: ContextoRating,
  mlCtx?: ContextoMlRodada | null,
  siglaSelecao?: string | null,
  odds?: OddsJogadorEntry | null,
): number {
  const historico = calcularRatingHistorico(j, ctx, odds);
  if (historico <= 0) return 0;

  const fator = fatorMlSelecao(siglaSelecao ?? j.sigla, mlCtx);
  if (fator === 1) return historico;

  const ajustado = historico * fator;
  return Math.round(Math.min(100, Math.max(1, ajustado)) * 10) / 10;
}

export function tooltipRating(
  j: JogadorMercado,
  rating: number,
  ctx: ContextoRating,
  mlCtx?: ContextoMlRodada | null,
  siglaSelecao?: string | null,
  odds?: OddsJogadorEntry | null,
): string {
  const mg = mediaGeralCopa(j);
  if (mg === null) {
    return "Nível de atuação do jogador durante a Copa";
  }

  const perf = performanceScore(j, ctx, odds);
  const historico = calcularRatingHistorico(j, ctx, odds);
  const sigla = siglaSelecao ?? j.sigla;
  const pVit = pVitSelecaoRodada(sigla, mlCtx);
  const fator = fatorMlSelecao(sigla, mlCtx);

  const mediaAdv = mediaNivelAdversarios(j, ctx);
  if (mediaAdv === null && pVit == null) {
    return `Performance ${perf?.toFixed(1) ?? "—"} (MG ${mg.toFixed(2)})`;
  }

  const partes: string[] = [];
  if (mediaAdv !== null) {
    const siglas = ctx.adversariosPorSelecao.get(j.selecao) ?? [];
    partes.push(
      `Performance ${perf?.toFixed(1) ?? "—"} → ${historico.toFixed(1)} ` +
        `(adversários ${siglas.join(", ") || "—"} · média ${mediaAdv.toFixed(0)})`,
    );
  } else {
    partes.push(`Performance ${perf?.toFixed(1) ?? "—"} → ${historico.toFixed(1)}`);
  }

  if (pVit != null && fator !== 1) {
    partes.push(
      `ML rodada P(vit.) ${pVit.toFixed(1)}% × fator ${fator.toFixed(2)} → ${rating.toFixed(1)}`,
    );
  } else if (pVit != null) {
    partes.push(`ML rodada P(vit.) ${pVit.toFixed(1)}%`);
  }

  return partes.join(". ");
}
