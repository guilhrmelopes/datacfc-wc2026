import type { DadosMataMata, Selecao } from "@/types/dados";
import { valorNumericoOuNull } from "@/lib/exibirValor";

/** Filtros de Elo no HUB Seleções: híbrido Copa ou só mata-mata. */
export type ModoRatingSelecao = "copa" | "ko";

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

/** Totais FotMob — converter para /jogo no rating cliente (fallback). */
const METRICAS_TOTAIS = new Set<keyof Selecao["metricas_coletivas"]>([
  "expected_goals_team",
  "expected_goals_conceded_team",
  "clean_sheet_team",
  "big_chance_team",
  "touches_in_opp_box_team",
  "total_yel_card_team",
  "total_red_card_team",
]);

const METRICAS_RATING: (keyof Selecao["metricas_coletivas"])[] = [
  "goals_team_match",
  "possession_percentage_team",
  "expected_goals_team",
  "clean_sheet_team",
  "total_tackle_team",
  "ontarget_scoring_att_team",
  "big_chance_team",
  "touches_in_opp_box_team",
  "poss_won_att_3rd_team",
  "saves_team",
  "fk_foul_lost_team",
];

const METRICAS_MENOR_MELHOR: Set<keyof Selecao["metricas_coletivas"]> = new Set([
  "goals_conceded_team_match",
  "expected_goals_conceded_team",
  "total_yel_card_team",
  "total_red_card_team",
]);

function metricaPorJogo(
  campo: keyof Selecao["metricas_coletivas"],
  valor: number,
  jogos: number,
): number {
  if (METRICAS_TOTAIS.has(campo) && jogos > 0) return valor / jogos;
  return valor;
}

function valorMetricaRating(
  s: Selecao,
  campo: keyof Selecao["metricas_coletivas"],
): number | null {
  const bruto = valorNumericoOuNull(s.metricas_coletivas[campo]);
  if (bruto === null) return null;
  const jogos = valorNumericoOuNull(s.metricas_coletivas.J) ?? 0;
  return metricaPorJogo(campo, bruto, jogos);
}

/**
 * Rating 0–100 da seleção na Copa (percentil médio das métricas coletivas).
 * Preferir `rating_scouts_100` persistido pelo pipeline quando disponível.
 */
export function calcularRatingSelecaoCopa(s: Selecao, pool: Selecao[]): number | null {
  if (s.rating_scouts_100 != null) return s.rating_scouts_100;
  if (!estreouCopa(s)) return null;

  const estrearam = pool.filter(estreouCopa);
  if (estrearam.length === 0) return null;

  const percentis: number[] = [];

  for (const campo of METRICAS_RATING) {
    const valor = valorMetricaRating(s, campo);
    if (valor === null) continue;
    const amostra = estrearam
      .map((x) => valorMetricaRating(x, campo))
      .filter((v): v is number => v !== null);
    if (amostra.length === 0) continue;
    percentis.push(percentil(valor, amostra));
  }

  for (const campo of METRICAS_MENOR_MELHOR) {
    const valor = valorMetricaRating(s, campo);
    if (valor === null) continue;
    const amostra = estrearam
      .map((x) => valorMetricaRating(x, campo))
      .filter((v): v is number => v !== null);
    if (amostra.length === 0) continue;
    percentis.push(100 - percentil(valor, amostra));
  }

  if (percentis.length === 0) return null;
  const media = percentis.reduce((a, b) => a + b, 0) / percentis.length;
  return Math.round(media * 10) / 10;
}

/** Seleções ainda vivas no chaveamento (vivo = próxima fase definida ou jogo pendente). */
export function selecoesVivasHub(mataMata: DadosMataMata | null | undefined): Set<string> | null {
  if (!mataMata?.fases?.length) return null;
  const vivas = new Set<string>();
  for (const fase of mataMata.fases) {
    for (const confronto of fase.confrontos) {
      if (confronto.finalizada) continue;
      if (confronto.mandante.selecao && !confronto.mandante.tbd) {
        vivas.add(confronto.mandante.selecao);
      }
      if (confronto.visitante.selecao && !confronto.visitante.tbd) {
        vivas.add(confronto.visitante.selecao);
      }
    }
  }
  // Fallback: se quartas ainda TBD, use vencedores das oitavas
  if (vivas.size === 0) {
    const oitavas = mataMata.fases.find((f) => f.stage === "1/8");
    for (const c of oitavas?.confrontos ?? []) {
      if (!c.finalizada) continue;
      if (c.mandante_venceu && c.mandante.selecao) vivas.add(c.mandante.selecao);
      if (c.visitante_venceu && c.visitante.selecao) vivas.add(c.visitante.selecao);
    }
  }
  return vivas.size > 0 ? vivas : null;
}

/**
 * Rating exibido no HUB Seleções.
 * - copa: híbrido Elo mundial + scouts + Elo KO
 * - ko: Elo só com resultados de mata-mata
 */
export function ratingSelecaoExibicao(
  s: Selecao,
  pool: Selecao[],
  modo: ModoRatingSelecao = "copa",
): number | null {
  if (modo === "ko") {
    return s.rating_ko_100 ?? null;
  }
  return (
    s.rating_copa_100 ??
    calcularRatingSelecaoCopa(s, pool) ??
    s.rating_elo_100 ??
    null
  );
}

export function tooltipRatingSelecao(
  s: Selecao,
  pool: Selecao[],
  modo: ModoRatingSelecao = "copa",
): string {
  const scouts = calcularRatingSelecaoCopa(s, pool);
  const partes = [
    `Elo mundial ${s.rating_elo_100 ?? "—"}`,
    `Scouts ${scouts ?? "—"}`,
  ];
  if ((s.jogos_mata_mata ?? 0) > 0) {
    partes.push(`Elo KO ${s.rating_ko_100 ?? "—"} (${s.jogos_mata_mata}J)`);
  }
  const atual = ratingSelecaoExibicao(s, pool, modo);
  const rotulo =
    modo === "ko" ? "Rating Mata-mata" : "Rating Copa do Mundo";
  return `${rotulo} ${atual ?? "—"} · ${partes.join(" · ")}`;
}
