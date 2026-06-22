/** Contexto ML pré-compilado (substitui odds_eventos_armazenados.json no frontend). */
export interface MlContextoRodadaData {
  referencia_data?: string;
  atualizado_em?: string;
  p_vit_por_sigla?: Record<string, number>;
  p_mediana?: number;
}

export function mlContextoParaMapa(
  bruto: MlContextoRodadaData | null | undefined,
): { pVitPorSigla: Map<string, number>; pMediana: number } | null {
  const mapa = bruto?.p_vit_por_sigla;
  if (!mapa || Object.keys(mapa).length === 0) return null;
  const pVitPorSigla = new Map<string, number>();
  for (const [sigla, p] of Object.entries(mapa)) {
    pVitPorSigla.set(sigla.toUpperCase(), p);
  }
  return { pVitPorSigla, pMediana: bruto.p_mediana ?? 0 };
}
