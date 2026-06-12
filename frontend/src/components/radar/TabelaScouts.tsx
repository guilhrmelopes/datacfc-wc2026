import { useMemo, useState } from "react";
import {
  type ChaveMetricaScouts,
  classificarFaixaMetrica,
  classeCelulaMetrica,
  classeCelulaNeutra,
} from "@/lib/formatacaoMetricas";
import { formatarValorMetrica, valorNumericoOuNull } from "@/lib/exibirValor";
import { estreouCopa, calcularRatingSelecaoCopa } from "@/lib/ratingSelecao";
import { TOOLTIPS_METRICAS, traduzirSelecao } from "@/lib/traducoes";
import type { Selecao } from "@/types/dados";

const COLUNAS: { chave: ChaveMetricaScouts; campo: keyof Selecao["metricas_coletivas"] }[] =
  [
    { chave: "GM", campo: "goals_team_match" },
    { chave: "GS", campo: "goals_conceded_team_match" },
    { chave: "POS%", campo: "possession_percentage_team" },
    { chave: "SG", campo: "clean_sheet_team" },
    { chave: "xG", campo: "expected_goals_team" },
    { chave: "xGA", campo: "expected_goals_conceded_team" },
    { chave: "FD", campo: "ontarget_scoring_att_team" },
    { chave: "GCC", campo: "big_chance_team" },
    { chave: "TAA", campo: "touches_in_opp_box_team" },
    { chave: "DS", campo: "total_tackle_team" },
    { chave: "RTF", campo: "poss_won_att_3rd_team" },
    { chave: "DE", campo: "saves_team" },
    { chave: "FS", campo: "fk_foul_lost_team" },
    { chave: "CA", campo: "total_yel_card_team" },
    { chave: "CV", campo: "total_red_card_team" },
  ];

type Ordem = "asc" | "desc";

interface Props {
  selecoes: Selecao[];
  competicao: string;
  grupo: string;
}

function filtrarSelecoes(selecoes: Selecao[], competicao: string, grupo: string) {
  return selecoes.filter((s) => {
    const okCompeticao =
      competicao === "TODAS" || s.competicao === competicao;
    const okGrupo = grupo === "TODOS" || s.grupo === grupo;
    return okCompeticao && okGrupo;
  });
}

export function TabelaScouts({ selecoes, competicao, grupo }: Props) {
  const [ordenarPor, setOrdenarPor] = useState<string>("rating_elo_100");
  const [ordem, setOrdem] = useState<Ordem>("desc");

  const linhasFiltradas = useMemo(
    () => filtrarSelecoes(selecoes, competicao, grupo),
    [selecoes, competicao, grupo]
  );

  const valoresPorMetrica = useMemo(() => {
    const mapa = new Map<ChaveMetricaScouts, number[]>();
    for (const col of COLUNAS) {
      const valores = linhasFiltradas
        .filter(estreouCopa)
        .map((s) => valorNumericoOuNull(s.metricas_coletivas[col.campo] ?? 0))
        .filter((v): v is number => v !== null);
      mapa.set(col.chave, valores);
    }
    return mapa;
  }, [linhasFiltradas]);

  const linhas = useMemo(() => {
    const dados = [...linhasFiltradas];
    dados.sort((a, b) => {
      const compararNumero = (va: number | null, vb: number | null) => {
        if (va === null && vb === null) return 0;
        if (va === null) return 1;
        if (vb === null) return -1;
        return ordem === "asc" ? va - vb : vb - va;
      };

      if (ordenarPor === "selecao") {
        const cmp = a.selecao.localeCompare(b.selecao);
        return ordem === "asc" ? cmp : -cmp;
      }
      if (ordenarPor === "competicao") {
        const cmp = (a.competicao ?? "").localeCompare(b.competicao ?? "");
        return ordem === "asc" ? cmp : -cmp;
      }
      if (ordenarPor === "rating_elo_100") {
        return compararNumero(
          calcularRatingSelecaoCopa(a, linhasFiltradas),
          calcularRatingSelecaoCopa(b, linhasFiltradas),
        );
      }
      if (ordenarPor === "J") {
        return compararNumero(
          valorNumericoOuNull(a.metricas_coletivas.J),
          valorNumericoOuNull(b.metricas_coletivas.J)
        );
      }
      const col = COLUNAS.find((c) => c.chave === ordenarPor);
      if (col) {
        return compararNumero(
          valorNumericoOuNull(a.metricas_coletivas[col.campo]),
          valorNumericoOuNull(b.metricas_coletivas[col.campo])
        );
      }
      return 0;
    });
    return dados;
  }, [linhasFiltradas, ordenarPor, ordem]);

  function alternarOrdenacao(coluna: string) {
    if (ordenarPor === coluna) {
      setOrdem((o) => (o === "asc" ? "desc" : "asc"));
    } else {
      setOrdenarPor(coluna);
      setOrdem("desc");
    }
  }

  return (
    <>
    <div className="overflow-x-auto rounded-lg border border-[var(--color-border)]">
      <table className="w-full min-w-[1100px] border-collapse text-center text-sm">
        <thead>
          <tr className="bg-[var(--color-card)] text-xs uppercase tracking-wide text-[var(--color-muted)]">
            {[
              { id: "selecao", rotulo: "Seleção" },
              { id: "competicao", rotulo: "Competição" },
              { id: "J", rotulo: "Jogos" },
              { id: "rating_elo_100", rotulo: "Rating" },
              ...COLUNAS.map((c) => ({ id: c.chave, rotulo: c.chave })),
            ].map((col) => (
              <th
                key={col.id}
                className="cursor-pointer px-2 py-3 hover:text-white"
                title={
                  col.id in TOOLTIPS_METRICAS
                    ? TOOLTIPS_METRICAS[col.id as ChaveMetricaScouts]
                    : undefined
                }
                onClick={() => alternarOrdenacao(col.id)}
              >
                {col.rotulo}
                {ordenarPor === col.id ? (ordem === "asc" ? " ↑" : " ↓") : ""}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {linhas.map((s) => (
            <tr
              key={`${s.selecao}-${s.grupo}`}
              className="border-t border-[var(--color-border)] hover:bg-[var(--color-card)]/50"
            >
              <td className="px-2 py-2 text-left">
                <div className="flex items-center gap-2">
                  {s.url_escudo && (
                    <img
                      src={s.url_escudo}
                      alt={s.sigla}
                      className="h-8 w-8 object-contain"
                    />
                  )}
                  <div>
                    <div className="font-medium">{traduzirSelecao(s.selecao)}</div>
                    <div className="text-xs text-[var(--color-muted)]">
                      GRUPO {s.grupo}
                    </div>
                  </div>
                </div>
              </td>
              <td className="px-2 py-2">
                {estreouCopa(s) ? s.competicao : "N/A"}
              </td>
              <td className="px-2 py-2">
                {formatarValorMetrica(
                  estreouCopa(s) ? s.metricas_coletivas.J : null,
                  0,
                  true,
                )}
              </td>
              <td className="px-2 py-2">
                {(() => {
                  const rating = calcularRatingSelecaoCopa(s, selecoes);
                  if (rating === null) {
                    return <span className="text-[var(--color-muted)]">N/A</span>;
                  }
                  return (
                    <div className="mx-auto flex max-w-[100px] items-center gap-2">
                      <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-700">
                        <div
                          className="h-full rounded-full bg-sky-500"
                          style={{ width: `${Math.min(100, rating)}%` }}
                        />
                      </div>
                      <span className="w-8 text-xs">{rating}</span>
                    </div>
                  );
                })()}
              </td>
              {COLUNAS.map((col) => {
                const valorBruto = estreouCopa(s)
                  ? s.metricas_coletivas[col.campo]
                  : null;
                const valorExibir =
                  estreouCopa(s) && (valorBruto === null || valorBruto === undefined)
                    ? 0
                    : valorBruto;
                const numerico = estreouCopa(s) ? valorNumericoOuNull(valorExibir ?? 0) : null;
                const valoresColuna = valoresPorMetrica.get(col.chave) ?? [];
                const classeCelula =
                  numerico === null
                    ? classeCelulaNeutra()
                    : classeCelulaMetrica(
                        classificarFaixaMetrica(col.chave, numerico, valoresColuna)
                      );
                const texto = formatarValorMetrica(
                  valorExibir,
                  2,
                  col.campo === "clean_sheet_team",
                );
                return (
                  <td key={col.chave} className={`px-2 py-2 ${classeCelula}`}>
                    {texto}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      {linhas.length === 0 && (
        <p className="py-8 text-center text-sm text-[var(--color-muted)]">
          Nenhuma seleção encontrada para os filtros aplicados.
        </p>
      )}
    </div>
    <div className="mt-4 rounded-md border border-gray-200 bg-gray-50 p-4 text-center text-xs text-gray-500">
      <p>Métricas coletivas e scouts refletem somente a Copa do Mundo 2026 (FotMob).</p>
    </div>
    </>
  );
}
