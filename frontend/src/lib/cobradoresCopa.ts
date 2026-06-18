export interface CobradorAtleta {
  penalti?: boolean;
  bola_parada?: boolean;
  ordem_penalti?: number;
  ordem_bola_parada?: number;
}

export interface CobradoresCopaData {
  atualizado_em?: string;
  fonte?: string;
  selecoes_com_dados?: number;
  por_atleta?: Record<string, CobradorAtleta>;
}

export function compilarIndiceCobradores(
  dados: CobradoresCopaData | null | undefined,
): Map<number, CobradorAtleta> {
  const indice = new Map<number, CobradorAtleta>();
  const bruto = dados?.por_atleta;
  if (!bruto) return indice;

  for (const [aid, entry] of Object.entries(bruto)) {
    const id = Number(aid);
    if (!Number.isFinite(id) || !entry) continue;
    indice.set(id, entry);
  }
  return indice;
}

export function tooltipCobrador(entry: CobradorAtleta | undefined): string | undefined {
  if (!entry) return undefined;
  const partes: string[] = [];
  if (entry.penalti) {
    const ord = entry.ordem_penalti ? ` (#${entry.ordem_penalti})` : "";
    partes.push(`Cobrador de pênalti${ord}`);
  }
  if (entry.bola_parada) {
    const ord = entry.ordem_bola_parada ? ` (#${entry.ordem_bola_parada})` : "";
    partes.push(`Bola parada — escanteios e faltas${ord}`);
  }
  return partes.length ? partes.join(" · ") : undefined;
}
