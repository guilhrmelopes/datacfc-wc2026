/** Cores para pontuação Cartola (MG, MB, CED) — faixas absolutas, paleta Wyscout. */

import {
  classificarFaixaCartola,
  classeCelulaMetrica,
} from "@/lib/formatacaoMetricas";

export function classeCorPerformance(valor: number): string {
  return classeCelulaMetrica(classificarFaixaCartola(valor));
}

export { classeCelulaNeutra } from "@/lib/formatacaoMetricas";
