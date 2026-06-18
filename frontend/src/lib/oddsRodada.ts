import type { OddsJogadorEntry } from "@/types/dados";
import { dataNaRodadaCartola, rodadaCartolaPorData } from "@/lib/rodadaMercado";

export interface EventoOddsArmazenado {
  event_id?: number;
  data?: string;
  rodada?: number | null;
  sigla_mandante?: string;
  sigla_visitante?: string;
  odds?: Record<string, OddsJogadorEntry>;
}

export interface OddsArmazenamentoData {
  eventos?: Record<string, EventoOddsArmazenado>;
}

/** Índice rodada → atleta_id → odds da partida cuja data cai no intervalo Cartola. */
export function compilarOddsPorRodada(
  armazenamento: OddsArmazenamentoData | null | undefined,
  rodadas: number[],
): Map<number, Record<string, OddsJogadorEntry>> {
  const indice = new Map<number, Record<string, OddsJogadorEntry>>();
  for (const r of rodadas) indice.set(r, {});

  const eventos = armazenamento?.eventos;
  if (!eventos) return indice;

  for (const ev of Object.values(eventos)) {
    const dataEvento = ev.data ?? null;
    const rodada = rodadaCartolaPorData(dataEvento);
    if (rodada == null || !rodadas.includes(rodada)) continue;
    const mapa = indice.get(rodada)!;

    for (const [aid, bruto] of Object.entries(ev.odds ?? {})) {
      if (!bruto || typeof bruto !== "object") continue;
      const dataConfronto = bruto.data_confronto ?? dataEvento ?? null;
      if (!dataNaRodadaCartola(dataConfronto, rodada)) continue;
      mapa[aid] = {
        ...bruto,
        event_id: bruto.event_id ?? ev.event_id ?? 0,
        rodada,
        data_confronto: dataConfronto,
      };
    }
  }

  return indice;
}

/** Odds exibíveis para a rodada Cartola selecionada. */
export function oddsParaRodada(
  atletaId: number,
  rodada: number,
  indice: Map<number, Record<string, OddsJogadorEntry>>,
  fallback: Record<string, OddsJogadorEntry> | null,
): OddsJogadorEntry | null {
  const porRodada = indice.get(rodada)?.[String(atletaId)];
  if (porRodada) return porRodada;
  const fb = fallback?.[String(atletaId)];
  if (fb && dataNaRodadaCartola(fb.data_confronto, rodada)) return fb;
  return null;
}

export function oddsAtivaNaRodada(odds: OddsJogadorEntry | null | undefined): boolean {
  return (
    odds != null &&
    (odds.g_pct != null ||
      odds.a_pct != null ||
      odds.ga_pct != null ||
      odds.sg_pct != null)
  );
}
