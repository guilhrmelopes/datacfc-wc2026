import type {
  ClassificacaoGrupos,
  Jogador,
  JogadorMercado,
  PontuacaoCedida,
  Selecao,
} from "@/types/dados";

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
}

/** Dados da aba Radar (selecoes + pontuacao_cedida). */
export async function carregarDadosRadar(): Promise<
  Pick<DadosAplicacao, "selecoes" | "pontuacaoCedida">
> {
  const [selecoes, pontuacaoCedida] = await Promise.all([
    carregarJson<Selecao[]>("/data/selecoes.json"),
    carregarJson<PontuacaoCedida>("/data/pontuacao_cedida.json"),
  ]);
  return { selecoes, pontuacaoCedida };
}

/** Dados da aba Mercado (jogadores_mercado + selecoes + pontuacao_cedida). */
export async function carregarDadosMercado(): Promise<DadosMercado> {
  const [jogadores, selecoes, pontuacaoCedida] = await Promise.all([
    carregarJson<JogadorMercado[]>("/data/jogadores_mercado.json"),
    carregarJson<Selecao[]>("/data/selecoes.json"),
    carregarJson<PontuacaoCedida>("/data/pontuacao_cedida.json"),
  ]);
  return { jogadores, selecoes, pontuacaoCedida };
}

/** Dados da aba Fase de Grupos (classificação). */
export async function carregarDadosFase(): Promise<
  Pick<DadosAplicacao, "classificacao">
> {
  const classificacao = await carregarJson<ClassificacaoGrupos>(
    "/data/classificacao_grupos.json"
  );
  return { classificacao };
}

/** Carrega todos os dados de uma vez (compatibilidade). */
export async function carregarDados(): Promise<DadosAplicacao> {
  const [selecoes, jogadores, pontuacaoCedida, classificacao] =
    await Promise.all([
      carregarJson<Selecao[]>("/data/selecoes.json"),
      carregarJson<Jogador[]>("/data/jogadores.json"),
      carregarJson<PontuacaoCedida>("/data/pontuacao_cedida.json"),
      carregarJson<ClassificacaoGrupos>("/data/classificacao_grupos.json"),
    ]);
  return { selecoes, jogadores, pontuacaoCedida, classificacao };
}
