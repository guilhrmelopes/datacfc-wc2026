import { useMemo, useState } from "react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  calcularPotencialRodada,
  tooltipPotencialRodada,
} from "@/lib/potencialRodada";
import {
  cedidoAdversarioCopa,
  mediaBaseCopa,
  mediaGeralCopa,
  temCopa,
  xgXaPor90Copa,
} from "@/lib/copaJogador";
import {
  calcularRatingJogador,
  construirContextoRating,
  tooltipRating,
  type ConfrontoCopa,
} from "@/lib/ratingJogador";
import {
  amostraScoutPorPosicao,
  classeCelulaCartola,
  classeCelulaScoutJogador,
} from "@/lib/formatacaoJogadorCopa";
import { classeCorPerformance } from "@/lib/cores";
import { traduzirSelecao } from "@/lib/traducoes";
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

const HEADER_POTENCIAL_RODADA = (
  <span
    className="inline-flex h-4 w-4 items-center justify-center rounded-full border border-current text-[10px] font-serif italic leading-none"
    aria-hidden
  >
    i
  </span>
);

type Ordem = "asc" | "desc";

const COLUNAS_NAO_ORDENAVEIS = new Set(["adv"]);

interface Props {
  jogadores: JogadorMercado[];
  selecoes: Selecao[];
  confrontosCopa: ConfrontoCopa[];
  partidasProcessadas: string[];
  oddsJogadores?: OddsJogadoresData | null;
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
  ativo = true,
}: {
  pct: number | null | undefined;
  casa: string | null | undefined;
  odds: number | null | undefined;
  tooltipPrefix?: string;
  ativo?: boolean;
}) {
  if (!ativo || pct === null || pct === undefined) return <Dash />;
  const tooltip =
    casa && odds
      ? `${tooltipPrefix} (${casa} - odd ${odds.toFixed(2)})`
      : undefined;
  return (
    <span className="tabular-nums font-medium" title={tooltip}>
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
  title: "Pontuação cedida pelo adversário",
  sortable: false,
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

const COL_POTENCIAL_RODADA: ColDef = {
  key: "potencial_r1",
  header: HEADER_POTENCIAL_RODADA,
  title: "Potencial para Rodada",
  render: () => null,
};

// Coluna de odds — marcar ou assistir
const COL_GA_PCT: ColDef = {
  key: "ga_pct",
  header: "GA%",
  title: "Probabilidade de participar de gol",
  render: (j, _ced, odds) => (
    <PctOdds
      pct={odds?.ga_pct}
      casa={odds?.casa_ga}
      odds={odds?.odds_ga}
      tooltipPrefix="Probabilidade de marcar ou assistir"
      ativo={temCopa(j)}
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
      ativo={temCopa(j)}
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
  (j) => (temCopa(j) && j.copa_jogos_num ? (j.copa_mins_played ?? 0) / j.copa_jogos_num : null),
  1,
);
const COL_G = copaCol("g", "G", "Gols", (j) =>
  temCopa(j) ? (j.copa_goals ?? 0) : null,
);
const COL_A = copaCol("a", "A", "Assistências", (j) =>
  temCopa(j) ? (j.copa_goal_assist ?? 0) : null,
);
const COL_SG = copaCol("sg", "SG", "Jogos sem sofrer gols", (j) =>
  temCopa(j) ? (j.copa_clean_sheet ?? 0) : null,
);
const COL_DE = copaCol("de", "DE", "Defesas", (j) =>
  temCopa(j) ? (j.copa_de ?? 0) : null,
);
const COL_DE_PCT = copaCol(
  "de_pct",
  "DE%",
  "Defesas por 90 minutos",
  (j) => (temCopa(j) ? (j.copa_de_pct ?? null) : null),
  2,
);
const COL_GE = copaCol(
  "ge",
  "GE",
  "Gols evitados",
  (j) => (temCopa(j) ? (j.copa_ge ?? 0) : null),
  2,
);
const COL_GS = copaCol("gs", "GS", "Gols sofridos na Copa", (j) =>
  temCopa(j) ? (j.copa_gs ?? 0) : null,
);
const COL_DS = copaCol("ds", "DS", "Desarmes", (j) =>
  temCopa(j) ? (j.copa_ds ?? 0) : null,
);
const COL_INT = copaCol("int", "INT", "Interceptações", (j) =>
  temCopa(j) ? (j.copa_int ?? 0) : null,
);
const COL_C = copaCol("c", "C", "Cortes", (j) =>
  temCopa(j) ? (j.copa_c ?? 0) : null,
);
const COL_BR = copaCol("br", "BR", "Bolas recuperadas", (j) =>
  temCopa(j) ? (j.copa_br ?? 0) : null,
);
const COL_FD = copaCol("fd", "FD", "Finalizações defendidas", (j) =>
  temCopa(j) ? (j.copa_fd ?? 0) : null,
);
const COL_GCC = copaCol("gcc", "GCC", "Grandes chances criadas", (j) =>
  temCopa(j) ? (j.copa_gcc ?? 0) : null,
);
const COL_XG = copaCol("xg", "xG", "Gols esperados", (j) =>
  temCopa(j) ? (j.copa_xg ?? 0) : null,
  2,
);
const COL_XA = copaCol("xa", "xA", "Assistências esperadas", (j) =>
  temCopa(j) ? (j.copa_xa ?? 0) : null,
  2,
);
const COL_XGXA90 = copaCol(
  "xgx_a90",
  "xG+xA/90'",
  "xG + xA por 90 minutos",
  (j) => xgXaPor90Copa(j),
  2,
);

function classeCelulaProbabilidade(pct: number | null | undefined): string {
  if (pct === null || pct === undefined) return "";
  if (pct <= 0) return "bg-red-500/15";
  if (pct >= 40) return "bg-green-500/15";
  if (pct >= 25) return "bg-yellow-500/15";
  return "bg-orange-500/15";
}

function classeCelulaHub(
  colKey: string,
  j: JogadorMercado,
  ced: number | null,
  jogadores: JogadorMercado[],
  odds: OddsJogadorEntry | null,
  escalas: ReturnType<typeof construirContextoRating>,
): string {
  if (colKey === "adv") {
    return j.proximo_adversario_escudo ? "bg-sky-500/20" : "";
  }

  if (colKey === "ced") {
    return ced != null ? classeCorPerformance(ced) : "";
  }

  if (colKey === "ga_pct") {
    return temCopa(j) ? classeCelulaProbabilidade(odds?.ga_pct) : "";
  }
  if (colKey === "sg_pct") {
    return temCopa(j) ? classeCelulaProbabilidade(odds?.sg_pct) : "";
  }
  if (colKey === "potencial_r1") {
    const valor = calcularPotencialRodada(j, odds, escalas);
    return valor != null ? classeCelulaCartola(valor) : "";
  }

  if (!temCopa(j)) return "";

  const pos = j.bucket_posicao;

  if (colKey === "rating") {
    const mg = mediaGeralCopa(j);
    return mg != null ? classeCelulaCartola(mg) : "";
  }
  if (colKey === "mg") {
    const mg = mediaGeralCopa(j);
    return mg != null ? classeCelulaCartola(mg) : "";
  }
  if (colKey === "mb") {
    const mb = mediaBaseCopa(j);
    return mb != null ? classeCelulaCartola(mb) : "";
  }
  if (colKey === "j") {
    const jogos = j.copa_jogos_num ?? 0;
    const amostra = amostraScoutPorPosicao(jogadores, pos, (x) =>
      x.copa_jogos_num ? x.copa_jogos_num : null,
    );
    return classeCelulaScoutJogador("j", jogos, amostra);
  }
  if (colKey === "min" && j.copa_jogos_num) {
    const min = (j.copa_mins_played ?? 0) / j.copa_jogos_num;
    const amostra = amostraScoutPorPosicao(jogadores, pos, (x) =>
      x.copa_jogos_num ? (x.copa_mins_played ?? 0) / x.copa_jogos_num : null,
    );
    return classeCelulaScoutJogador("min", min, amostra);
  }

  const scoutMap: Record<string, (x: JogadorMercado) => number | null> = {
    g: (x) => x.copa_goals ?? 0,
    a: (x) => x.copa_goal_assist ?? 0,
    sg: (x) => x.copa_clean_sheet ?? 0,
    de: (x) => x.copa_de ?? 0,
    de_pct: (x) => x.copa_de_pct ?? null,
    ge: (x) => x.copa_ge ?? 0,
    gs: (x) => x.copa_gs ?? 0,
    ds: (x) => x.copa_ds ?? 0,
    int: (x) => x.copa_int ?? 0,
    c: (x) => x.copa_c ?? 0,
    br: (x) => x.copa_br ?? 0,
    fd: (x) => x.copa_fd ?? 0,
    gcc: (x) => x.copa_gcc ?? 0,
    xg: (x) => x.copa_xg ?? 0,
    xa: (x) => x.copa_xa ?? 0,
    xgx_a90: (x) => xgXaPor90Copa(x),
  };

  const extrair = scoutMap[colKey];
  if (!extrair) return "";

  const valor = extrair(j);
  if (valor === null) return "";
  const amostra = amostraScoutPorPosicao(jogadores, pos, extrair);
  return classeCelulaScoutJogador(colKey, valor, amostra);
}

// ---------------------------------------------------------------------------
// Ordenação
// ---------------------------------------------------------------------------

function valorOrdenacao(
  j: JogadorMercado,
  colKey: string,
  odds: OddsJogadorEntry | null,
  escalas: ReturnType<typeof construirContextoRating>,
): number | null {
  switch (colKey) {
    case "rating":
      return temCopa(j) ? calcularRatingJogador(j, escalas) : null;
    case "mg":
      return mediaGeralCopa(j);
    case "mb":
      return mediaBaseCopa(j);
    case "ga_pct":
      return temCopa(j) ? (odds?.ga_pct ?? null) : null;
    case "sg_pct":
      return temCopa(j) ? (odds?.sg_pct ?? null) : null;
    case "potencial_r1":
      return calcularPotencialRodada(j, odds, escalas);
    case "j":
      return temCopa(j) ? (j.copa_jogos_num ?? null) : null;
    case "min":
      return temCopa(j) && j.copa_jogos_num
        ? (j.copa_mins_played ?? 0) / j.copa_jogos_num
        : null;
    case "g":
      return temCopa(j) ? (j.copa_goals ?? 0) : null;
    case "a":
      return temCopa(j) ? (j.copa_goal_assist ?? 0) : null;
    case "sg":
      return temCopa(j) ? (j.copa_clean_sheet ?? 0) : null;
    default:
      return null;
  }
}

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
    COL_CED, COL_ADV, COL_POTENCIAL_RODADA,
  ],
  ZAG: [
    COL_RATING, COL_J, COL_MIN, COL_MG, COL_MB,
    COL_SG, COL_DS, COL_INT, COL_C, COL_BR, COL_FD,
    COL_SG_PCT, COL_GA_PCT,
    COL_CED, COL_ADV, COL_POTENCIAL_RODADA,
  ],
  LAT: [
    COL_RATING, COL_J, COL_MIN, COL_MG, COL_MB,
    COL_SG, COL_DS, COL_G, COL_A, COL_XGXA90, COL_GCC, COL_FD, COL_BR,
    COL_SG_PCT, COL_GA_PCT,
    COL_CED, COL_ADV, COL_POTENCIAL_RODADA,
  ],
  MEI: [
    COL_RATING, COL_J, COL_MIN, COL_MG, COL_MB,
    COL_G, COL_A, COL_GCC, COL_XG, COL_XA, COL_XGXA90, COL_FD, COL_DS,
    COL_GA_PCT,
    COL_CED, COL_ADV, COL_POTENCIAL_RODADA,
  ],
  ATA: [
    COL_RATING, COL_J, COL_MIN, COL_MG, COL_MB,
    COL_G, COL_A, COL_FD, COL_XG, COL_XA, COL_XGXA90,
    COL_GA_PCT,
    COL_CED, COL_ADV, COL_POTENCIAL_RODADA,
  ],
};

// ---------------------------------------------------------------------------
// Componente
// ---------------------------------------------------------------------------
export function MercadoJogadores({
  jogadores,
  selecoes,
  confrontosCopa,
  partidasProcessadas,
  oddsJogadores,
  pontuacaoCedida,
}: Props) {
  const oddsMap = oddsJogadores?.odds ?? null;
  const escalasRating = useMemo(
    () => construirContextoRating(selecoes, confrontosCopa, partidasProcessadas),
    [selecoes, confrontosCopa, partidasProcessadas],
  );
  const [posicao,       setPosicao]       = useState<BucketPos>("ATA");
  const [selecaoFiltro, setSelecaoFiltro] = useState<string>("TODAS");
  const [statusFiltro,  setStatusFiltro]  = useState<string>("TODOS");
  const [ordenarPor,    setOrdenarPor]    = useState<string>("rating");
  const [ordem,         setOrdem]         = useState<Ordem>("desc");

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
      .filter((j) => j.bucket_posicao === posicao)
      .filter((j) => selecaoFiltro === "TODAS" || j.selecao === selecaoFiltro)
      .filter((j) => statusFiltro === "TODOS" || String(j.status_id) === statusFiltro);

    const dados = [...filtradas];
    dados.sort((a, b) => {
      const oddsA = oddsMap ? (oddsMap[String(a.atleta_id)] ?? null) : null;
      const oddsB = oddsMap ? (oddsMap[String(b.atleta_id)] ?? null) : null;
      return compararValores(
        valorOrdenacao(a, ordenarPor, oddsA, escalasRating),
        valorOrdenacao(b, ordenarPor, oddsB, escalasRating),
        ordem,
      );
    });
    return dados.slice(0, 500);
  }, [jogadores, posicao, selecaoFiltro, statusFiltro, ordenarPor, ordem, oddsMap, escalasRating]);

  const colunas = useMemo(() => {
    return COLUNAS[posicao].map((col) => {
      if (col.key === "rating") {
        return {
          ...col,
          render: (j: JogadorMercado) => {
            const valor = calcularRatingJogador(j, escalasRating);
            return (
              <span className="tabular-nums" title={tooltipRating(j, valor, escalasRating)}>
                {temCopa(j) && valor > 0 ? fmt(valor, 1) : <Dash />}
              </span>
            );
          },
        };
      }
      if (col.key === "potencial_r1") {
        return {
          ...col,
          render: (j: JogadorMercado, _ced: number | null, odds: OddsJogadorEntry | null) => {
            const valor = calcularPotencialRodada(j, odds, escalasRating);
            return (
              <span
                className="tabular-nums font-medium"
                title={tooltipPotencialRodada(j, odds, valor, escalasRating)}
              >
                {valor != null ? fmt(valor, 1) : <Dash />}
              </span>
            );
          },
        };
      }
      return col;
    });
  }, [posicao, escalasRating]);
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
              {STATUS_ORDEM.map((id) => (
                <SelectItem key={id} value={String(id)}>
                  <span className="flex items-center gap-2">
                    <span className={`inline-block h-2 w-2 rounded-full ${STATUS_MAP[id].cor}`} />
                    {STATUS_MAP[id].label}
                  </span>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <span className="text-xs text-[var(--color-muted)]">
          {linhas.length} jogador{linhas.length !== 1 ? "es" : ""}
        </span>
      </div>

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
                  className="border-t border-[var(--color-border)] transition-colors hover:bg-[var(--color-card)]/40"
                >
                  {/* JOGADOR */}
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-2">
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
                    </div>
                  </td>

                  {/* COLUNAS DINÂMICAS */}
                  {colunas.map((col) => {
                    const odds = oddsMap ? (oddsMap[String(j.atleta_id)] ?? null) : null;
                    const ced = cedidoAdversarioCopa(j, pontuacaoCedida);
                    const corCelula = classeCelulaHub(
                      col.key,
                      j,
                      ced,
                      jogadores,
                      odds,
                      escalasRating,
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
