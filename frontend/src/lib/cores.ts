/** Cores para pontuação Cartola (cedido/conquistado) — faixas absolutas. */

export function classeCorPerformance(valor: number): string {
  if (valor <= 2.5) return "bg-red-500/80 text-white";
  if (valor <= 3.99) return "bg-orange-500/80 text-white";
  if (valor <= 5.5) return "bg-yellow-500/80 text-slate-900";
  return "bg-green-500/80 text-white";
}

export { classeCelulaNeutra } from "@/lib/formatacaoMetricas";
