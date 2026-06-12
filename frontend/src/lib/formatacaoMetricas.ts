/** Formatação condicional de métricas na tabela Scouts (quartis + limites estáticos). */

export type ChaveMetricaScouts =
  | "GM"
  | "GS"
  | "POS%"
  | "SG"
  | "xG"
  | "xGA"
  | "FD"
  | "GCC"
  | "TAA"
  | "DS"
  | "RTF"
  | "DE"
  | "FS"
  | "CA"
  | "CV";

/** Métricas em que valor maior é melhor. */
export const METRICAS_OFENSIVAS: ReadonlySet<ChaveMetricaScouts> = new Set([
  "GM",
  "POS%",
  "xG",
  "FD",
  "GCC",
  "TAA",
  "DS",
  "RTF",
  "DE",
  "SG",
]);

/** Métricas em que valor menor é melhor. */
export const METRICAS_DEFENSIVAS: ReadonlySet<ChaveMetricaScouts> = new Set([
  "GS",
  "xGA",
  "FS",
  "CA",
  "CV",
]);

export type FaixaMetrica = "excelente" | "acima" | "abaixo" | "critico";

const CLASSES_FAIXA: Record<FaixaMetrica, string> = {
  excelente: "bg-green-500/15",
  acima: "bg-yellow-500/15",
  abaixo: "bg-orange-500/15",
  critico: "bg-red-500/15",
};

/** Limites estáticos (excelente, acima, abaixo) quando há poucos dados para quartis. */
const LIMITES_ESTATICOS: Partial<
  Record<ChaveMetricaScouts, { invertido: boolean; excelente: number; acima: number; abaixo: number }>
> = {
  GM: { invertido: false, excelente: 1.8, acima: 1.2, abaixo: 0.6 },
  GS: { invertido: true, excelente: 0.6, acima: 1.0, abaixo: 1.4 },
  "POS%": { invertido: false, excelente: 58, acima: 50, abaixo: 42 },
  SG: { invertido: false, excelente: 8, acima: 5, abaixo: 2 },
  xG: { invertido: false, excelente: 1.8, acima: 1.2, abaixo: 0.7 },
  xGA: { invertido: true, excelente: 0.7, acima: 1.1, abaixo: 1.5 },
  FD: { invertido: false, excelente: 5, acima: 3.5, abaixo: 2 },
  GCC: { invertido: false, excelente: 3, acima: 2, abaixo: 1 },
  TAA: { invertido: false, excelente: 22, acima: 16, abaixo: 10 },
  DS: { invertido: false, excelente: 16, acima: 12, abaixo: 8 },
  RTF: { invertido: false, excelente: 4, acima: 2.5, abaixo: 1.2 },
  DE: { invertido: false, excelente: 4, acima: 2.5, abaixo: 1.5 },
  FS: { invertido: true, excelente: 10, acima: 13, abaixo: 16 },
  CA: { invertido: true, excelente: 8, acima: 12, abaixo: 16 },
  CV: { invertido: true, excelente: 0.2, acima: 0.5, abaixo: 0.8 },
};

interface Quartis {
  q1: number;
  q2: number;
  q3: number;
}

function percentil(valores: number[], p: number): number {
  const ordenados = [...valores].sort((a, b) => a - b);
  if (ordenados.length === 1) return ordenados[0];
  const indice = (ordenados.length - 1) * p;
  const inferior = Math.floor(indice);
  const superior = Math.ceil(indice);
  if (inferior === superior) return ordenados[inferior];
  const peso = indice - inferior;
  return ordenados[inferior] * (1 - peso) + ordenados[superior] * peso;
}

export function calcularQuartis(valores: number[]): Quartis | null {
  if (valores.length === 0) return null;
  return {
    q1: percentil(valores, 0.25),
    q2: percentil(valores, 0.5),
    q3: percentil(valores, 0.75),
  };
}

function faixaPorQuartis(
  valor: number,
  quartis: Quartis,
  invertido: boolean
): FaixaMetrica {
  if (invertido) {
    if (valor <= quartis.q1) return "excelente";
    if (valor <= quartis.q2) return "acima";
    if (valor <= quartis.q3) return "abaixo";
    return "critico";
  }
  if (valor >= quartis.q3) return "excelente";
  if (valor >= quartis.q2) return "acima";
  if (valor >= quartis.q1) return "abaixo";
  return "critico";
}

function faixaPorLimitesEstaticos(
  valor: number,
  limites: { invertido: boolean; excelente: number; acima: number; abaixo: number }
): FaixaMetrica {
  const { invertido, excelente, acima, abaixo } = limites;
  if (invertido) {
    if (valor <= excelente) return "excelente";
    if (valor <= acima) return "acima";
    if (valor <= abaixo) return "abaixo";
    return "critico";
  }
  if (valor >= excelente) return "excelente";
  if (valor >= acima) return "acima";
  if (valor >= abaixo) return "abaixo";
  return "critico";
}

export function classificarFaixaMetrica(
  chave: ChaveMetricaScouts,
  valor: number,
  valoresColuna: number[]
): FaixaMetrica {
  const invertido = METRICAS_DEFENSIVAS.has(chave);
  const quartis = calcularQuartis(valoresColuna);

  if (quartis && valoresColuna.length >= 4) {
    return faixaPorQuartis(valor, quartis, invertido);
  }

  const limites = LIMITES_ESTATICOS[chave];
  if (limites) {
    return faixaPorLimitesEstaticos(valor, limites);
  }

  return "abaixo";
}

export function classeCelulaMetrica(faixa: FaixaMetrica): string {
  return CLASSES_FAIXA[faixa];
}

export function classeCelulaNeutra(): string {
  return "bg-slate-700/40 text-[var(--color-muted)]";
}
