import { useEffect, useMemo, useState } from "react";
import { traduzirSelecao } from "@/lib/traducoes";
import type { PontuacaoCedida, Selecao } from "@/types/dados";
import { TabelaPerformanceCruzada } from "./TabelaPerformanceCruzada";

interface ConfrontoExibicao {
  id: string;
  data: string;
  hora: string;
  estadio: string;
  casa: Selecao;
  fora: Selecao;
}

interface ConfrontoWC {
  grupo: string;
  rodada: number;
  mandante: string;
  visitante: string;
  data: string;
  hora?: string;
  finalizada?: boolean;
  placar?: string | null;
}

interface CopaEstado {
  rodada_cartola_atual: number;
  partidas_processadas: string[];
  atualizado_em: string | null;
}

interface Props {
  selecoes: Selecao[];
  pontuacaoCedida: PontuacaoCedida;
}

function formatarDataExibicao(data: string): string {
  if (!data) return "";
  const [ano, mes, dia] = data.split("-");
  return `${dia}/${mes}/${ano}`;
}

export function Recorrencia({ selecoes, pontuacaoCedida }: Props) {
  const [ativa, setAtiva] = useState<string | null>(null);
  const [confrontosWC, setConfrontosWC] = useState<ConfrontoWC[]>([]);
  const [rodadaCartola, setRodadaCartola] = useState(1);
  const [diaAtual, setDiaAtual] = useState<string>("");

  useEffect(() => {
    Promise.all([
      fetch("/data/grupos_wc2026.json").then((r) => r.json()),
      fetch("/data/copa_estado.json").then((r) => r.json()).catch(() => null),
    ])
      .then(([grupos, estado]: [{ confrontos: ConfrontoWC[] }, CopaEstado | null]) => {
        const confrontos = grupos.confrontos ?? [];
        setConfrontosWC(confrontos);

        const rodada = estado?.rodada_cartola_atual ?? 1;
        setRodadaCartola(rodada);

        const daRodada = confrontos.filter((c) => c.rodada === rodada);
        const hoje = new Date().toISOString().slice(0, 10);
        const datas = [...new Set(daRodada.map((c) => c.data))].sort();
        const inicial = datas.find((d) => d >= hoje) ?? datas[0] ?? "";
        setDiaAtual(inicial);
      })
      .catch(console.error);
  }, []);

  const confrontosRodada = useMemo(
    () => confrontosWC.filter((c) => c.rodada === rodadaCartola),
    [confrontosWC, rodadaCartola],
  );

  const datasDisponiveis = useMemo(
    () => [...new Set(confrontosRodada.map((c) => c.data))].sort(),
    [confrontosRodada],
  );

  const idxDia = datasDisponiveis.indexOf(diaAtual);

  const jogosDoDia = useMemo(
    () => confrontosRodada.filter((c) => c.data === diaAtual),
    [confrontosRodada, diaAtual],
  );

  const selecoesUnicas = useMemo(() => {
    const mapa = new Map<string, Selecao>();
    for (const s of selecoes) {
      if (!mapa.has(s.selecao)) mapa.set(s.selecao, s);
    }
    return [...mapa.values()];
  }, [selecoes]);

  const mapaSelecao = useMemo(
    () => new Map(selecoesUnicas.map((s) => [s.selecao, s])),
    [selecoesUnicas]
  );

  const obterPerformance = (sigla: string) => {
    return pontuacaoCedida[sigla.trim().toUpperCase()] ?? null;
  };

  const selecaoAtiva = ativa ? mapaSelecao.get(ativa) : null;

  const confrontosDoGrupo = useMemo((): ConfrontoExibicao[] => {
    if (!selecaoAtiva) return [];

    return selecaoAtiva.confrontos_agendados
      .filter((c) => c.grupo_adversario === selecaoAtiva.grupo)
      .map((confronto) => {
        const adversario = mapaSelecao.get(confronto.adversario);
        if (!adversario) return null;

        const participantes = [selecaoAtiva, adversario].sort((a, b) =>
          a.selecao.localeCompare(b.selecao)
        );

        return {
          id: `${confronto.data}-${participantes[0].selecao}-${participantes[1].selecao}`,
          data: confronto.data,
          hora: confronto.hora,
          estadio: confronto.estadio,
          casa: participantes[0],
          fora: participantes[1],
        };
      })
      .filter((c): c is ConfrontoExibicao => c !== null)
      .sort((a, b) => a.data.localeCompare(b.data) || a.hora.localeCompare(b.hora));
  }, [selecaoAtiva, mapaSelecao]);

  return (
    <div className="space-y-6">
      {/* a) Contêiner de Escudos */}
      <div className="grid grid-cols-4 gap-3 sm:grid-cols-6 md:grid-cols-8 lg:grid-cols-12">
        {selecoesUnicas
          .slice()
          .sort((a, b) => a.selecao.localeCompare(b.selecao))
          .map((s) => (
            <button
              key={s.selecao}
              type="button"
              onClick={() => setAtiva((prev) => (prev === s.selecao ? null : s.selecao))}
              className={`flex flex-col items-center rounded-lg border p-2 transition ${
                ativa === s.selecao
                  ? "border-sky-400 bg-[var(--color-accent)]"
                  : "border-[var(--color-border)] bg-[var(--color-card)] hover:border-sky-600"
              }`}
            >
              {s.url_escudo && (
                <img src={s.url_escudo} alt={s.sigla} className="h-10 w-10 object-contain" />
              )}
              <span className="mt-1 text-[10px] font-bold">{s.sigla.toUpperCase()}</span>
            </button>
          ))}
      </div>

      {/* b) Contêiner de Detalhes (Condicional — visível somente quando uma seleção está ativa) */}
      {selecaoAtiva && (
        <div className="mx-auto max-w-6xl space-y-6 rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-6">
          <div className="flex items-center gap-3 border-b border-[var(--color-border)] pb-4">
            {selecaoAtiva.url_escudo && (
              <img
                src={selecaoAtiva.url_escudo}
                alt={selecaoAtiva.sigla}
                className="h-14 w-14 object-contain"
              />
            )}
            <div>
              <h3 className="text-lg font-semibold">
                {traduzirSelecao(selecaoAtiva.selecao)} ({selecaoAtiva.sigla.toUpperCase()})
              </h3>
              <p className="text-sm text-[var(--color-muted)]">
                GRUPO {selecaoAtiva.grupo} — {confrontosDoGrupo.length} confronto(s) da fase de
                grupos
              </p>
            </div>
          </div>

          {confrontosDoGrupo.length === 0 ? (
            <p className="text-center text-sm text-[var(--color-muted)]">
              Nenhum confronto do grupo encontrado para esta seleção.
            </p>
          ) : (
            confrontosDoGrupo.map((confronto) => (
              <article
                key={confronto.id}
                className="space-y-4 rounded-lg border border-[var(--color-border)] p-4"
              >
                <header className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-3">
                    {confronto.casa.url_escudo && (
                      <img
                        src={confronto.casa.url_escudo}
                        alt={confronto.casa.sigla}
                        className="h-9 w-9"
                      />
                    )}
                    <span className="text-base font-bold">
                      {confronto.casa.sigla.toUpperCase()}
                    </span>
                    <span className="text-[var(--color-muted)]">vs</span>
                    {confronto.fora.url_escudo && (
                      <img
                        src={confronto.fora.url_escudo}
                        alt={confronto.fora.sigla}
                        className="h-9 w-9"
                      />
                    )}
                    <span className="text-base font-bold">
                      {confronto.fora.sigla.toUpperCase()}
                    </span>
                  </div>
                  <p className="text-xs text-[var(--color-muted)]">
                    {confronto.data} · {confronto.hora} · {confronto.estadio}
                  </p>
                </header>

                <div className="grid gap-4 md:grid-cols-2">
                  <TabelaPerformanceCruzada
                    titulo="Seleção"
                    sigla={confronto.casa.sigla}
                    escudo={confronto.casa.url_escudo}
                    performance={obterPerformance(confronto.casa.sigla)}
                  />
                  <TabelaPerformanceCruzada
                    titulo="Seleção"
                    sigla={confronto.fora.sigla}
                    escudo={confronto.fora.url_escudo}
                    performance={obterPerformance(confronto.fora.sigla)}
                  />
                </div>
              </article>
            ))
          )}
        </div>
      )}

      {/* c) Contêiner de Jogos — sempre visível, empurrado para baixo quando os Detalhes estão abertos */}
      {datasDisponiveis.length > 0 && (
        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-4">
          <div className="mb-4 flex items-center justify-between gap-2">
            <button
              type="button"
              onClick={() => setDiaAtual(datasDisponiveis[idxDia - 1])}
              disabled={idxDia <= 0}
              className="rounded-lg px-3 py-1.5 text-sm font-bold tracking-widest transition hover:bg-[var(--color-accent)] disabled:cursor-not-allowed disabled:opacity-30"
              aria-label="Dia anterior"
            >
              ‹‹‹
            </button>

            <h3 className="text-sm font-bold uppercase tracking-wide">
              Jogos do Dia &mdash; Rodada {rodadaCartola} &mdash;{" "}
              {formatarDataExibicao(diaAtual)}
            </h3>

            <button
              type="button"
              onClick={() => setDiaAtual(datasDisponiveis[idxDia + 1])}
              disabled={idxDia >= datasDisponiveis.length - 1}
              className="rounded-lg px-3 py-1.5 text-sm font-bold tracking-widest transition hover:bg-[var(--color-accent)] disabled:cursor-not-allowed disabled:opacity-30"
              aria-label="Próximo dia"
            >
              ›››
            </button>
          </div>

          {jogosDoDia.length === 0 ? (
            <p className="text-center text-sm text-[var(--color-muted)]">Sem jogos neste dia.</p>
          ) : (
            <div className="flex flex-wrap justify-center gap-3">
              {jogosDoDia.map((jogo) => {
                const mandante = mapaSelecao.get(jogo.mandante);
                const visitante = mapaSelecao.get(jogo.visitante);
                return (
                  <div
                    key={`${jogo.data}-${jogo.mandante}-${jogo.visitante}`}
                    className="flex flex-col items-center gap-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-background)]/50 p-3 text-center w-full sm:w-[calc(50%-6px)] lg:w-[calc(33.333%-8px)]"
                  >
                    <span className="text-[10px] font-semibold uppercase text-[var(--color-muted)]">
                      Grupo {jogo.grupo} · Rodada {jogo.rodada}
                    </span>
                    <div className="flex items-center justify-center gap-4">
                      <div className="flex flex-col items-center gap-1">
                        {mandante?.url_escudo && (
                          <img
                            src={mandante.url_escudo}
                            alt={mandante.sigla}
                            className="h-8 w-8 object-contain"
                          />
                        )}
                        <span className="text-xs font-bold">
                          {mandante?.sigla?.toUpperCase() ?? jogo.mandante}
                        </span>
                      </div>
                      <span className="text-xs font-semibold text-[var(--color-muted)]">vs</span>
                      <div className="flex flex-col items-center gap-1">
                        {visitante?.url_escudo && (
                          <img
                            src={visitante.url_escudo}
                            alt={visitante.sigla}
                            className="h-8 w-8 object-contain"
                          />
                        )}
                        <span className="text-xs font-bold">
                          {visitante?.sigla?.toUpperCase() ?? jogo.visitante}
                        </span>
                      </div>
                    </div>
                    <span className="text-[10px] text-[var(--color-muted)]">
                      {jogo.hora ? `${jogo.hora.slice(0, 5)} · ` : ""}
                      {formatarDataExibicao(jogo.data)}
                      {jogo.finalizada && jogo.placar ? ` · ${jogo.placar}` : ""}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
