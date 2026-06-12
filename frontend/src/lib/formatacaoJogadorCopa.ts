import { classeCorPerformance } from "@/lib/cores";
import {
  classificarFaixaMetrica,
  classificarFaixaRelativa,
  classeCelulaMetrica,
  classeCelulaNeutra,
  type ChaveMetricaScouts,
  type FaixaMetrica,
} from "@/lib/formatacaoMetricas";
import type { JogadorMercado } from "@/types/dados";
import { temCopa } from "@/lib/copaJogador";

/** Colunas Cartola (MG/MB/CED) — faixas absolutas de pontuação por jogo. */
export function classeCelulaCartola(valor: number): string {
  return classeCorPerformance(valor);
}

const CHAVE_METRICA_POR_COLUNA: Partial<Record<string, ChaveMetricaScouts>> = {
  g: "GM",
  fd: "FD",
  gcc: "GCC",
  ds: "DS",
  de: "DE",
  sg: "SG",
  xg: "xG",
  xa: "xG",
  xgx_a90: "xG",
  gs: "GS",
};

function chaveMetricaScout(colKey: string, invertido: boolean): ChaveMetricaScouts {
  if (invertido) return "GS";
  return CHAVE_METRICA_POR_COLUNA[colKey] ?? "GM";
}

/** Colunas numéricas de scouts — quartis entre pares da mesma posição (Wyscout). */
export function classeCelulaScoutJogador(
  colKey: string,
  valor: number,
  amostra: number[],
): string {
  const invertido = colKey === "gs";

  if (!invertido && valor <= 0) {
    return classeCelulaMetrica("critico");
  }
  if (invertido && valor <= 0) {
    return classeCelulaMetrica("excelente");
  }

  if (amostra.length >= 4) {
    const faixa = classificarFaixaRelativa(valor, amostra, invertido);
    return classeCelulaMetrica(faixa);
  }

  const metrica = chaveMetricaScout(colKey, invertido);
  const faixa = classificarFaixaMetrica(metrica, valor, amostra);
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

export { classeCelulaNeutra, type FaixaMetrica };
