import {
  cedidoAdversarioCopa,
  dePctPor90Copa,
  mediaBaseCopa,
  mediaGeralCopa,
  minutosPorJogoCopa,
  oddsVigentes,
  scoutPorJogoCopa,
  temCopa,
  xaPor90Copa,
  xgPor90Copa,
  xgXaPor90Copa,
} from "@/lib/copaJogador";
import { classeCorPerformance } from "@/lib/cores";
import {
  amostraScoutPorPosicao,
  classeCelulaCartola,
  classeCelulaScoutJogador,
} from "@/lib/formatacaoJogadorCopa";
import { classeCelulaIndice100 } from "@/lib/formatacaoMetricas";
import type { ContextoMlRodada } from "@/lib/fatorMoneylineRodada";
import { gaPctEfetivo } from "@/lib/oddsGaFallback";
import { calcularPotencialRodada } from "@/lib/potencialRodada";
import {
  calcularRatingJogador,
  type ContextoRating,
} from "@/lib/ratingJogador";
import type {
  JogadorMercado,
  OddsJogadorEntry,
  PontuacaoCedida,
} from "@/types/dados";

type BucketPos = "GOL" | "LAT" | "ZAG" | "MEI" | "ATA";

const POSICOES: BucketPos[] = ["GOL", "LAT", "ZAG", "MEI", "ATA"];

const EXTRATORES_SCOUT: Record<string, (j: JogadorMercado) => number | null> = {
  g: (j) => scoutPorJogoCopa(j, j.copa_goals),
  a: (j) => scoutPorJogoCopa(j, j.copa_goal_assist),
  sg: (j) => scoutPorJogoCopa(j, j.copa_clean_sheet),
  de: (j) => scoutPorJogoCopa(j, j.copa_de),
  de_pct: (j) => dePctPor90Copa(j),
  ge: (j) => scoutPorJogoCopa(j, j.copa_ge),
  gs: (j) => scoutPorJogoCopa(j, j.copa_gs),
  ds: (j) => scoutPorJogoCopa(j, j.copa_ds),
  int: (j) => scoutPorJogoCopa(j, j.copa_int),
  c: (j) => scoutPorJogoCopa(j, j.copa_c),
  br: (j) => scoutPorJogoCopa(j, j.copa_br),
  fd: (j) => scoutPorJogoCopa(j, j.copa_fd),
  gcc: (j) => scoutPorJogoCopa(j, j.copa_gcc),
  xg: (j) => xgPor90Copa(j),
  xa: (j) => xaPor90Copa(j),
  xgx_a90: (j) => xgXaPor90Copa(j),
  j: (j) => (j.copa_jogos_num ? j.copa_jogos_num : null),
  min: (j) => minutosPorJogoCopa(j),
};

export interface IndiceMercadoHub {
  oddsAtivas: Map<number, OddsJogadorEntry | null>;
  ratings: Map<number, number>;
  scores: Map<number, number | null>;
  sortCache: Map<number, Record<string, number | null>>;
  classeCelula: (
    colKey: string,
    j: JogadorMercado,
    ced: number | null,
    temAdv: boolean,
  ) => string;
  valorOrdenacao: (j: JogadorMercado, colKey: string, advSigla: string | null) => number | null;
}

function amostrasPorPosicao(
  jogadores: JogadorMercado[],
  posicao: string,
  extrair: (j: JogadorMercado) => number | null,
): number[] {
  return amostraScoutPorPosicao(jogadores, posicao, extrair);
}

export function construirIndiceMercadoHub(
  jogadores: JogadorMercado[],
  oddsMap: Record<string, OddsJogadorEntry> | null,
  escalas: ContextoRating,
  mlCtx: ContextoMlRodada | null,
  pontuacaoCedida: PontuacaoCedida,
): IndiceMercadoHub {
  const oddsAtivas = new Map<number, OddsJogadorEntry | null>();
  const ratings = new Map<number, number>();
  const scores = new Map<number, number | null>();
  const sortCache = new Map<number, Record<string, number | null>>();
  const amostras = new Map<string, Map<string, number[]>>();

  const resolverOdds = (j: JogadorMercado): OddsJogadorEntry | null =>
    oddsMap?.[String(j.atleta_id)] ?? null;

  for (const j of jogadores) {
    const raw = resolverOdds(j);
    const ativa = oddsVigentes(j, raw) ? raw : null;
    oddsAtivas.set(j.atleta_id, ativa);
  }

  for (const j of jogadores) {
    if (!temCopa(j)) continue;
    const odds = oddsAtivas.get(j.atleta_id) ?? null;
    ratings.set(j.atleta_id, calcularRatingJogador(j, escalas, mlCtx, j.sigla, odds));
    scores.set(
      j.atleta_id,
      calcularPotencialRodada(j, odds, escalas, true, mlCtx, j.sigla),
    );
  }

  for (const pos of POSICOES) {
    const porCol = new Map<string, number[]>();

    for (const [colKey, extrair] of Object.entries(EXTRATORES_SCOUT)) {
      porCol.set(colKey, amostrasPorPosicao(jogadores, pos, extrair));
    }

    porCol.set(
      "rating",
      amostrasPorPosicao(jogadores, pos, (j) => {
        const r = ratings.get(j.atleta_id);
        return r != null && r > 0 ? r : null;
      }),
    );

    porCol.set(
      "score",
      amostrasPorPosicao(jogadores, pos, (j) => scores.get(j.atleta_id) ?? null),
    );

    porCol.set(
      "g_pct",
      amostrasPorPosicao(jogadores, pos, (j) => oddsAtivas.get(j.atleta_id)?.g_pct ?? null),
    );
    porCol.set(
      "a_pct",
      amostrasPorPosicao(jogadores, pos, (j) => oddsAtivas.get(j.atleta_id)?.a_pct ?? null),
    );
    porCol.set(
      "ga_pct",
      amostrasPorPosicao(jogadores, pos, (j) => gaPctEfetivo(oddsAtivas.get(j.atleta_id) ?? null)),
    );
    porCol.set(
      "sg_pct",
      amostrasPorPosicao(jogadores, pos, (j) => oddsAtivas.get(j.atleta_id)?.sg_pct ?? null),
    );

    amostras.set(pos, porCol);
  }

  for (const j of jogadores) {
    const odds = oddsAtivas.get(j.atleta_id) ?? null;
    const adv = j.proximo_adversario_sigla ?? null;
    sortCache.set(j.atleta_id, {
      rating: temCopa(j) ? (ratings.get(j.atleta_id) ?? null) : null,
      mg: mediaGeralCopa(j),
      mb: mediaBaseCopa(j),
      ced: cedidoAdversarioCopa(j, pontuacaoCedida, adv),
      g_pct: odds?.g_pct ?? null,
      a_pct: odds?.a_pct ?? null,
      ga_pct: gaPctEfetivo(odds),
      sg_pct: odds?.sg_pct ?? null,
      score: scores.get(j.atleta_id) ?? null,
      j: temCopa(j) ? (j.copa_jogos_num ?? null) : null,
      min: minutosPorJogoCopa(j),
      g: EXTRATORES_SCOUT.g(j),
      a: EXTRATORES_SCOUT.a(j),
      sg: EXTRATORES_SCOUT.sg(j),
      de: EXTRATORES_SCOUT.de(j),
      de_pct: EXTRATORES_SCOUT.de_pct(j),
      ge: EXTRATORES_SCOUT.ge(j),
      gs: EXTRATORES_SCOUT.gs(j),
      ds: EXTRATORES_SCOUT.ds(j),
      int: EXTRATORES_SCOUT.int(j),
      c: EXTRATORES_SCOUT.c(j),
      br: EXTRATORES_SCOUT.br(j),
      fd: EXTRATORES_SCOUT.fd(j),
      gcc: EXTRATORES_SCOUT.gcc(j),
      xg: EXTRATORES_SCOUT.xg(j),
      xa: EXTRATORES_SCOUT.xa(j),
      xgx_a90: temCopa(j) ? EXTRATORES_SCOUT.xgx_a90(j) : null,
    });
  }

  function classeCelula(
    colKey: string,
    j: JogadorMercado,
    ced: number | null,
    temAdv: boolean,
  ): string {
    if (colKey === "adv") return temAdv ? "bg-sky-500/20" : "";
    if (colKey === "ced") return ced != null ? classeCorPerformance(ced) : "";

    const pos = j.bucket_posicao;
    const amostraPos = amostras.get(pos);
    const odds = oddsAtivas.get(j.atleta_id) ?? null;

    if (colKey === "g_pct") {
      if (!odds?.g_pct) return "";
      return classeCelulaIndice100(odds.g_pct, amostraPos?.get("g_pct") ?? []);
    }
    if (colKey === "a_pct") {
      if (!odds?.a_pct) return "";
      return classeCelulaIndice100(odds.a_pct, amostraPos?.get("a_pct") ?? []);
    }
    if (colKey === "ga_pct") {
      const ga = gaPctEfetivo(odds);
      if (ga == null) return "";
      return classeCelulaIndice100(ga, amostraPos?.get("ga_pct") ?? []);
    }
    if (colKey === "sg_pct") {
      if (!odds?.sg_pct) return "";
      return classeCelulaIndice100(odds.sg_pct, amostraPos?.get("sg_pct") ?? []);
    }
    if (colKey === "score") {
      const valor = scores.get(j.atleta_id);
      if (valor == null) return "";
      return classeCelulaIndice100(valor, amostraPos?.get("score") ?? []);
    }

    if (!temCopa(j)) return "";

    if (colKey === "rating") {
      const valor = ratings.get(j.atleta_id) ?? 0;
      if (valor <= 0) return "";
      return classeCelulaIndice100(valor, amostraPos?.get("rating") ?? []);
    }
    if (colKey === "mg") {
      const mg = mediaGeralCopa(j);
      return mg != null ? classeCelulaCartola(mg) : "";
    }
    if (colKey === "mb") {
      const mb = mediaBaseCopa(j);
      return mb != null ? classeCelulaCartola(mb) : "";
    }

    const extrair = EXTRATORES_SCOUT[colKey];
    if (!extrair) return "";
    const valor = extrair(j);
    if (valor === null) return "";
    return classeCelulaScoutJogador(colKey, valor, amostraPos?.get(colKey) ?? []);
  }

  function valorOrdenacao(
    j: JogadorMercado,
    colKey: string,
    _advSigla: string | null,
  ): number | null {
    return sortCache.get(j.atleta_id)?.[colKey] ?? null;
  }

  return {
    oddsAtivas,
    ratings,
    scores,
    sortCache,
    classeCelula,
    valorOrdenacao,
  };
}
