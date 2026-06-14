import { useEffect, useMemo, useState } from "react";
import type { ClassificacaoGruposParseada } from "@/lib/classificacaoGrupos";
import {
  chaveConfronto,
  formatarDataExibicao,
  obterPerformance,
} from "@/lib/recorrenciaHelpers";
import { traduzirSelecao } from "@/lib/traducoes";
import type { LinhaClassificacao, PontuacaoCedida, Selecao } from "@/types/dados";
import { FiltrosRecorrencia } from "./FiltrosRecorrencia";
import { MiniClassificacaoGrupo } from "./MiniClassificacaoGrupo";
import { TabelaPerformanceCruzada } from "./TabelaPerformanceCruzada";

interface ConfrontoExibicao {
  id: string;
  data: string;
  hora: string;
  estadio: string;
  casa: Selecao;
  fora: Selecao;
  finalizada?: boolean;
  placar?: string | null;
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
}

interface Props {
  selecoes: Selecao[];
  pontuacaoCedida: PontuacaoCedida;
  classificacao: ClassificacaoGruposParseada;
}

function LegendaRecorrencia() {
  return (
    <span
      className="inline-flex h-5 w-5 cursor-help items-center justify-center rounded-full border border-[var(--color-border)] text-[10px] font-serif italic"
      title="Pontuação cedido/conquistado — média Cartola por posição (Copa 2026). Cores: BOM (verde) · MEDIANO (âmbar) · RUIM (vermelho). Conquistado: maior é melhor. Cedido: menor é melhor."
    >
      i
    </span>
  );
}

function linhaClassificacao(
  classificacao: ClassificacaoGruposParseada,
  selecaoNome: string,
): LinhaClassificacao | null {
  for (const linhas of Object.values(classificacao.grupos)) {
    const linha = linhas.find((l) => l.selecao === selecaoNome);
    if (linha) return linha;
  }
  return null;
}

export function Recorrencia({ selecoes, pontuacaoCedida, classificacao }: Props) {
  const [confrontosWC, setConfrontosWC] = useState<ConfrontoWC[]>([]);
  const [rodadaCartola, setRodadaCartola] = useState(1);
  const [diaAtual, setDiaAtual] = useState("");
  const [grupoFiltro, setGrupoFiltro] = useState("TODOS");
  const [somenteJogosDia, setSomenteJogosDia] = useState(false);
  const [busca, setBusca] = useState("");
  const [confrontoAtivo, setConfrontoAtivo] = useState<string | null>(null);
  const [selecaoAtiva, setSelecaoAtiva] = useState<string | null>(null);
  const [verGrupoCompleto, setVerGrupoCompleto] = useState(false);

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

  const rodadasDisponiveis = useMemo(
    () => [...new Set(confrontosWC.map((c) => c.rodada))].sort((a, b) => a - b),
    [confrontosWC],
  );

  const confrontosRodada = useMemo(
    () => confrontosWC.filter((c) => c.rodada === rodadaCartola),
    [confrontosWC, rodadaCartola],
  );

  const datasDisponiveis = useMemo(
    () => [...new Set(confrontosRodada.map((c) => c.data))].sort(),
    [confrontosRodada],
  );

  useEffect(() => {
    if (datasDisponiveis.length && !datasDisponiveis.includes(diaAtual)) {
      setDiaAtual(datasDisponiveis[0]);
    }
  }, [datasDisponiveis, diaAtual]);

  const selecoesUnicas = useMemo(() => {
    const mapa = new Map<string, Selecao>();
    for (const s of selecoes) {
      if (!mapa.has(s.selecao)) mapa.set(s.selecao, s);
    }
    return [...mapa.values()];
  }, [selecoes]);

  const mapaSelecao = useMemo(
    () => new Map(selecoesUnicas.map((s) => [s.selecao, s])),
    [selecoesUnicas],
  );

  const siglasDoDia = useMemo(() => {
    const siglas = new Set<string>();
    for (const j of confrontosRodada.filter((c) => c.data === diaAtual)) {
      const m = mapaSelecao.get(j.mandante);
      const v = mapaSelecao.get(j.visitante);
      if (m) siglas.add(m.selecao);
      if (v) siglas.add(v.selecao);
    }
    return siglas;
  }, [confrontosRodada, diaAtual, mapaSelecao]);

  const jogosFiltrados = useMemo(() => {
    return confrontosRodada.filter((j) => {
      if (j.data !== diaAtual) return false;
      if (grupoFiltro !== "TODOS" && j.grupo !== grupoFiltro) return false;
      if (busca.trim()) {
        const q = busca.trim().toLowerCase();
        const m = mapaSelecao.get(j.mandante);
        const v = mapaSelecao.get(j.visitante);
        const haystack = [
          j.mandante,
          j.visitante,
          m?.sigla,
          v?.sigla,
          m ? traduzirSelecao(m.selecao) : "",
          v ? traduzirSelecao(v.selecao) : "",
        ]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();
        if (!haystack.includes(q)) return false;
      }
      return true;
    });
  }, [confrontosRodada, diaAtual, grupoFiltro, busca, mapaSelecao]);

  const selecoesFiltradas = useMemo(() => {
    let lista = selecoesUnicas;
    if (grupoFiltro !== "TODOS") {
      lista = lista.filter((s) => s.grupo === grupoFiltro);
    }
    if (somenteJogosDia) {
      lista = lista.filter((s) => siglasDoDia.has(s.selecao));
    }
    if (busca.trim()) {
      const q = busca.trim().toLowerCase();
      lista = lista.filter(
        (s) =>
          s.sigla.toLowerCase().includes(q) ||
          s.selecao.toLowerCase().includes(q) ||
          traduzirSelecao(s.selecao).toLowerCase().includes(q),
      );
    }
    return lista.sort((a, b) =>
      traduzirSelecao(a.selecao).localeCompare(traduzirSelecao(b.selecao), "pt-BR", {
        sensitivity: "base",
      }),
    );
  }, [selecoesUnicas, grupoFiltro, somenteJogosDia, siglasDoDia, busca]);

  const selecaoDetalhe = selecaoAtiva ? mapaSelecao.get(selecaoAtiva) : null;

  const confrontosDoGrupo = useMemo((): ConfrontoExibicao[] => {
    if (!selecaoDetalhe) return [];

    const lista: ConfrontoExibicao[] = [];
    for (const confronto of selecaoDetalhe.confrontos_agendados) {
      if (confronto.grupo_adversario !== selecaoDetalhe.grupo) continue;
      const adversario = mapaSelecao.get(confronto.adversario);
      if (!adversario) continue;

      const wc = confrontosWC.find(
        (j) =>
          j.grupo === selecaoDetalhe.grupo &&
          ((j.mandante === selecaoDetalhe.selecao && j.visitante === adversario.selecao) ||
            (j.visitante === selecaoDetalhe.selecao && j.mandante === adversario.selecao)) &&
          j.data === confronto.data,
      );

      const participantes = [selecaoDetalhe, adversario].sort((a, b) =>
        a.selecao.localeCompare(b.selecao),
      );

      lista.push({
        id: `${confronto.data}-${participantes[0].selecao}-${participantes[1].selecao}`,
        data: confronto.data,
        hora: confronto.hora,
        estadio: confronto.estadio,
        casa: participantes[0],
        fora: participantes[1],
        finalizada: wc?.finalizada,
        placar: wc?.placar,
      });
    }
    return lista.sort((a, b) => a.data.localeCompare(b.data) || a.hora.localeCompare(b.hora));
  }, [selecaoDetalhe, mapaSelecao, confrontosWC]);

  const proximoConfrontoSelecao = useMemo(() => {
    if (confrontosDoGrupo.length === 0) return null;
    const pendente = confrontosDoGrupo.find((c) => !c.finalizada);
    return pendente ?? confrontosDoGrupo[confrontosDoGrupo.length - 1];
  }, [confrontosDoGrupo]);

  const confrontosRestantes = useMemo(() => {
    if (!proximoConfrontoSelecao) return confrontosDoGrupo;
    return confrontosDoGrupo.filter((c) => c.id !== proximoConfrontoSelecao.id);
  }, [confrontosDoGrupo, proximoConfrontoSelecao]);

  function selecionarConfrontoWC(jogo: ConfrontoWC) {
    const id = chaveConfronto(jogo.mandante, jogo.visitante, jogo.data);
    setConfrontoAtivo((prev) => (prev === id ? null : id));
    setSelecaoAtiva(null);
    setVerGrupoCompleto(false);
  }

  function selecionarTime(nome: string) {
    setSelecaoAtiva((prev) => (prev === nome ? null : nome));
    setConfrontoAtivo(null);
    setVerGrupoCompleto(false);
  }

  function renderDetalheConfronto(confronto: ConfrontoExibicao, compacto = false) {
    return (
      <article
        key={confronto.id}
        className={`space-y-3 rounded-lg border border-[var(--color-border)] ${compacto ? "p-3" : "p-4"}`}
      >
        <header className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            {confronto.casa.url_escudo && (
              <img src={confronto.casa.url_escudo} alt={confronto.casa.sigla} className="h-8 w-8" />
            )}
            <span className="font-bold">{confronto.casa.sigla.toUpperCase()}</span>
            <span className="text-[var(--color-muted)]">vs</span>
            {confronto.fora.url_escudo && (
              <img src={confronto.fora.url_escudo} alt={confronto.fora.sigla} className="h-8 w-8" />
            )}
            <span className="font-bold">{confronto.fora.sigla.toUpperCase()}</span>
            {confronto.finalizada && confronto.placar && (
              <span className="ml-1 rounded bg-[var(--color-accent)] px-2 py-0.5 text-xs font-semibold">
                {confronto.placar}
              </span>
            )}
          </div>
          <p className="text-xs text-[var(--color-muted)]">
            {formatarDataExibicao(confronto.data)} · {confronto.hora?.slice(0, 5)} ·{" "}
            {confronto.estadio}
          </p>
        </header>
        <div className="grid gap-3 md:grid-cols-2">
          <TabelaPerformanceCruzada
            titulo="Seleção"
            sigla={confronto.casa.sigla}
            escudo={confronto.casa.url_escudo}
            performance={obterPerformance(pontuacaoCedida, confronto.casa.sigla)}
          />
          <TabelaPerformanceCruzada
            titulo="Seleção"
            sigla={confronto.fora.sigla}
            escudo={confronto.fora.url_escudo}
            performance={obterPerformance(pontuacaoCedida, confronto.fora.sigla)}
          />
        </div>
      </article>
    );
  }

  const confrontoWCAtivo = confrontoAtivo
    ? jogosFiltrados.find(
        (j) => chaveConfronto(j.mandante, j.visitante, j.data) === confrontoAtivo,
      )
    : null;

  const grupoContexto =
    grupoFiltro !== "TODOS"
      ? grupoFiltro
      : selecaoDetalhe?.grupo ?? confrontoWCAtivo?.grupo ?? null;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <FiltrosRecorrencia
          rodada={rodadaCartola}
          rodadasDisponiveis={rodadasDisponiveis}
          diaAtual={diaAtual}
          datasDisponiveis={datasDisponiveis}
          grupo={grupoFiltro}
          somenteJogosDia={somenteJogosDia}
          busca={busca}
          onRodadaChange={(r) => {
            setRodadaCartola(r);
            setConfrontoAtivo(null);
            setSelecaoAtiva(null);
          }}
          onDiaChange={setDiaAtual}
          onGrupoChange={setGrupoFiltro}
          onSomenteJogosDiaChange={setSomenteJogosDia}
          onBuscaChange={setBusca}
        />
        <LegendaRecorrencia />
      </div>

      {/* Confrontos da rodada/dia — visão principal */}
      <section className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-4">
        <h3 className="mb-3 text-sm font-bold uppercase tracking-wide text-[var(--color-muted)]">
          Confrontos — Rodada {rodadaCartola} · {formatarDataExibicao(diaAtual)}
        </h3>

        {jogosFiltrados.length === 0 ? (
          <p className="py-6 text-center text-sm text-[var(--color-muted)]">
            Nenhum jogo para os filtros selecionados.
          </p>
        ) : (
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {jogosFiltrados.map((jogo) => {
              const mandante = mapaSelecao.get(jogo.mandante);
              const visitante = mapaSelecao.get(jogo.visitante);
              const id = chaveConfronto(jogo.mandante, jogo.visitante, jogo.data);
              const ativo = confrontoAtivo === id;
              const destaqueTime =
                selecaoAtiva &&
                (jogo.mandante === selecaoAtiva || jogo.visitante === selecaoAtiva);

              return (
                <button
                  key={id}
                  type="button"
                  onClick={() => selecionarConfrontoWC(jogo)}
                  className={`flex flex-col gap-2 rounded-lg border p-3 text-left transition ${
                    ativo
                      ? "border-sky-400 bg-[var(--color-accent)]"
                      : destaqueTime
                        ? "border-sky-500/50 bg-sky-500/10"
                        : "border-[var(--color-border)] bg-[var(--color-background)]/50 hover:border-sky-600"
                  }`}
                >
                  <span className="text-[10px] font-semibold uppercase text-[var(--color-muted)]">
                    Grupo {jogo.grupo}
                    {jogo.finalizada ? " · Finalizado" : ""}
                    {jogo.hora ? ` · ${jogo.hora.slice(0, 5)}` : ""}
                  </span>
                  <div className="flex items-center justify-center gap-3">
                    <div className="flex flex-col items-center gap-1">
                      {mandante?.url_escudo && (
                        <img src={mandante.url_escudo} alt={mandante.sigla} className="h-9 w-9" />
                      )}
                      <span className="text-sm font-bold">{mandante?.sigla ?? "?"}</span>
                    </div>
                    <span className="text-sm font-semibold text-[var(--color-muted)]">
                      {jogo.finalizada && jogo.placar ? jogo.placar : "vs"}
                    </span>
                    <div className="flex flex-col items-center gap-1">
                      {visitante?.url_escudo && (
                        <img src={visitante.url_escudo} alt={visitante.sigla} className="h-9 w-9" />
                      )}
                      <span className="text-sm font-bold">{visitante?.sigla ?? "?"}</span>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </section>

      {/* Detalhe do confronto selecionado */}
      {confrontoWCAtivo && (() => {
        const mandante = mapaSelecao.get(confrontoWCAtivo.mandante);
        const visitante = mapaSelecao.get(confrontoWCAtivo.visitante);
        if (!mandante || !visitante) {
          return (
            <p className="text-sm text-[var(--color-muted)]">Dados da seleção indisponíveis.</p>
          );
        }
        return (
          <section className="rounded-xl border border-sky-400/40 bg-[var(--color-card)] p-4">
            {renderDetalheConfronto(
              {
                id: confrontoAtivo!,
                data: confrontoWCAtivo.data,
                hora: confrontoWCAtivo.hora ?? "",
                estadio: "",
                casa: mandante,
                fora: visitante,
                finalizada: confrontoWCAtivo.finalizada,
                placar: confrontoWCAtivo.placar,
              },
              false,
            )}
          </section>
        );
      })()}

      {/* Mini classificação contextual */}
      {grupoContexto && (
        <MiniClassificacaoGrupo
          grupo={grupoContexto}
          classificacao={classificacao}
          selecoesDestaque={
            selecaoAtiva
              ? new Set([selecaoAtiva])
              : confrontoWCAtivo
                ? new Set([confrontoWCAtivo.mandante, confrontoWCAtivo.visitante])
                : undefined
          }
        />
      )}

      {/* Explorar por seleção */}
      <section className="space-y-3">
        <h3 className="text-sm font-bold uppercase tracking-wide text-[var(--color-muted)]">
          Explorar por seleção
        </h3>
        <div className="grid grid-cols-4 gap-2 sm:grid-cols-6 md:grid-cols-8 lg:grid-cols-12">
          {selecoesFiltradas.map((s) => {
            const classif = linhaClassificacao(classificacao, s.selecao);
            const proxAdv = s.confrontos_agendados.find((c) => !c.data || c.data >= diaAtual);
            return (
              <button
                key={s.selecao}
                type="button"
                onClick={() => selecionarTime(s.selecao)}
                className={`flex flex-col items-center rounded-lg border p-2 transition ${
                  selecaoAtiva === s.selecao
                    ? "border-sky-400 bg-[var(--color-accent)]"
                    : siglasDoDia.has(s.selecao)
                      ? "border-sky-500/40 bg-[var(--color-card)] hover:border-sky-600"
                      : "border-[var(--color-border)] bg-[var(--color-card)] hover:border-sky-600"
                }`}
              >
                {s.url_escudo && (
                  <img src={s.url_escudo} alt={s.sigla} className="h-9 w-9 object-contain" />
                )}
                <span className="mt-1 text-[10px] font-bold">{s.sigla.toUpperCase()}</span>
                {classif && classif.J > 0 && (
                  <span className="text-[9px] text-[var(--color-muted)]">
                    {classif.P}pts · J{classif.J}
                  </span>
                )}
                {proxAdv && (
                  <span className="text-[9px] text-sky-500">vs {proxAdv.adversario_sigla}</span>
                )}
              </button>
            );
          })}
        </div>
      </section>

      {/* Detalhe da seleção — próximo jogo expandido */}
      {selecaoDetalhe && (
        <section className="mx-auto max-w-6xl space-y-4 rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-5">
          <div className="flex items-center gap-3 border-b border-[var(--color-border)] pb-3">
            {selecaoDetalhe.url_escudo && (
              <img
                src={selecaoDetalhe.url_escudo}
                alt={selecaoDetalhe.sigla}
                className="h-12 w-12 object-contain"
              />
            )}
            <div>
              <h3 className="text-lg font-semibold">
                {traduzirSelecao(selecaoDetalhe.selecao)} ({selecaoDetalhe.sigla.toUpperCase()})
              </h3>
              <p className="text-sm text-[var(--color-muted)]">
                Grupo {selecaoDetalhe.grupo} — recorrência na fase de grupos
              </p>
            </div>
          </div>

          {proximoConfrontoSelecao ? (
            <>
              <p className="text-xs font-semibold uppercase text-[var(--color-muted)]">
                {proximoConfrontoSelecao.finalizada ? "Último jogo" : "Próximo jogo"}
              </p>
              {renderDetalheConfronto(proximoConfrontoSelecao, true)}

              {confrontosRestantes.length > 0 && (
                <div>
                  <button
                    type="button"
                    onClick={() => setVerGrupoCompleto((v) => !v)}
                    className="text-sm font-medium text-sky-500 hover:underline"
                  >
                    {verGrupoCompleto
                      ? "Ocultar demais jogos do grupo"
                      : `Ver ${confrontosRestantes.length} outro(s) jogo(s) do grupo`}
                  </button>
                  {verGrupoCompleto && (
                    <div className="mt-3 space-y-3">
                      {confrontosRestantes.map((c) => renderDetalheConfronto(c, true))}
                    </div>
                  )}
                </div>
              )}
            </>
          ) : (
            <p className="text-center text-sm text-[var(--color-muted)]">
              Nenhum confronto do grupo encontrado.
            </p>
          )}
        </section>
      )}
    </div>
  );
}
