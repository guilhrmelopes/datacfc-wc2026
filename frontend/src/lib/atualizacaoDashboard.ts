const FUSO_BR = "America/Sao_Paulo";

/** Intervalo de verificação — alinhado à rotina de 30 min, com margem para deploy. */
export const INTERVALO_POLL_MS = 2 * 60 * 1000;

interface CopaEstadoMeta {
  atualizado_em?: string | null;
  cartola_atualizado_em?: string | null;
}

interface OddsMeta {
  atualizado_em?: string | null;
}

function parseIso(iso: string | null | undefined): number | null {
  if (!iso) return null;
  const ms = Date.parse(iso);
  return Number.isNaN(ms) ? null : ms;
}

function maisRecente(...timestamps: (string | null | undefined)[]): string | null {
  let melhor: string | null = null;
  let melhorMs = -1;
  for (const iso of timestamps) {
    const ms = parseIso(iso);
    if (ms !== null && ms > melhorMs) {
      melhorMs = ms;
      melhor = iso!;
    }
  }
  return melhor;
}

async function fetchJson<T>(url: string): Promise<T | null> {
  try {
    const res = await fetch(`${url}?_=${Date.now()}`, { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

/** Busca o timestamp mais recente entre copa_estado e odds (sem cache). */
export async function buscarTimestampDashboard(): Promise<string | null> {
  const [estado, odds] = await Promise.all([
    fetchJson<CopaEstadoMeta>("/data/copa_estado.json"),
    fetchJson<OddsMeta>("/data/odds_jogadores.json"),
  ]);

  return maisRecente(
    estado?.atualizado_em,
    estado?.cartola_atualizado_em,
    odds?.atualizado_em,
  );
}

export function formatarTimestampDashboard(iso: string): string {
  return new Intl.DateTimeFormat("pt-BR", {
    timeZone: FUSO_BR,
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(iso));
}
