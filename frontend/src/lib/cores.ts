/** Cores para pontuação Cartola (cedido/conquistado) — faixas absolutas. */

export function classeCorPerformance(valor: number): string {
  if (valor <= 2.5) return "bg-red-500/20 text-[var(--color-fg)]";
  if (valor <= 3.99) return "bg-orange-500/20 text-[var(--color-fg)]";
  if (valor <= 5.5) return "bg-yellow-500/20 text-[var(--color-fg)]";
  return "bg-green-500/20 text-[var(--color-fg)]";
}

export { classeCelulaNeutra } from "@/lib/formatacaoMetricas";
