import type { ConfrontoMataMata, DadosMataMata, FaseMataMata } from "@/types/dados";

const ROTULOS_FASE: Record<string, string> = {
  "1/16": "16 avos",
  "1/8": "Oitavas",
  "1/4": "Quartas",
  "1/2": "Semis",
  final: "Final",
  bronze: "3º lugar",
};

export function rotuloFase(stage: string): string {
  return ROTULOS_FASE[stage] ?? stage;
}

export function formatarDataConfronto(data: string): string {
  if (!data) return "";
  const [ano, mes, dia] = data.split("-").map(Number);
  if (!ano || !mes || !dia) return data;
  const dt = new Date(ano, mes - 1, dia);
  return dt.toLocaleDateString("pt-BR", { day: "numeric", month: "short" });
}

function metadeEsquerda(confrontos: ConfrontoMataMata[], metade: "esquerda" | "direita") {
  const meio = Math.ceil(confrontos.length / 2);
  return metade === "esquerda" ? confrontos.slice(0, meio) : confrontos.slice(meio);
}

export interface ChaveamentoLado {
  fases: { stage: string; rotulo: string; confrontos: ConfrontoMataMata[] }[];
}

export function montarChaveamentoLados(dados: DadosMataMata): {
  esquerda: ChaveamentoLado;
  direita: ChaveamentoLado;
} {
  const esquerda: ChaveamentoLado = { fases: [] };
  const direita: ChaveamentoLado = { fases: [] };

  for (const fase of dados.fases) {
    if (fase.stage === "final") continue;
    esquerda.fases.push({
      stage: fase.stage,
      rotulo: rotuloFase(fase.stage),
      confrontos: metadeEsquerda(fase.confrontos, "esquerda"),
    });
    direita.fases.push({
      stage: fase.stage,
      rotulo: rotuloFase(fase.stage),
      confrontos: metadeEsquerda(fase.confrontos, "direita"),
    });
  }

  direita.fases.reverse();
  return { esquerda, direita };
}

export function parseDadosMataMata(raw: unknown): DadosMataMata {
  const obj = raw as DadosMataMata;
  return {
    modo: obj.modo ?? "As it stands",
    atualizado_em: obj.atualizado_em ?? null,
    fases: Array.isArray(obj.fases) ? obj.fases : [],
    final: obj.final ?? null,
    disputa_bronze: obj.disputa_bronze ?? null,
  };
}

export function alturaChaveamento(numConfrontos: number, alturaCard = 76, gap = 10): number {
  if (numConfrontos <= 0) return 0;
  return numConfrontos * alturaCard + (numConfrontos - 1) * gap;
}

export function faseOitavas(dados: DadosMataMata): FaseMataMata | undefined {
  return dados.fases.find((f) => f.stage === "1/16");
}
