import { useMemo, useState } from "react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { IconesCobrador } from "@/components/mercado/IconesCobrador";
import {
  compilarIndiceCobradores,
  type CobradoresCopaData,
} from "@/lib/cobradoresCopa";
import {
  mlContextoParaMapa,
  type MlContextoRodadaData,
} from "@/lib/mlContextoRodada";
import {
  tooltipPotencialRodada,
} from "@/lib/potencialRodada";
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
import {
  tooltipRating,
  construirContextoRating,
  type ConfrontoCopa,
} from "@/lib/ratingJogador";
import { traduzirSelecao } from "@/lib/traducoes";
import type { ContextoMlRodada } from "@/lib/fatorMoneylineRodada";
import { gaPctCalculado, gaPctEfetivo } from "@/lib/oddsGaFallback";
import {
  construirIndiceMercadoHub,
} from "@/lib/indiceMercadoHub";
import type {
  JogadorMercado,
  OddsJogadoresData,
  OddsJogadorEntry,
  PontuacaoCedida,
  Selecao,
} from "@/types/dados";

// ---------------------------------------------------------------------------
// Tipos
// ---------------------------------------------------------------------------
const POSICOES = ["GOL", "LAT", "ZAG", "MEI", "ATA"] as const;
type BucketPos = (typeof POSICOES)[number];

interface ColDef {
  key: string;
  header: React.ReactNode;
  title: string;
  sortable?: boolean;
  render: (j: JogadorMercado, ced: number | null, odds: OddsJogadorEntry | null) => React.ReactNode;
}

const HEADER_SCORE = "SCORE";

type Ordem = "asc" | "desc";

const COLUNAS_NAO_ORDENAVEIS = new Set(["adv"]);

interface Props {
  jogadores: JogadorMercado[];
  selecoes: Selecao[];
  confrontosCopa: ConfrontoCopa[];
  partidasProcessadas: string[];
  oddsJogadores?: OddsJogadoresData | null;
  mlContextoRodada?: MlContextoRodadaData | null;
  cobradoresCopa?: CobradoresCopaData | null;
  rodadaCartolaAtual?: number;
  pontuacaoCedida: PontuacaoCedida;
}

// ---------------------------------------------------------------------------
// Status dos jogadores
// ---------------------------------------------------------------------------
const STATUS_MAP: Record<number, { label: string; cor: string }> = {
  6: { label: "Provável",  cor: "bg-green-500"  },
  2: { label: "Dúvida",    cor: "bg-amber-400"  },
  5: { label: "Suspenso",  cor: "bg-red-500"    },
  3: { label: "Lesionado", cor: "bg-orange-500" },
  7: { label: "Nulo",      cor: "bg-gray-400"   },
};

const STATUS_ORDEM = [6, 2, 5, 3, 7] as const;
const FILTRO_PROVAVEL_DUVIDA = "6+2";

function passaFiltroStatus(statusId: number, filtro: string): boolean {
  if (filtro === "TODOS") return true;
  if (filtro === FILTRO_PROVAVEL_DUVIDA) return statusId === 6 || statusId === 2;
  return String(statusId) === filtro;
}

function StatusDotFiltro({ statusId }: { statusId: number | typeof FILTRO_PROVAVEL_DUVIDA }) {
  if (statusId === FILTRO_PROVAVEL_DUVIDA) {
    return (
      <span
        className="inline-block h-2 w-2 shrink-0 overflow-hidden rounded-full"
        title="Provável + Dúvida"
        aria-hidden
      >
        <span className="flex h-full w-full">
          <span className="h-full w-1/2 bg-green-500" />
          <span className="h-full w-1/2 bg-amber-400" />
        </span>
      </span>
    );
  }
  const s = STATUS_MAP[statusId as number];
  if (!s) return null;
  return (
    <span
      className={`inline-block h-2 w-2 shrink-0 rounded-full ${s.cor}`}
      title={s.label}
    />
  );
}

function EscudoSelecao({ j }: { j: JogadorMercado }) {
  if (!j.url_escudo) return null;
  return (
    <span
      className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-sm border border-[var(--color-border)] bg-[var(--color-card)] p-0.5"
      title={traduzirSelecao(j.selecao)}
    >
      <img
        src={j.url_escudo}
        alt={j.sigla ?? j.selecao}
        className="h-full w-full object-contain"
      />
    </span>
  );
}

function StatusDot({ statusId }: { statusId: number }) {
  const s = STATUS_MAP[statusId];
  if (!s) return null;
  return (
    <span
      className={`inline-block h-2.5 w-2.5 shrink-0 rounded-full ${s.cor}`}
      title={s.label}
    />
  );
}

// ---------------------------------------------------------------------------
// Helpers de formatação
// ---------------------------------------------------------------------------
function fmt(valor: number | null | undefined, casas = 1): string {
  if (valor === null || valor === undefined) return "—";
  return valor.toFixed(casas);
}

function Dash() {
  return <span className="text-[var(--color-muted)]">—</span>;
}

function PctOdds({
  pct,
  casa,
  odds,
  tooltipPrefix = "Probabilidade",
  tooltip,
  ativo = true,
}: {
  pct: number | null | undefined;
  casa: string | null | undefined;
  odds: number | null | undefined;
  tooltipPrefix?: string;
  tooltip?: string;
  ativo?: boolean;
}) {
  if (!ativo || pct === null || pct === undefined) return <Dash />;
  const tooltipFinal =
    tooltip ??
    (casa && odds
      ? `${tooltipPrefix} (${casa} - odd ${odds.toFixed(2)})`
      : tooltipPrefix);
  return (
    <span className="tabular-nums font-medium" title={tooltipFinal}>
      {pct.toFixed(1)}%
    </span>
  );
}


// ---------------------------------------------------------------------------
// Definições de colunas reutilizáveis
// ---------------------------------------------------------------------------

// Colunas com dados da Copa 2026 (FotMob + Cartola)
const COL_RATING: ColDef = {
  key: "rating",
  header: "Rating",
  title: "Nível de atuação na Copa ponderado pelo nível dos adversários enfrentados",
  render: () => null,
};

const COL_MG: ColDef = {
  key: "mg",
  header: "MG",
  title: "Média Geral",
  render: (j) => {
    const mg = mediaGeralCopa(j);
    return mg != null ? <span className="tabular-nums">{fmt(mg, 2)}</span> : <Dash />;
  },
};

const COL_MB: ColDef = {
  key: "mb",
  header: "MB",
  title: "Média Básica",
  render: (j) => {
    const mb = mediaBaseCopa(j);
    return mb != null ? <span className="tabular-nums">{fmt(mb, 2)}</span> : <Dash />;
  },
};

const COL_CED: ColDef = {
  key: "ced",
  header: "CED",
  title: "Pontuação cedida acumulada na Copa pelo próximo adversário",
  render: (_j, ced) =>
    ced != null ? <span className="tabular-nums">{fmt(ced, 2)}</span> : <Dash />,
};

const COL_ADV: ColDef = {
  key: "adv",
  header: "ADV",
  title: "Próximo adversário",
  sortable: false,
  render: (j) =>
    j.proximo_adversario_escudo ? (
      <div className="flex flex-col items-center gap-0.5">
        <img
          src={j.proximo_adversario_escudo}
          alt={j.proximo_adversario_sigla ?? ""}
          className="h-6 w-6 object-contain"
          title={j.proximo_adversario_sigla ?? ""}
        />
        <span className="text-[9px] font-bold text-[var(--color-muted)]">
          {j.proximo_adversario_sigla}
        </span>
      </div>
    ) : (
      <Dash />
    ),
};

const COL_SCORE: ColDef = {
  key: "score",
  header: HEADER_SCORE,
  title: "SCORE — 65% Rating + 35% odds da rodada (ajustado por status e ML)",
  sortable: true,
  render: () => null,
};

const COL_G_PCT: ColDef = {
  key: "g_pct",
  header: "G%",
  title: "Probabilidade de marcar",
  render: (j, _ced, odds) => (
    <PctOdds
      pct={odds?.g_pct}
      casa={odds?.casa_g}
      odds={odds?.odds_g}
      tooltipPrefix="Probabilidade de marcar"
      ativo={oddsVigentes(j, odds)}
    />
  ),
};

const COL_A_PCT: ColDef = {
  key: "a_pct",
  header: "A%",
  title: "Probabilidade de assistir",
  render: (j, _ced, odds) => (
    <PctOdds
      pct={odds?.a_pct}
      casa={odds?.casa_a}
      odds={odds?.odds_a}
      tooltipPrefix="Probabilidade de assistir"
      ativo={oddsVigentes(j, odds)}
    />
  ),
};

const COL_GA_PCT: ColDef = {
  key: "ga_pct",
  header: "GA%",
  title: "Probabilidade de marcar ou assistir",
  render: (j, _ced, odds) => (
    <PctOdds
      pct={odds?.ga_pct}
      casa={odds?.casa_ga}
      odds={odds?.odds_ga}
      tooltipPrefix="Probabilidade de marcar ou assistir"
      ativo={oddsVigentes(j, odds)}
    />
  ),
};

const COL_SG_PCT: ColDef = {
  key: "sg_pct",
  header: "SG%",
  title: "Probabilidade de não sofrer gol na rodada (odds Copa)",
  render: (j, _ced, odds) => (
    <PctOdds
      pct={odds?.sg_pct}
      casa={odds?.casa_sg}
      odds={odds?.odds_sg}
      tooltipPrefix="Probabilidade de não sofrer gol"
      ativo={oddsVigentes(j, odds)}
    />
  ),
};

function copaCol(
  key: string,
  header: string,
  title: string,
  valor: (j: JogadorMercado) => number | null,
  casas = 0,
): ColDef {
  return {
    key,
    header,
    title,
    render: (j) => {
      const v = valor(j);
      if (v === null) return <Dash />;
      return <span className="tabular-nums">{fmt(v, casas)}</span>;
    },
  };
}

const COL_J = copaCol("j", "J", "Número de jogos", (j) =>
  temCopa(j) ? (j.copa_jogos_num ?? 0) : null,
);
const COL_MIN = copaCol(
  "min",
  "MIN",
  "Minutos por jogo",
  (j) => minutosPorJogoCopa(j),
  1,
);
const COL_G = copaCol("g", "G", "Gols por jogo", (j) =>
  scoutPorJogoCopa(j, j.copa_goals),
);
const COL_A = copaCol("a", "A", "Assistências por jogo", (j) =>
  scoutPorJogoCopa(j, j.copa_goal_assist),
);
const COL_SG = copaCol("sg", "SG", "SG por jogo", (j) =>
  scoutPorJogoCopa(j, j.copa_clean_sheet),
);
const COL_DE = copaCol("de", "DE", "Defesas por jogo", (j) =>
  scoutPorJogoCopa(j, j.copa_de),
);
const COL_DE_PCT = copaCol(
  "de_pct",
  "DE%",
  "Defesas por 90 minutos",
  (j) => dePctPor90Copa(j),
  2,
);
const COL_GE = copaCol(
  "ge",
  "GE",
  "Gols evitados por jogo",
  (j) => scoutPorJogoCopa(j, j.copa_ge),
  2,
);
const COL_GS = copaCol("gs", "GS", "Gols sofridos por jogo", (j) =>
  scoutPorJogoCopa(j, j.copa_gs),
);
const COL_DS = copaCol("ds", "DS", "Desarmes por jogo", (j) =>
  scoutPorJogoCopa(j, j.copa_ds),
);
const COL_INT = copaCol("int", "INT", "Interceptações por jogo", (j) =>
  scoutPorJogoCopa(j, j.copa_int),
);
const COL_C = copaCol("c", "C", "Cortes por jogo", (j) =>
  scoutPorJogoCopa(j, j.copa_c),
);
const COL_BR = copaCol("br", "BR", "Bolas recuperadas por jogo", (j) =>
  scoutPorJogoCopa(j, j.copa_br),
);
const COL_FD = copaCol("fd", "FD", "Finalizações defendidas por jogo", (j) =>
  scoutPorJogoCopa(j, j.copa_fd),
);
const COL_GCC = copaCol("gcc", "GCC", "Grandes chances criadas por jogo", (j) =>
  scoutPorJogoCopa(j, j.copa_gcc),
);
const COL_XG = copaCol("xg", "xG", "Gols esperados por 90 minutos", (j) =>
  xgPor90Copa(j),
  2,
);
const COL_XA = copaCol("xa", "xA", "Assistências esperadas por 90 minutos", (j) =>
  xaPor90Copa(j),
  2,
);
const COL_XGXA90 = copaCol(
  "xgx_a90",
  "xG+xA/90'",
  "xG + xA por 90 minutos",
  (j) => xgXaPor90Copa(j),
  2,
);

function compararValores(va: number | null, vb: number | null, ordem: Ordem): number {
  if (va === null && vb === null) return 0;
  if (va === null) return 1;
  if (vb === null) return -1;
  return ordem === "asc" ? va - vb : vb - va;
}

// ---------------------------------------------------------------------------
// Configuração de colunas por posição
// ---------------------------------------------------------------------------
const COLUNAS: Record<BucketPos, ColDef[]> = {
  GOL: [
    COL_RATING, COL_J, COL_MIN, COL_MG, COL_MB,
    COL_SG_PCT,
    COL_SG, COL_DE, COL_DE_PCT, COL_GE, COL_GS,
    COL_CED, COL_ADV, COL_SCORE,
  ],
  ZAG: [
    COL_RATING, COL_J, COL_MIN, COL_MG, COL_MB,
    COL_SG, COL_DS, COL_INT, COL_C, COL_BR, COL_FD,
    COL_SG_PCT, COL_G_PCT, COL_A_PCT, COL_GA_PCT,
    COL_CED, COL_ADV, COL_SCORE,
  ],
  LAT: [
    COL_RATING, COL_J, COL_MIN, COL_MG, COL_MB,
    COL_SG, COL_DS, COL_G, COL_A, COL_XGXA90, COL_GCC, COL_FD, COL_BR,
    COL_SG_PCT, COL_G_PCT, COL_A_PCT, COL_GA_PCT,
    COL_CED, COL_ADV, COL_SCORE,
  ],
  MEI: [
    COL_RATING, COL_J, COL_MIN, COL_MG, COL_MB,
    COL_G, COL_A, COL_GCC, COL_XG, COL_XA, COL_XGXA90, COL_FD, COL_DS,
    COL_G_PCT, COL_A_PCT, COL_GA_PCT,
    COL_CED, COL_ADV, COL_SCORE,
  ],
  ATA: [
    COL_RATING, COL_J, COL_MIN, COL_MG, COL_MB,
    COL_G, COL_A, COL_FD, COL_XG, COL_XA, COL_XGXA90,
    COL_G_PCT, COL_A_PCT, COL_GA_PCT,
    COL_CED, COL_ADV, COL_SCORE,
  ],
};

/** Colunas comuns quando a comparação mistura posições (GOL + ATA, etc.). */
const COLUNAS_COMPARACAO: ColDef[] = [
  COL_RATING, COL_J, COL_MIN, COL_MG, COL_MB,
  COL_G_PCT, COL_A_PCT, COL_GA_PCT,
  COL_CED, COL_ADV, COL_SCORE,
];

// ---------------------------------------------------------------------------
// Componente
// ---------------------------------------------------------------------------
export function MercadoJogadores({
  jogadores,
  selecoes,
  confrontosCopa,
  partidasProcessadas,
  oddsJogadores,
  mlContextoRodada,
  cobradoresCopa,
  pontuacaoCedida,
}: Props) {
  const oddsMap = oddsJogadores?.odds ?? null;
  const mlCtxRodada = useMemo(
    (): ContextoMlRodada | null => mlContextoParaMapa(mlContextoRodada),
    [mlContextoRodada],
  );
  const indiceCobradores = useMemo(
    () => compilarIndiceCobradores(cobradoresCopa),
    [cobradoresCopa],
  );
  const escalasRating = useMemo(
    () => construirContextoRating(selecoes, confrontosCopa, partidasProcessadas),
    [selecoes, confrontosCopa, partidasProcessadas],
  );
  const indice = useMemo(
    () =>
      construirIndiceMercadoHub(
        jogadores,
        oddsMap,
        escalasRating,
        mlCtxRodada,
        pontuacaoCedida,
      ),
    [jogadores, oddsMap, escalasRating, mlCtxRodada, pontuacaoCedida],
  );
  const [posicao,       setPosicao]       = useState<BucketPos>("ATA");
  const [selecaoFiltro, setSelecaoFiltro] = useState<string>("TODAS");
  const [statusFiltro,  setStatusFiltro]  = useState<string>("TODOS");
  const [ordenarPor,    setOrdenarPor]    = useState<string>("rating");
  const [ordem,         setOrdem]         = useState<Ordem>("desc");
  const [selecionados,  setSelecionados]  = useState<Set<number>>(() => new Set());
  const [modoComparacao, setModoComparacao] = useState(false);

  function toggleSelecao(atletaId: number) {
    setSelecionados((prev) => {
      const next = new Set(prev);
      if (next.has(atletaId)) next.delete(atletaId);
      else next.add(atletaId);
      return next;
    });
  }

  function iniciarComparacao() {
    if (selecionados.size >= 2) setModoComparacao(true);
  }

  function sairComparacao() {
    setModoComparacao(false);
    setSelecionados(new Set());
  }

  function handlePosicaoChange(v: BucketPos) {
    setPosicao(v);
    setOrdenarPor("rating");
    setOrdem("desc");
  }

  function alternarOrdenacao(colKey: string) {
    if (COLUNAS_NAO_ORDENAVEIS.has(colKey)) return;
    if (ordenarPor === colKey) {
      setOrdem((o) => (o === "asc" ? "desc" : "asc"));
    } else {
      setOrdenarPor(colKey);
      setOrdem("desc");
    }
  }

  const listaSelecoes = useMemo(
    () =>
      [...new Set(jogadores.map((j) => j.selecao))]
        .filter(Boolean)
        .sort((a, b) =>
          traduzirSelecao(a).localeCompare(traduzirSelecao(b), "pt-BR", {
            sensitivity: "base",
          }),
        ),
    [jogadores],
  );

  const linhas = useMemo(() => {
    const filtradas = jogadores
      .filter((j) => modoComparacao || j.bucket_posicao === posicao)
      .filter((j) => selecaoFiltro === "TODAS" || j.selecao === selecaoFiltro)
      .filter((j) => passaFiltroStatus(j.status_id, statusFiltro))
      .filter((j) => !modoComparacao || selecionados.has(j.atleta_id));

    const dados = [...filtradas];
    dados.sort((a, b) => {
      const advA = a.proximo_adversario_sigla ?? null;
      const advB = b.proximo_adversario_sigla ?? null;
      const cmp = compararValores(
        indice.valorOrdenacao(a, ordenarPor, advA),
        indice.valorOrdenacao(b, ordenarPor, advB),
        ordem,
      );
      if (cmp !== 0) return cmp;
      return a.apelido.localeCompare(b.apelido, "pt-BR", { sensitivity: "base" });
    });
    const limitadas = dados.slice(0, modoComparacao ? 50 : 500);
    return limitadas;
  }, [
    jogadores,
    posicao,
    selecaoFiltro,
    statusFiltro,
    ordenarPor,
    ordem,
    indice,
    modoComparacao,
    selecionados,
  ]);

  const qtdSelecionados = selecionados.size;
  const bucketsComparacaoMista =
    modoComparacao &&
    new Set(
      [...selecionados]
        .map((id) => jogadores.find((j) => j.atleta_id === id)?.bucket_posicao)
        .filter(Boolean),
    ).size > 1;

  const colunas = useMemo(() => {
    const buckets = [...new Set(linhas.map((j) => j.bucket_posicao))];
    const bucketCols =
      modoComparacao && buckets.length !== 1
        ? null
        : modoComparacao && buckets.length === 1
          ? (buckets[0] as BucketPos)
          : posicao;
    const defs = bucketCols ? COLUNAS[bucketCols] : COLUNAS_COMPARACAO;
    return defs.map((col) => {
      if (col.key === "rating") {
        return {
          ...col,
          render: (j: JogadorMercado) => {
            const oddsVal = indice.oddsAtivas.get(j.atleta_id) ?? null;
            const valor = indice.ratings.get(j.atleta_id) ?? 0;
            return (
              <span
                className="tabular-nums"
                title={tooltipRating(j, valor, escalasRating, mlCtxRodada, j.sigla, oddsVal)}
              >
                {temCopa(j) && valor > 0 ? fmt(valor, 1) : <Dash />}
              </span>
            );
          },
        };
      }
      if (col.key === "score") {
        return {
          ...col,
          render: (j: JogadorMercado, _ced: number | null, odds: OddsJogadorEntry | null) => {
            const oddsVal = odds ?? indice.oddsAtivas.get(j.atleta_id) ?? null;
            const valor = indice.scores.get(j.atleta_id) ?? null;
            return (
              <span
                className="tabular-nums font-medium"
                title={tooltipPotencialRodada(j, oddsVal, valor, escalasRating, true, mlCtxRodada, j.sigla)}
              >
                {valor != null ? fmt(valor, 1) : <Dash />}
              </span>
            );
          },
        };
      }
      if (["g_pct", "a_pct", "ga_pct", "sg_pct"].includes(col.key)) {
        return {
          ...col,
          render: (j: JogadorMercado, _ced: number | null, odds: OddsJogadorEntry | null) => {
            const oddsVal = odds ?? indice.oddsAtivas.get(j.atleta_id) ?? null;
            const ativo = oddsVal != null;
            if (col.key === "ga_pct") {
              const ga = gaPctEfetivo(oddsVal);
              const calculado = gaPctCalculado(oddsVal);
              return (
                <PctOdds
                  pct={ga}
                  casa={calculado ? null : oddsVal?.casa_ga}
                  odds={calculado ? null : oddsVal?.odds_ga}
                  tooltipPrefix="Probabilidade de marcar ou assistir"
                  tooltip={
                    calculado && oddsVal?.g_pct != null && oddsVal?.a_pct != null
                      ? `GA% estimado: G% ${oddsVal.g_pct.toFixed(1)} + A% ${oddsVal.a_pct.toFixed(1)} (independência)`
                      : undefined
                  }
                  ativo={ativo}
                />
              );
            }
            const props =
              col.key === "g_pct"
                ? { pct: oddsVal?.g_pct, casa: oddsVal?.casa_g, odds: oddsVal?.odds_g, tooltipPrefix: "Probabilidade de marcar" }
                : col.key === "a_pct"
                  ? { pct: oddsVal?.a_pct, casa: oddsVal?.casa_a, odds: oddsVal?.odds_a, tooltipPrefix: "Probabilidade de assistir" }
                  : { pct: oddsVal?.sg_pct, casa: oddsVal?.casa_sg, odds: oddsVal?.odds_sg, tooltipPrefix: "Probabilidade de não sofrer gol" };
            return <PctOdds {...props} ativo={ativo} />;
          },
        };
      }
      return col;
    });
  }, [posicao, escalasRating, mlCtxRodada, indice, modoComparacao]);
  const totalCols = 1 + colunas.length; // 1 = coluna JOGADOR

  return (
    <div className="space-y-4">
      {/* ---------------------------------------------------------------- */}
      {/* Filtros                                                           */}
      {/* ---------------------------------------------------------------- */}
      <div className="flex flex-wrap items-end gap-4">
        {/* Posição */}
        <div>
          <label className="mb-1 block text-xs text-[var(--color-muted)]">
            Posição
          </label>
          <Select
            value={posicao}
            onValueChange={(v) => handlePosicaoChange(v as BucketPos)}
          >
            <SelectTrigger className="w-[100px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {POSICOES.map((p) => (
                <SelectItem key={p} value={p}>
                  {p}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Seleção */}
        <div>
          <label className="mb-1 block text-xs text-[var(--color-muted)]">
            Seleção
          </label>
          <Select value={selecaoFiltro} onValueChange={setSelecaoFiltro}>
            <SelectTrigger className="min-w-[200px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="TODAS">Todas</SelectItem>
              {listaSelecoes.map((s) => (
                <SelectItem key={s} value={s}>
                  {traduzirSelecao(s)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Status */}
        <div>
          <label className="mb-1 block text-xs text-[var(--color-muted)]">
            Status
          </label>
          <Select value={statusFiltro} onValueChange={setStatusFiltro}>
            <SelectTrigger className="w-[150px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="TODOS">Todos</SelectItem>
              {STATUS_ORDEM.flatMap((id) => {
                const item = (
                  <SelectItem key={id} value={String(id)}>
                    <span className="flex items-center gap-2">
                      <StatusDotFiltro statusId={id} />
                      {STATUS_MAP[id].label}
                    </span>
                  </SelectItem>
                );
                if (id !== 2) return [item];
                return [
                  item,
                  <SelectItem key={FILTRO_PROVAVEL_DUVIDA} value={FILTRO_PROVAVEL_DUVIDA}>
                    <span className="flex items-center gap-2">
                      <StatusDotFiltro statusId={FILTRO_PROVAVEL_DUVIDA} />
                      Provável + Dúvida
                    </span>
                  </SelectItem>,
                ];
              })}
            </SelectContent>
          </Select>
        </div>

        <span className="text-xs text-[var(--color-muted)]">
          {linhas.length} jogador{linhas.length !== 1 ? "es" : ""}
          {modoComparacao ? " · comparação" : null}
        </span>

        <div className="ml-auto flex flex-wrap items-center gap-2">
          {modoComparacao ? (
            <button
              type="button"
              onClick={sairComparacao}
              className="rounded-md border border-[var(--color-border)] bg-[var(--color-card)] px-3 py-1.5 text-xs font-medium text-[var(--color-fg)] transition-colors hover:bg-[var(--color-border)]/40"
            >
              Sair da comparação
            </button>
          ) : qtdSelecionados >= 2 ? (
            <button
              type="button"
              onClick={iniciarComparacao}
              className="rounded-md bg-sky-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-sky-500"
            >
              Comparar ({qtdSelecionados})
            </button>
          ) : qtdSelecionados === 1 ? (
            <span className="text-xs text-[var(--color-muted)]">
              Selecione mais 1 jogador
            </span>
          ) : null}
        </div>
      </div>

      {modoComparacao ? (
        <p className="rounded-md border border-sky-500/30 bg-sky-500/10 px-3 py-2 text-xs text-sky-200/90">
          Modo comparação: exibindo {linhas.length} jogador
          {linhas.length !== 1 ? "es" : ""} selecionado{linhas.length !== 1 ? "s" : ""}.
          Troque posição ou filtros para incluir outros atletas na seleção.
        </p>
      ) : null}

      {/* ---------------------------------------------------------------- */}
      {/* Tabela                                                            */}
      {/* ---------------------------------------------------------------- */}
      <div className="overflow-x-auto rounded-lg border border-[var(--color-border)]">
        <table className="w-full min-w-[960px] text-left text-sm">
          <thead className="bg-[var(--color-card)] text-xs uppercase tracking-wide text-[var(--color-muted)]">
            <tr>
              <th className="px-3 py-2">Jogador</th>
              {colunas.map((col) => {
                const sortable = col.sortable !== false && !COLUNAS_NAO_ORDENAVEIS.has(col.key);
                return (
                  <th
                    key={col.key}
                    className={
                      sortable
                        ? "cursor-pointer px-3 py-2 text-center hover:text-[var(--color-fg)] select-none"
                        : "px-3 py-2 text-center"
                    }
                    title={col.title}
                    onClick={sortable ? () => alternarOrdenacao(col.key) : undefined}
                  >
                    {col.header}
                    {sortable && ordenarPor === col.key ? (ordem === "asc" ? " ↑" : " ↓") : ""}
                  </th>
                );
              })}
            </tr>
          </thead>

          <tbody>
            {linhas.length === 0 ? (
              <tr>
                <td
                  colSpan={totalCols}
                  className="px-3 py-8 text-center text-sm text-[var(--color-muted)]"
                >
                  Nenhum jogador encontrado para os filtros selecionados.
                </td>
              </tr>
            ) : (
              linhas.map((j) => (
                <tr
                  key={j.atleta_id}
                  className={`border-t border-[var(--color-border)] transition-colors hover:bg-[var(--color-card)]/40 ${
                    selecionados.has(j.atleta_id) ? "bg-sky-500/5" : ""
                  }`}
                >
                  {/* JOGADOR */}
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={selecionados.has(j.atleta_id)}
                        onChange={() => toggleSelecao(j.atleta_id)}
                        aria-label={`Selecionar ${j.apelido} para comparar`}
                        className="h-3.5 w-3.5 shrink-0 cursor-pointer rounded border-[var(--color-border)] accent-sky-500"
                      />
                      {j.foto_url ? (
                        <img
                          src={j.foto_url}
                          alt={j.apelido}
                          className="h-8 w-8 shrink-0 rounded-full object-cover"
                        />
                      ) : null}
                      <StatusDot statusId={j.status_id} />
                      <EscudoSelecao j={j} />
                      <span className="font-medium">{j.apelido}</span>
                      {modoComparacao && bucketsComparacaoMista ? (
                        <span className="rounded bg-[var(--color-border)]/60 px-1 py-0.5 text-[10px] font-medium uppercase text-[var(--color-muted)]">
                          {j.bucket_posicao}
                        </span>
                      ) : null}
                      <IconesCobrador cobrador={indiceCobradores.get(j.atleta_id)} />
                    </div>
                  </td>

                  {/* COLUNAS DINÂMICAS */}
                  {colunas.map((col) => {
                    const odds = indice.oddsAtivas.get(j.atleta_id) ?? null;
                    const ced = cedidoAdversarioCopa(
                      j,
                      pontuacaoCedida,
                      j.proximo_adversario_sigla ?? null,
                    );
                    const corCelula = indice.classeCelula(
                      col.key,
                      j,
                      ced,
                      Boolean(j.proximo_adversario_escudo),
                    );
                    return (
                      <td
                        key={col.key}
                        className={`px-3 py-2 text-center ${corCelula}`}
                      >
                        {col.render(j, ced, odds)}
                      </td>
                    );
                  })}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
