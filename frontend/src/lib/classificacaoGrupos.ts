import type { ClassificacaoGrupos, LinhaClassificacao } from "@/types/dados";

export type ZonaClassificacao = "classificado" | "melhor-terceiro" | "neutro";

const GRUPOS = "ABCDEFGHIJKL".split("");

export interface ClassificacaoGruposParseada {
  melhoresTerceiros: string[];
  grupos: ClassificacaoGrupos;
}

/** Lê classificacao_grupos.json (com ou sem campo melhores_terceiros). */
export function parseClassificacaoGrupos(
  raw: Record<string, unknown>,
): ClassificacaoGruposParseada {
  const melhoresTerceiros = Array.isArray(raw.melhores_terceiros)
    ? (raw.melhores_terceiros as string[])
    : [];

  const grupos: ClassificacaoGrupos = {};
  for (const [chave, valor] of Object.entries(raw)) {
    if (chave === "melhores_terceiros" || !Array.isArray(valor)) continue;
    grupos[chave] = valor as LinhaClassificacao[];
  }

  return { melhoresTerceiros, grupos };
}

export function calcularZonaPorSelecao(
  grupos: ClassificacaoGrupos,
  melhoresTerceiros: string[],
): Map<string, ZonaClassificacao> {
  const terceirosClassificados = new Set(melhoresTerceiros);
  const zonas = new Map<string, ZonaClassificacao>();

  for (const grupo of GRUPOS) {
    for (const linha of grupos[grupo] ?? []) {
      let zona: ZonaClassificacao = "neutro";
      if (linha.posicao === 1 || linha.posicao === 2) {
        zona = "classificado";
      } else if (linha.posicao === 3 && terceirosClassificados.has(linha.selecao)) {
        zona = "melhor-terceiro";
      }
      zonas.set(linha.selecao, zona);
    }
  }

  return zonas;
}

export function classeColunaZona(zona: ZonaClassificacao): string {
  switch (zona) {
    case "classificado":
      return "bg-green-500/25 text-[var(--color-fg)]";
    case "melhor-terceiro":
      return "bg-sky-500/30 text-[var(--color-fg)]";
    default:
      return "";
  }
}
