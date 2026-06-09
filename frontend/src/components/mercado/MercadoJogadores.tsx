import { useMemo, useState } from "react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { traduzirSelecao } from "@/lib/traducoes";
import type { JogadorMercado, OddsJogadoresData, OddsJogadorEntry, PontuacaoCedida } from "@/types/dados";

// ---------------------------------------------------------------------------
// Tipos
// ---------------------------------------------------------------------------
const POSICOES = ["GOL", "LAT", "ZAG", "MEI", "ATA"] as const;
type BucketPos = (typeof POSICOES)[number];

interface ColDef {
  key: string;
  header: string;
  title: string;
  render: (j: JogadorMercado, ced: number | null, odds: OddsJogadorEntry | null) => React.ReactNode;
}

interface Props {
  jogadores: JogadorMercado[];
  pontuacaoCedida: PontuacaoCedida;
  oddsJogadores?: OddsJogadoresData | null;
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
}: {
  pct: number | null | undefined;
  casa: string | null | undefined;
  odds: number | null | undefined;
  tooltipPrefix?: string;
}) {
  if (pct === null || pct === undefined) return <Dash />;
  const tooltip =
    casa && odds
      ? `${tooltipPrefix} (${casa} - odd ${odds.toFixed(2)})`
      : undefined;
  const cor =
    pct >= 40
      ? "text-green-400"
      : pct >= 25
        ? "text-amber-400"
        : "text-[var(--color-fg)]";
  return (
    <span className={`tabular-nums font-medium ${cor}`} title={tooltip}>
      {pct.toFixed(1)}%
    </span>
  );
}


// ---------------------------------------------------------------------------
// Definições de colunas reutilizáveis
// ---------------------------------------------------------------------------

// Colunas com dados reais (eliminatórias + escala ELO)
const COL_RATING: ColDef = {
  key: "rating",
  header: "Rating",
  title: "Índice de recomendação 0–100 (Z-score composto × ELO)",
  render: (j) => (
    <span className="tabular-nums">
      {j.rating_recomendacao > 0 ? fmt(j.rating_recomendacao, 1) : <Dash />}
    </span>
  ),
};

const COL_MG: ColDef = {
  key: "mg",
  header: "MG",
  title: "Média geral",
  render: () => <Dash />,
};

const COL_MB: ColDef = {
  key: "mb",
  header: "MB",
  title: "Média básica",
  render: () => <Dash />,
};

const COL_CED: ColDef = {
  key: "ced",
  header: "CED",
  title: "Pontuação cedida pelo adversário",
  render: () => <Dash />,
};

const COL_ADV: ColDef = {
  key: "adv",
  header: "ADV",
  title: "Próximo adversário",
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

// Coluna de odds — marcar ou assistir
const COL_GA_PCT: ColDef = {
  key: "ga_pct",
  header: "GA%",
  title: "Probabilidade de marcar ou assistir — melhor odd disponível",
  render: (_j, _ced, odds) => (
    <PctOdds
      pct={odds?.ga_pct}
      casa={odds?.casa_ga}
      odds={odds?.odds_ga}
      tooltipPrefix="Probabilidade de marcar ou assistir"
    />
  ),
};

// Colunas de métricas da Copa (ainda sem dados — Copa não iniciou)
function copaDash(header: string, title: string): ColDef {
  return { key: header.toLowerCase().replace(/[^a-z0-9]/g, "_"), header, title, render: () => <Dash /> };
}

const COL_J       = copaDash("J",       "Partidas jogadas");
const COL_MIN     = copaDash("MIN",     "Minutos por jogo");
const COL_G       = copaDash("G",       "Gols");
const COL_A       = copaDash("A",       "Assistências");
const COL_SG      = copaDash("SG",      "Jogos sem sofrer gol");
const COL_DE      = copaDash("DE",      "Defesas");
const COL_DE_PCT  = copaDash("DE%",     "Porcentagem de defesas");
const COL_GE      = copaDash("GE",      "Gols evitados");
const COL_GS      = copaDash("GS",      "Gols sofridos");
const COL_DS      = copaDash("DS",      "Desarmes");
const COL_INT     = copaDash("INT",     "Interceptações na Copa");
const COL_C       = copaDash("C",       "Cortes efetivos na Copa");
const COL_BR      = copaDash("BR",      "Bolas recuperadas");
const COL_FD      = copaDash("FD",      "Finalizações defendidas");
const COL_GCC     = copaDash("GCC",     "Grandes chances criadas");
const COL_XG      = copaDash("xG",      "Gols esperados (Expected goals)");
const COL_XA      = copaDash("xA",      "Assistências esperadas (Expected assists)");
const COL_XGXA90  = copaDash("xG+xA/90'", "xG + xA por 90 minutos");

// ---------------------------------------------------------------------------
// Configuração de colunas por posição
// ---------------------------------------------------------------------------
const COLUNAS: Record<BucketPos, ColDef[]> = {
  GOL: [
    COL_RATING, COL_J, COL_MIN, COL_MG, COL_MB,
    COL_SG, COL_DE, COL_DE_PCT, COL_GE, COL_GS,
    COL_CED, COL_ADV,
  ],
  ZAG: [
    COL_RATING, COL_J, COL_MIN, COL_MG, COL_MB,
    COL_SG, COL_DS, COL_INT, COL_C, COL_BR, COL_FD,
    COL_GA_PCT,
    COL_CED, COL_ADV,
  ],
  LAT: [
    COL_RATING, COL_J, COL_MIN, COL_MG, COL_MB,
    COL_SG, COL_DS, COL_G, COL_A, COL_XGXA90, COL_GCC, COL_FD, COL_BR,
    COL_GA_PCT,
    COL_CED, COL_ADV,
  ],
  MEI: [
    COL_RATING, COL_J, COL_MIN, COL_MG, COL_MB,
    COL_G, COL_A, COL_GCC, COL_XG, COL_XA, COL_XGXA90, COL_FD, COL_DS,
    COL_GA_PCT,
    COL_CED, COL_ADV,
  ],
  ATA: [
    COL_RATING, COL_J, COL_MIN, COL_MG, COL_MB,
    COL_G, COL_A, COL_FD, COL_XG, COL_XA, COL_XGXA90,
    COL_GA_PCT,
    COL_CED, COL_ADV,
  ],
};

// ---------------------------------------------------------------------------
// Componente
// ---------------------------------------------------------------------------
export function MercadoJogadores({ jogadores, oddsJogadores }: Props) {
  const oddsMap = oddsJogadores?.odds ?? null;
  const [posicao,       setPosicao]       = useState<BucketPos>("ATA");
  const [selecaoFiltro, setSelecaoFiltro] = useState<string>("TODAS");
  const [statusFiltro,  setStatusFiltro]  = useState<string>("TODOS");

  const listaSelecoes = useMemo(
    () =>
      [...new Set(jogadores.map((j) => j.selecao))]
        .filter(Boolean)
        .sort((a, b) => a.localeCompare(b)),
    [jogadores],
  );

  const linhas = useMemo(
    () =>
      jogadores
        .filter((j) => j.bucket_posicao === posicao)
        .filter((j) => selecaoFiltro === "TODAS" || j.selecao === selecaoFiltro)
        .filter((j) => statusFiltro === "TODOS" || String(j.status_id) === statusFiltro)
        .sort((a, b) => (b.rating_recomendacao ?? 0) - (a.rating_recomendacao ?? 0))
        .slice(0, 500),
    [jogadores, posicao, selecaoFiltro, statusFiltro],
  );

  const colunas = COLUNAS[posicao];
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
            onValueChange={(v) => setPosicao(v as BucketPos)}
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
              {colunas.map((col) => (
                <th
                  key={col.key}
                  className="px-3 py-2 text-center"
                  title={col.title}
                >
                  {col.header}
                </th>
              ))}
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
                      ) : j.url_escudo ? (
                        <img
                          src={j.url_escudo}
                          alt={j.sigla}
                          className="h-8 w-8 shrink-0 object-contain"
                        />
                      ) : null}
                      <StatusDot statusId={j.status_id} />
                      <span className="font-medium">{j.apelido}</span>
                    </div>
                  </td>

                  {/* COLUNAS DINÂMICAS */}
                  {colunas.map((col) => {
                    const odds = oddsMap ? (oddsMap[String(j.atleta_id)] ?? null) : null;
                    return (
                      <td key={col.key} className="px-3 py-2 text-center">
                        {col.render(j, null, odds)}
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
