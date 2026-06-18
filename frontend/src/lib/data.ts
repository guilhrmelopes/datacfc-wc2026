import type {
  ClassificacaoGrupos,
  Jogador,
  JogadorMercado,
  OddsJogadoresData,
  PontuacaoCedida,
  Selecao,
} from "@/types/dados";
import type { ConfrontoCopa } from "@/lib/ratingJogador";
import {
  parseClassificacaoGrupos,
  type ClassificacaoGruposParseada,
} from "@/lib/classificacaoGrupos";
import type { OddsArmazenamentoData } from "@/lib/oddsRodada";
import type { CobradoresCopaData } from "@/lib/cobradoresCopa";

// Cache em memória para evitar re-fetch ao trocar de aba
const _cache = new Map<string, unknown>();

async function carregarJson<T>(caminho: string): Promise<T> {
  if (_cache.has(caminho)) {
    return _cache.get(caminho) as T;
  }
  const resposta = await fetch(caminho);
  if (!resposta.ok) {
    throw new Error(`Falha ao carregar ${caminho}: ${resposta.status}`);
  }
  const dados = (await resposta.json()) as T;
  _cache.set(caminho, dados);
  return dados;
}

export interface DadosAplicacao {
  selecoes: Selecao[];
  jogadores: Jogador[];
  pontuacaoCedida: PontuacaoCedida;
  classificacao: ClassificacaoGrupos;
}

export interface DadosMercado {
  jogadores: JogadorMercado[];
  selecoes: Selecao[];
  pontuacaoCedida: PontuacaoCedida;
  oddsJogadores: OddsJogadoresData | null;
  oddsArmazenamento: OddsArmazenamentoData | null;
  cobradoresCopa: CobradoresCopaData | null;
  rodadaCartolaAtual: number;
  confrontosCopa: ConfrontoCopa[];
  partidasProcessadas: string[];
}

/** Dados da aba Radar (selecoes + pontuacao_cedida + classificação). */
export async function carregarDadosRadar(): Promise<
  Pick<DadosAplicacao, "selecoes" | "pontuacaoCedida"> & {
    classificacao: ClassificacaoGruposParseada;
  }
> {
  const [selecoes, pontuacaoCedida, classificacaoRaw] = await Promise.all([
    carregarJson<Selecao[]>("/data/selecoes.json"),
    carregarJson<PontuacaoCedida>("/data/pontuacao_cedida.json"),
    carregarJson<Record<string, unknown>>("/data/classificacao_grupos.json"),
  ]);
  return {
    selecoes,
    pontuacaoCedida,
    classificacao: parseClassificacaoGrupos(classificacaoRaw),
  };
}

/** Dados da aba Mercado (jogadores_mercado + selecoes + pontuacao_cedida + odds). */
export async function carregarDadosMercado(): Promise<DadosMercado> {
  const [jogadores, selecoes, pontuacaoCedida, oddsResult, oddsArmaz, cobradores, grupos, copaEstado] =
    await Promise.all([
    carregarJson<JogadorMercado[]>("/data/jogadores_mercado.json"),
    carregarJson<Selecao[]>("/data/selecoes.json"),
    carregarJson<PontuacaoCedida>("/data/pontuacao_cedida.json"),
    fetch("/data/odds_jogadores.json")
      .then((r) => (r.ok ? (r.json() as Promise<OddsJogadoresData>) : null))
      .catch(() => null),
    fetch("/data/odds_eventos_armazenados.json")
      .then((r) => (r.ok ? (r.json() as Promise<OddsArmazenamentoData>) : null))
      .catch(() => null),
    fetch("/data/cobradores_copa.json")
      .then((r) => (r.ok ? (r.json() as Promise<CobradoresCopaData>) : null))
      .catch(() => null),
    carregarJson<{ confrontos: ConfrontoCopa[] }>("/data/grupos_wc2026.json"),
    carregarJson<{ partidas_processadas?: string[]; rodada_cartola_atual?: number }>(
      "/data/copa_estado.json",
    ),
  ]);
  return {
    jogadores,
    selecoes,
    pontuacaoCedida,
    oddsJogadores: oddsResult,
    oddsArmazenamento: oddsArmaz,
    cobradoresCopa: cobradores,
    rodadaCartolaAtual: Number(copaEstado.rodada_cartola_atual) || 2,
    confrontosCopa: grupos.confrontos ?? [],
    partidasProcessadas: copaEstado.partidas_processadas ?? [],
  };
}

/** Dados da aba Fase de Grupos (classificação). */
export async function carregarDadosFase(): Promise<{
  classificacao: ClassificacaoGruposParseada;
}> {
  const raw = await carregarJson<Record<string, unknown>>(
    "/data/classificacao_grupos.json",
  );
  return { classificacao: parseClassificacaoGrupos(raw) };
}

/** Carrega todos os dados de uma vez (compatibilidade). */
export async function carregarDados(): Promise<DadosAplicacao> {
  const [selecoes, jogadores, pontuacaoCedida, classificacaoRaw] =
    await Promise.all([
      carregarJson<Selecao[]>("/data/selecoes.json"),
      carregarJson<Jogador[]>("/data/jogadores.json"),
      carregarJson<PontuacaoCedida>("/data/pontuacao_cedida.json"),
      carregarJson<Record<string, unknown>>("/data/classificacao_grupos.json"),
    ]);
  const classificacao = parseClassificacaoGrupos(classificacaoRaw).grupos;
  return { selecoes, jogadores, pontuacaoCedida, classificacao };
}
