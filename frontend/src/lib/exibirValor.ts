export function formatarValorMetrica(
  valor: number | null | undefined,
  casasDecimais = 2,
  inteiro = false
): string {
  if (valor === null || valor === undefined || Number.isNaN(Number(valor))) {
    return "N/A";
  }
  if (inteiro) {
    return String(Math.round(Number(valor)));
  }
  return Number(valor).toFixed(casasDecimais);
}

export function valorNumericoOuNull(
  valor: number | null | undefined
): number | null {
  if (valor === null || valor === undefined || Number.isNaN(Number(valor))) {
    return null;
  }
  return Number(valor);
}
