import { mediaGeralCopa, temCopa } from "@/lib/copaJogador";
import { calcularRatingSelecaoCopa } from "@/lib/ratingSelecao";
import type { JogadorMercado, Selecao } from "@/types/dados";

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
  return calcularRatingSelecaoCopa(s, pool) ?? s.rating_elo_100 ?? NIVEL_NEUTRO;
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

export function calcularRatingJogador(j: JogadorMercado, ctx: ContextoRating): number {
  if (!temCopa(j)) return 0;
  const mg = mediaGeralCopa(j);
  if (mg === null) return 0;

  const base = mgParaRating(mg);
  const mediaAdv = mediaNivelAdversarios(j, ctx);
  if (mediaAdv === null) return base;

  const ponderado = base * fatorPonderacaoAdversarios(mediaAdv);
  return Math.round(Math.min(100, Math.max(1, ponderado)) * 10) / 10;
}

export function tooltipRating(
  j: JogadorMercado,
  rating: number,
  ctx: ContextoRating,
): string {
  const mg = mediaGeralCopa(j);
  if (mg === null) return "Nível de atuação do jogador durante a Copa";

  const base = mgParaRating(mg);
  const mediaAdv = mediaNivelAdversarios(j, ctx);
  if (mediaAdv === null) {
    return `Nível de atuação na Copa (MG ${mg.toFixed(2)})`;
  }

  const siglas = ctx.adversariosPorSelecao.get(j.selecao) ?? [];
  return (
    `Nível de atuação na Copa ponderado pelo nível dos adversários ` +
    `(${siglas.join(", ") || "—"} · média ${mediaAdv.toFixed(0)}). ` +
    `MG ${mg.toFixed(2)} → ${base.toFixed(1)} → ${rating.toFixed(1)}`
  );
}
