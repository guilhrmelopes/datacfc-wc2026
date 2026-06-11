import type { JogadorMercado, OddsJogadorEntry } from "@/types/dados";

/**
 * Potencial para Rodada (coluna ⓘ) — índice híbrido 0–100.
 *
 * Combina o melhor sinal histórico individual (Rating das eliminatórias)
 * com o sinal de mercado da rodada (GA%/SG%), calibrado por posição.
 *
 * P_bruto = α·R + (1−α)·O   (com odds)
 * P       = P_bruto × f(status)
 *
 * α = 0,65 — o Rating captura forma/rol na seleção; odds refletem o confronto.
 * Sem odds, P_bruto = R (cadeia de fallbacks em ratingBase).
 */

export const POTENCIAL_ALPHA = 0.65;

/** Pesos SG/GA no sinal de odds O — alinhados aos mercados disponíveis e ao perfil Cartola. */
export const PESOS_ODDS: Record<
  string,
  { sg: number; ga: number; descricao: string }
> = {
  GOL: { sg: 1, ga: 0, descricao: "SG% (clean sheet)" },
  ZAG: { sg: 0.65, ga: 0.35, descricao: "65% SG% + 35% GA%" },
  LAT: { sg: 0.55, ga: 0.45, descricao: "55% SG% + 45% GA%" },
  MEI: { sg: 0, ga: 1, descricao: "GA% (marcar ou assistir)" },
  ATA: { sg: 0, ga: 1, descricao: "GA% (marcar ou assistir)" },
};

/** Escala de disponibilidade para a rodada — essencial para “potencial” vs “talento”. */
export const FATOR_STATUS: Record<number, number> = {
  6: 1.0, // Provável
  2: 0.85, // Dúvida
  7: 0.72, // Nulo (reserva)
  5: 0, // Suspenso
  3: 0, // Lesionado
};

const FATOR_STATUS_PADRAO = 0.72;

/**
 * Sinal de odds 0–100 por posição.
 * GA% = prob. individual marcar ou assistir; SG% = prob. time não sofrer gol.
 * SG% é por equipe (mesmo valor para todos do time) — por isso ZAG/LAT
 * misturam GA% individual para diferenciar titulares.
 */
export function sinalOddsRodada(
  bucket: string,
  odds: OddsJogadorEntry | null | undefined,
): number | null {
  const ga = odds?.ga_pct ?? null;
  const sg = odds?.sg_pct ?? null;
  const pesos = PESOS_ODDS[bucket];

  if (!pesos) return ga ?? sg;

  if (pesos.ga === 0) return sg;
  if (pesos.sg === 0) return ga;

  if (sg !== null && ga !== null) {
    return pesos.sg * sg + pesos.ga * ga;
  }
  return sg ?? ga;
}

/** Rating histórico com fallbacks para garantir índice em todo elenco. */
export function ratingBase(j: JogadorMercado): number {
  if (j.rating_recomendacao > 0) return j.rating_recomendacao;

  if (j.media_geral != null && j.media_geral > 0) {
    return Math.min(100, Math.round((j.media_geral / 12) * 1000) / 10);
  }

  if (j.media_base != null && j.media_base > 0) {
    return Math.min(100, Math.round((j.media_base / 12) * 1000) / 10);
  }

  const jogos = Math.max(j.jogos_num, 1);
  let pts = j.goals * 8 + j.goal_assist * 5;
  if (j.bucket_posicao === "GOL" || j.bucket_posicao === "LAT" || j.bucket_posicao === "ZAG") {
    pts += j.clean_sheet * 5;
  }
  const proxy = (pts / jogos / 12) * 100;
  return Math.min(100, Math.max(1, Math.round(proxy * 10) / 10));
}

export function fatorStatus(statusId: number): number {
  return FATOR_STATUS[statusId] ?? FATOR_STATUS_PADRAO;
}

/** Potencial bruto antes do ajuste de status (0–100). */
export function calcularPotencialBruto(
  j: JogadorMercado,
  odds: OddsJogadorEntry | null | undefined,
): number {
  const r = ratingBase(j);
  const o = sinalOddsRodada(j.bucket_posicao, odds);
  if (o !== null) {
    return Math.round((POTENCIAL_ALPHA * r + (1 - POTENCIAL_ALPHA) * o) * 10) / 10;
  }
  return Math.round(r * 10) / 10;
}

/**
 * Potencial para Rodada 1 (0–100):
 * combina Rating + odds por posição, penalizado por status.
 */
export function calcularPotencialRodada(
  j: JogadorMercado,
  odds: OddsJogadorEntry | null | undefined,
): number {
  const bruto = calcularPotencialBruto(j, odds);
  const fator = fatorStatus(j.status_id);
  return Math.round(bruto * fator * 10) / 10;
}

export function tooltipPotencialRodada(
  j: JogadorMercado,
  odds: OddsJogadorEntry | null | undefined,
  potencial: number,
): string {
  const r = ratingBase(j);
  const o = sinalOddsRodada(j.bucket_posicao, odds);
  const bruto = calcularPotencialBruto(j, odds);
  const fator = fatorStatus(j.status_id);
  const pesos = PESOS_ODDS[j.bucket_posicao];

  let base: string;
  if (o !== null) {
    const oddsLabel = pesos?.descricao ?? "odds";
    base = `${Math.round(POTENCIAL_ALPHA * 100)}% Rating ${r.toFixed(1)} + ${Math.round((1 - POTENCIAL_ALPHA) * 100)}% ${oddsLabel} ${o.toFixed(1)}`;
  } else {
    base = `Rating ${r.toFixed(1)} (sem odds na rodada)`;
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
    return `Potencial: ${potencial.toFixed(1)} (${base}; bruto ${bruto.toFixed(1)} × ${Math.round(fator * 100)}% ${status})`;
  }

  return `Potencial para Rodada: ${potencial.toFixed(1)} (${base})`;
}
