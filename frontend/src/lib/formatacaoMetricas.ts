/** Formatação condicional de métricas coletivas (Scouts) e índices derivados. */

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
  "FS",
]);

/** Métricas em que valor menor é melhor. */
export const METRICAS_DEFENSIVAS: ReadonlySet<ChaveMetricaScouts> = new Set([
  "GS",
  "xGA",
  "CA",
  "CV",
]);

export type FaixaMetrica = "excelente" | "acima" | "abaixo" | "critico";

/** BOM / MEDIANO / RUIM na aba Scouts (seleções). */
export type FaixaMetrica3 = "bom" | "mediano" | "ruim";

/** Mínimo de jogos por seleção para recalibrar limiares pela amostra da Copa. */
export const MIN_JOGOS_RECALIBRACAO = 3;

/** Seleções com J≥3 necessárias para quartis confiáveis na recalibração. */
export const MIN_AMOSTRA_RECALIBRACAO = 4;

export interface ContextoMetricaSelecao {
  /** Jogos disputados na Copa — usado em SG (taxa de clean sheets). */
  jogos?: number;
  /** Valores da coluna (seleções com J≥3 quando recalibração ativa). */
  amostraColuna?: number[];
  /** Maior J entre seleções visíveis na tabela. */
  maxJogosAmostra?: number;
  /** Recalibração por quartis da Copa ativa (max J ≥ 3 e amostra suficiente). */
  recalibAtiva?: boolean;
}

/**
 * Paleta Wyscout / InStat para tabelas densas (4 faixas — comparação relativa entre pares).
 */
const CLASSES_FAIXA: Record<FaixaMetrica, string> = {
  excelente: "bg-emerald-600/22 text-[var(--color-fg)]",
  acima: "bg-lime-500/18 text-[var(--color-fg)]",
  abaixo: "bg-amber-500/18 text-[var(--color-fg)]",
  critico: "bg-rose-600/20 text-[var(--color-fg)]",
};

/** Scouts seleções: verde / âmbar / vermelho (BOM / MEDIANO / RUIM). */
const CLASSES_FAIXA_SELECAO: Record<FaixaMetrica3, string> = {
  bom: "bg-emerald-600/22 text-[var(--color-fg)]",
  mediano: "bg-amber-500/18 text-[var(--color-fg)]",
  ruim: "bg-rose-600/20 text-[var(--color-fg)]",
};

/**
 * Limiares absolutos por métrica (valores por jogo ≈ por 90 em partidas completas).
 * Referências: Wyscout percentis de ligas top, StatsBomb/Opta (xG, xGA), médias de Copas e UCL.
 *
 * | Métrica | BOM | MEDIANO | RUIM | Lógica |
 * |---------|-----|---------|------|--------|
 * | GM | ≥1,8 | 0,9–1,79 | <0,9 | Produção ofensiva elite ~2,0/jogo |
 * | GS | ≤0,7 | 0,71–1,4 | >1,4 | Defesas elite <1,0 sofrido |
 * | POS% | ≥55 | 45–54,9 | <45 | Domínio de bola (contexto tático) |
 * | SG | taxa ≥67% | 34–66% | 0% | Clean sheets / jogos (SG÷J) |
 * | xG | ≥1,6 | 0,9–1,59 | <0,9 | Processo ofensivo (StatsBomb) |
 * | xGA | ≤0,8 | 0,81–1,3 | >1,3 | Processo defensivo elite <1,0 |
 * | FD | ≥5 | 3–4,9 | <3 | Finalizações no alvo |
 * | GCC | ≥2,5 | 1,5–2,49 | <1,5 | Grandes chances criadas |
 * | TAA | ≥22 | 12–21,9 | <12 | Toques na área (presença ofensiva) |
 * | DS | ≥16 | 10–15,9 | <10 | Intensidade defensiva / pressing |
 * | RTF | ≥4 | 2–3,9 | <2 | Recuperações no terço final |
 * | DE | ≥3 | 1,5–2,9 | <1,5 | Volume de defesas (GK sob demanda) |
 * | FS | ≥14 | 10–13,9 | <10 | Faltas sofridas (verticalidade) |
 * | CA | ≤1,5 | 1,6–3 | >3 | Disciplina |
 * | CV | 0 | — | ≥1 | Cartão vermelho = ruim imediato |
 */
interface LimiarSelecao {
  invertido: boolean;
  bom: number;
  ruim: number;
  classificar?: (valor: number, contexto?: ContextoMetricaSelecao) => FaixaMetrica3;
}

const LIMIARES_SELECAO: Record<ChaveMetricaScouts, LimiarSelecao> = {
  GM: { invertido: false, bom: 1.8, ruim: 0.9 },
  GS: { invertido: true, bom: 0.7, ruim: 1.4 },
  "POS%": { invertido: false, bom: 55, ruim: 45 },
  SG: {
    invertido: false,
    bom: 1,
    ruim: 0,
    classificar(valor, contexto) {
      const jogos = contexto?.jogos ?? 1;
      if (jogos <= 0) return "mediano";
      const taxa = valor / jogos;
      if (taxa >= 0.67) return "bom";
      if (taxa >= 0.34) return "mediano";
      return "ruim";
    },
  },
  xG: { invertido: false, bom: 1.6, ruim: 0.9 },
  xGA: { invertido: true, bom: 0.8, ruim: 1.3 },
  FD: { invertido: false, bom: 5, ruim: 3 },
  GCC: { invertido: false, bom: 2.5, ruim: 1.5 },
  TAA: { invertido: false, bom: 22, ruim: 12 },
  DS: { invertido: false, bom: 16, ruim: 10 },
  RTF: { invertido: false, bom: 4, ruim: 2 },
  DE: { invertido: false, bom: 3, ruim: 1.5 },
  FS: { invertido: false, bom: 14, ruim: 10 },
  CA: { invertido: true, bom: 1.5, ruim: 3 },
  CV: {
    invertido: true,
    bom: 0,
    ruim: 0.5,
    classificar(valor) {
      if (valor <= 0) return "bom";
      return "ruim";
    },
  },
};

/** Limites legados (4 faixas) para fallback quando não há amostra relativa. */
const LIMITES_ESTATICOS: Partial<
  Record<ChaveMetricaScouts, { invertido: boolean; excelente: number; acima: number; abaixo: number }>
> = {
  GM: { invertido: false, excelente: 1.8, acima: 1.2, abaixo: 0.6 },
  GS: { invertido: true, excelente: 0.6, acima: 1.0, abaixo: 1.4 },
  "POS%": { invertido: false, excelente: 58, acima: 50, abaixo: 42 },
  SG: { invertido: false, excelente: 1, acima: 0.5, abaixo: 0.1 },
  xG: { invertido: false, excelente: 1.8, acima: 1.2, abaixo: 0.7 },
  xGA: { invertido: true, excelente: 0.7, acima: 1.1, abaixo: 1.5 },
  FD: { invertido: false, excelente: 5, acima: 3.5, abaixo: 2 },
  GCC: { invertido: false, excelente: 3, acima: 2, abaixo: 1 },
  TAA: { invertido: false, excelente: 22, acima: 16, abaixo: 10 },
  DS: { invertido: false, excelente: 16, acima: 12, abaixo: 8 },
  RTF: { invertido: false, excelente: 4, acima: 2.5, abaixo: 1.2 },
  DE: { invertido: false, excelente: 4, acima: 2.5, abaixo: 1.5 },
  FS: { invertido: false, excelente: 14, acima: 12, abaixo: 10 },
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
  invertido: boolean,
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
  limites: { invertido: boolean; excelente: number; acima: number; abaixo: number },
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

function classificarTresNiveis(
  valor: number,
  limiar: LimiarSelecao,
  contexto?: ContextoMetricaSelecao,
): FaixaMetrica3 {
  if (limiar.classificar) {
    return limiar.classificar(valor, contexto);
  }

  const { invertido, bom, ruim } = limiar;
  if (invertido) {
    if (valor <= bom) return "bom";
    if (valor <= ruim) return "mediano";
    return "ruim";
  }
  if (valor >= bom) return "bom";
  if (valor >= ruim) return "mediano";
  return "ruim";
}

function recalibracaoDisponivel(contexto?: ContextoMetricaSelecao): boolean {
  return (
    (contexto?.maxJogosAmostra ?? 0) >= MIN_JOGOS_RECALIBRACAO &&
    (contexto?.amostraColuna?.length ?? 0) >= MIN_AMOSTRA_RECALIBRACAO
  );
}

function classificarPorQuartisSelecao(
  valor: number,
  amostra: number[],
  invertido: boolean,
): FaixaMetrica3 {
  const quartis = calcularQuartis(amostra);
  if (!quartis) return "mediano";
  if (invertido) {
    if (valor <= quartis.q1) return "bom";
    if (valor <= quartis.q3) return "mediano";
    return "ruim";
  }
  if (valor >= quartis.q3) return "bom";
  if (valor >= quartis.q1) return "mediano";
  return "ruim";
}

/** Normaliza valor bruto para comparação (ex.: SG → taxa por jogo). */
export function valorNormalizadoMetricaSelecao(
  chave: ChaveMetricaScouts,
  valor: number,
  jogos = 1,
): number {
  if (chave === "SG" && jogos > 0) return valor / jogos;
  return valor;
}

/** Classificação para métricas coletivas — benchmark fixo ou quartis da Copa (J≥3). */
export function classificarFaixaMetricaSelecao(
  chave: ChaveMetricaScouts,
  valor: number,
  contexto?: ContextoMetricaSelecao,
): FaixaMetrica3 {
  const limiar = LIMIARES_SELECAO[chave];
  const invertido = limiar.invertido;

  if (chave === "CV") {
    return limiar.classificar!(valor, contexto);
  }

  const jogos = contexto?.jogos ?? 1;
  const valorComparavel = valorNormalizadoMetricaSelecao(chave, valor, jogos);

  if (recalibracaoDisponivel(contexto)) {
    const amostra = contexto!.amostraColuna!;
    return classificarPorQuartisSelecao(valorComparavel, amostra, invertido);
  }

  if (chave === "SG") {
    return limiar.classificar!(valor, contexto);
  }

  return classificarTresNiveis(valorComparavel, limiar, contexto);
}

export function classeCelulaMetricaSelecao(faixa: FaixaMetrica3): string {
  return CLASSES_FAIXA_SELECAO[faixa];
}

/** Fallback relativo entre pares (jogadores) — quartis Wyscout. */
export function classificarFaixaMetrica(
  chave: ChaveMetricaScouts,
  valor: number,
  valoresColuna: number[],
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
  return "bg-slate-700/30 text-[var(--color-muted)]";
}

/** Faixa absoluta para índices 0–100 (Rating, Potencial). */
export function classificarFaixaIndice100(valor: number): FaixaMetrica {
  if (valor >= 75) return "excelente";
  if (valor >= 50) return "acima";
  if (valor >= 25) return "abaixo";
  return "critico";
}

/** Faixa absoluta para pontuação Cartola por jogo (MG, MB) — 4 níveis legado. */
export function classificarFaixaCartola(valor: number): FaixaMetrica {
  if (valor <= 2.5) return "critico";
  if (valor <= 3.99) return "abaixo";
  if (valor <= 5.5) return "acima";
  return "excelente";
}

/**
 * Pontuação Cartola cedido/conquistado — 3 faixas (Recorrência).
 * Conquistado: maior é melhor. Cedido: menor é melhor (invertido).
 */
export function classificarFaixaCartolaSelecao(
  valor: number,
  invertido = false,
): FaixaMetrica3 {
  if (invertido) {
    if (valor <= 2.5) return "bom";
    if (valor <= 5.5) return "mediano";
    return "ruim";
  }
  if (valor > 5.5) return "bom";
  if (valor > 2.5) return "mediano";
  return "ruim";
}

/** Quartis relativos ao grupo (estilo Wyscout — comparação entre pares). */
export function classificarFaixaRelativa(
  valor: number,
  amostra: number[],
  invertido = false,
): FaixaMetrica {
  const quartis = calcularQuartis(amostra);
  if (quartis && amostra.length >= 4) {
    return faixaPorQuartis(valor, quartis, invertido);
  }
  return invertido ? "acima" : "abaixo";
}

/** Célula para índice 0–100: quartis entre pares quando possível, senão faixas absolutas. */
export function classeCelulaIndice100(valor: number, amostra?: number[]): string {
  const faixa =
    amostra && amostra.length >= 4
      ? classificarFaixaRelativa(valor, amostra, false)
      : classificarFaixaIndice100(valor);
  return classeCelulaMetrica(faixa);
}

const LEGENDA_RECALIBRACAO =
  "Quartis Copa (J≥3): verde=Q4 · âmbar=Q2–Q3 · vermelho=Q1";

/** Texto de referência dos limiares (tooltip / legenda). */
export function descricaoLimiarMetrica(
  chave: ChaveMetricaScouts,
  recalibAtiva = false,
): string {
  if (recalibAtiva && chave !== "CV") {
    return LEGENDA_RECALIBRACAO;
  }

  const limiar = LIMIARES_SELECAO[chave];
  if (chave === "SG") {
    return "BOM ≥67% de SG · MEDIANO 34–66% · RUIM 0% (SG÷J)";
  }
  if (chave === "CV") {
    return "BOM 0 CV · RUIM ≥1 CV por jogo";
  }
  if (limiar.invertido) {
    return `BOM ≤${limiar.bom} · MEDIANO ${limiar.bom}–${limiar.ruim} · RUIM >${limiar.ruim}`;
  }
  return `BOM ≥${limiar.bom} · MEDIANO ${limiar.ruim}–${limiar.bom} · RUIM <${limiar.ruim}`;
}

export function descricaoLimiarCartolaRecorrencia(tipo: "conquistado" | "cedido"): string {
  if (tipo === "cedido") {
    return "BOM ≤2,5 · MEDIANO 2,51–5,5 · RUIM >5,5 (menos cedido = melhor)";
  }
  return "BOM >5,5 · MEDIANO 2,51–5,5 · RUIM ≤2,5 (mais conquistado = melhor)";
}
