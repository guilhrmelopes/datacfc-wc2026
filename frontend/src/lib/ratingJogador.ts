import { mediaGeralCopa, temCopa } from "@/lib/copaJogador";
import type { JogadorMercado } from "@/types/dados";

export type EscalasRating = Record<string, number[]>;

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

/** Mantido para compatibilidade com potencialRodada (escala não usada no rating). */
export function construirEscalasRating(_jogadores: JogadorMercado[]): EscalasRating {
  return {};
}

export function calcularRatingJogador(j: JogadorMercado, _escalas: EscalasRating): number {
  if (!temCopa(j)) return 0;
  const mg = mediaGeralCopa(j);
  if (mg === null) return 0;
  return mgParaRating(mg);
}

export function tooltipRating(_j: JogadorMercado, _rating: number, _escalas: EscalasRating): string {
  return "Nível de atuação do jogador durante a Copa";
}
