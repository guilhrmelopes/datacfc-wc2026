import { classeCorPerformance } from "@/lib/cores";
import {
  calcularQuartis,
  classificarFaixaMetrica,
  classeCelulaMetrica,
  type ChaveMetricaScouts,
} from "@/lib/formatacaoMetricas";
import type { JogadorMercado } from "@/types/dados";
import { temCopa } from "@/lib/copaJogador";

/** Colunas Cartola (MG/MB) — faixas absolutas de pontuação por jogo. */
export function classeCelulaCartola(valor: number): string {
  return classeCorPerformance(valor);
}

/** Colunas numéricas de scouts — quartis entre pares da mesma posição na Copa. */
export function classeCelulaScoutJogador(
  chave: string,
  valor: number,
  amostra: number[],
): string {
  const invertido = chave === "gs";
  if (!invertido && valor <= 0) return "bg-red-500/15";

  if (amostra.length < 4) {
    if (invertido) {
      if (valor <= 0) return "bg-green-500/15";
      if (valor >= 2) return "bg-red-500/15";
      return "bg-yellow-500/15";
    }
    if (valor >= 3) return "bg-green-500/15";
    if (valor >= 1) return "bg-yellow-500/15";
    return "bg-orange-500/15";
  }

  const quartis = calcularQuartis(amostra);
  if (!quartis) return "bg-slate-700/25";

  const faixa = classificarFaixaMetrica(
    (invertido ? "GS" : "GM") as ChaveMetricaScouts,
    valor,
    amostra,
  );
  return classeCelulaMetrica(faixa);
}

export function amostraScoutPorPosicao(
  jogadores: JogadorMercado[],
  posicao: string,
  extrair: (j: JogadorMercado) => number | null,
): number[] {
  return jogadores
    .filter((j) => j.bucket_posicao === posicao && temCopa(j))
    .map(extrair)
    .filter((v): v is number => v !== null);
}

export function amostraMgMbPorPosicao(
  jogadores: JogadorMercado[],
  posicao: string,
  extrair: (j: JogadorMercado) => number | null,
): number[] {
  return amostraScoutPorPosicao(jogadores, posicao, extrair);
}
