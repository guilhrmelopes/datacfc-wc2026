export interface CobradorAtleta {
  penalti?: boolean;
  escanteio?: boolean;
  falta?: boolean;
  /** @deprecated campo legado — escanteio + falta */
  bola_parada?: boolean;
  ordem_penalti?: number;
  ordem_escanteio?: number;
  ordem_falta?: number;
  /** @deprecated campo legado */
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
    indice.set(id, normalizarCobrador(entry));
  }
  return indice;
}

function normalizarCobrador(entry: CobradorAtleta): CobradorAtleta {
  if (entry.bola_parada && !entry.escanteio && !entry.falta) {
    const ordem = entry.ordem_bola_parada;
    return {
      ...entry,
      escanteio: true,
      falta: true,
      ordem_escanteio: ordem,
      ordem_falta: ordem,
    };
  }
  return entry;
}

export function labelPrioridadeCobranca(ordem: number | undefined): string {
  if (!ordem || ordem < 1) return "Cobrador";
  if (ordem === 1) return "Cobrador oficial";
  if (ordem === 2) return "Cobrador secundário";
  if (ordem === 3) return "Cobrador terciário";
  return `${ordem}º cobrador`;
}

export function tooltipTipoCobranca(
  tipo: "escanteio" | "falta" | "penalti",
  ordem: number | undefined,
): string {
  const rotulos: Record<typeof tipo, string> = {
    escanteio: "Cobrador de escanteio",
    falta: "Cobrador de falta",
    penalti: "Cobrador de pênalti",
  };
  return `${rotulos[tipo]} — ${labelPrioridadeCobranca(ordem)}`;
}

export function tooltipCobrador(entry: CobradorAtleta | undefined): string | undefined {
  if (!entry) return undefined;
  const norm = normalizarCobrador(entry);
  const partes: string[] = [];
  if (norm.escanteio) {
    partes.push(tooltipTipoCobranca("escanteio", norm.ordem_escanteio));
  }
  if (norm.falta) {
    partes.push(tooltipTipoCobranca("falta", norm.ordem_falta));
  }
  if (norm.penalti) {
    partes.push(tooltipTipoCobranca("penalti", norm.ordem_penalti));
  }
  return partes.length ? partes.join(" · ") : undefined;
}
