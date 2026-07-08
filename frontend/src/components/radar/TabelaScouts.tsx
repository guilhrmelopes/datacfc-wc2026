import { useMemo, useState } from "react";
import {
  type ChaveMetricaScouts,
  classificarFaixaMetricaSelecao,
  classeCelulaMetricaSelecao,
  classeCelulaNeutra,
  METRICAS_TOTAIS_SCOUTS,
  MIN_JOGOS_RECALIBRACAO,
  valorNormalizadoMetricaSelecao,
} from "@/lib/formatacaoMetricas";
import { formatarValorMetrica, valorNumericoOuNull } from "@/lib/exibirValor";
import {
  estreouCopa,
  ratingSelecaoExibicao,
  tooltipRatingSelecao,
  type ModoRatingSelecao,
} from "@/lib/ratingSelecao";
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
  modoRating?: ModoRatingSelecao;
}

function filtrarSelecoes(selecoes: Selecao[], competicao: string, grupo: string) {
  return selecoes.filter((s) => {
    const okCompeticao =
      competicao === "TODAS" || s.competicao === competicao;
    const okGrupo = grupo === "TODOS" || s.grupo === grupo;
    return okCompeticao && okGrupo;
  });
}

function valorExibicaoColuna(
  chave: ChaveMetricaScouts,
  bruto: number | null,
  jogos: number,
): number | null {
  if (bruto === null) return null;
  if (chave === "SG") return bruto; // mostra clean sheets totais; cor usa taxa
  if (METRICAS_TOTAIS_SCOUTS.has(chave) && jogos > 0) {
    return valorNormalizadoMetricaSelecao(chave, bruto, jogos);
  }
  return bruto;
}

export function TabelaScouts({
  selecoes,
  competicao,
  grupo,
  modoRating = "copa",
}: Props) {
  const [ordenarPor, setOrdenarPor] = useState<string>("rating");
  const [ordem, setOrdem] = useState<Ordem>("desc");

  const linhasFiltradas = useMemo(
    () => filtrarSelecoes(selecoes, competicao, grupo),
    [selecoes, competicao, grupo],
  );

  const contextoMetricas = useMemo(() => {
    const estreou = linhasFiltradas.filter(estreouCopa);
    const maxJogosAmostra = Math.max(
      0,
      ...estreou.map((s) => valorNumericoOuNull(s.metricas_coletivas.J) ?? 0),
    );
    const recalibAtiva = maxJogosAmostra >= MIN_JOGOS_RECALIBRACAO;
    const valoresPorMetrica = new Map<ChaveMetricaScouts, number[]>();

    for (const col of COLUNAS) {
      const valores = estreou
        .filter(
          (s) =>
            !recalibAtiva ||
            (valorNumericoOuNull(s.metricas_coletivas.J) ?? 0) >= MIN_JOGOS_RECALIBRACAO,
        )
        .map((s) => {
          const bruto = valorNumericoOuNull(s.metricas_coletivas[col.campo] ?? 0);
          if (bruto === null) return null;
          const jogos = valorNumericoOuNull(s.metricas_coletivas.J) ?? 1;
          return valorNormalizadoMetricaSelecao(col.chave, bruto, jogos);
        })
        .filter((v): v is number => v !== null);
      valoresPorMetrica.set(col.chave, valores);
    }

    return { valoresPorMetrica, maxJogosAmostra, recalibAtiva };
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
      if (ordenarPor === "rating") {
        return compararNumero(
          ratingSelecaoExibicao(a, linhasFiltradas, modoRating),
          ratingSelecaoExibicao(b, linhasFiltradas, modoRating),
        );
      }
      if (ordenarPor === "J") {
        return compararNumero(
          valorNumericoOuNull(a.metricas_coletivas.J),
          valorNumericoOuNull(b.metricas_coletivas.J),
        );
      }
      const col = COLUNAS.find((c) => c.chave === ordenarPor);
      if (col) {
        const ja = valorNumericoOuNull(a.metricas_coletivas.J) ?? 1;
        const jb = valorNumericoOuNull(b.metricas_coletivas.J) ?? 1;
        return compararNumero(
          valorExibicaoColuna(
            col.chave,
            valorNumericoOuNull(a.metricas_coletivas[col.campo]),
            ja,
          ),
          valorExibicaoColuna(
            col.chave,
            valorNumericoOuNull(b.metricas_coletivas[col.campo]),
            jb,
          ),
        );
      }
      return 0;
    });
    return dados;
  }, [linhasFiltradas, ordenarPor, ordem, modoRating]);

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
                { id: "rating", rotulo: "Rating" },
                ...COLUNAS.map((c) => ({ id: c.chave, rotulo: c.chave })),
              ].map((col) => (
                <th
                  key={col.id}
                  className="cursor-pointer px-2 py-3 hover:text-white"
                  title={
                    col.id === "rating"
                      ? TOOLTIPS_METRICAS.Rating
                      : col.id in TOOLTIPS_METRICAS
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
                        {(s.jogos_mata_mata ?? 0) > 0 ? ` · KO ${s.jogos_mata_mata}` : ""}
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
                <td
                  className="px-2 py-2"
                  title={tooltipRatingSelecao(s, linhasFiltradas, modoRating)}
                >
                  {(() => {
                    const rating = ratingSelecaoExibicao(
                      s,
                      linhasFiltradas,
                      modoRating,
                    );
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
                  const jogos = valorNumericoOuNull(s.metricas_coletivas.J) ?? 1;
                  const numericoBruto = estreouCopa(s)
                    ? valorNumericoOuNull(valorBruto ?? 0)
                    : null;
                  const valorExibir = estreouCopa(s)
                    ? valorExibicaoColuna(col.chave, numericoBruto, jogos)
                    : null;
                  const classeCelula =
                    numericoBruto === null
                      ? classeCelulaNeutra()
                      : classeCelulaMetricaSelecao(
                          classificarFaixaMetricaSelecao(col.chave, numericoBruto, {
                            jogos,
                            amostraColuna: contextoMetricas.valoresPorMetrica.get(
                              col.chave,
                            ),
                            maxJogosAmostra: contextoMetricas.maxJogosAmostra,
                            recalibAtiva: contextoMetricas.recalibAtiva,
                          }),
                        );
                  const texto = formatarValorMetrica(
                    valorExibir,
                    col.campo === "clean_sheet_team" ? 0 : 2,
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
      </div>
      {linhas.length === 0 && (
        <p className="py-6 text-center text-sm text-[var(--color-muted)]">
          Nenhuma seleção no filtro.
        </p>
      )}
    </>
  );
}
