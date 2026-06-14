/** Cores para pontuação Cartola (MG, MB) — faixas absolutas, paleta Wyscout. */

import {
  classificarFaixaCartola,
  classificarFaixaCartolaSelecao,
  classeCelulaMetrica,
  classeCelulaMetricaSelecao,
} from "@/lib/formatacaoMetricas";

export function classeCorPerformance(valor: number): string {
  return classeCelulaMetrica(classificarFaixaCartola(valor));
}

/** Recorrência cedido/conquistado — paleta BOM/MEDIANO/RUIM alinhada à aba Scouts. */
export function classeCorPerformanceRecorrencia(
  valor: number,
  invertido = false,
): string {
  return classeCelulaMetricaSelecao(classificarFaixaCartolaSelecao(valor, invertido));
}

export { classeCelulaNeutra } from "@/lib/formatacaoMetricas";
