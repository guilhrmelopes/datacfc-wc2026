export interface MetricasColetivas {
  goals_team_match: number | null;
  goals_conceded_team_match: number | null;
  possession_percentage_team: number | null;
  clean_sheet_team: number | null;
  expected_goals_team: number | null;
  expected_goals_conceded_team: number | null;
  ontarget_scoring_att_team: number | null;
  big_chance_team: number | null;
  touches_in_opp_box_team: number | null;
  total_tackle_team: number | null;
  poss_won_att_3rd_team: number | null;
  saves_team: number | null;
  fk_foul_lost_team: number | null;
  total_yel_card_team: number | null;
  total_red_card_team: number | null;
  J: number | null;
}

export interface ConfrontoAgendado {
  adversario: string;
  adversario_sigla: string;
  adversario_clube_id: number;
  adversario_escudo: string | null;
  grupo_adversario: string;
  data: string;
  hora: string;
  estadio: string;
  rodada?: number;
  match_id?: string;
  /** False quando o confronto não entra na rodada fantasy do Cartola FC. */
  valida_cartola?: boolean;
}

export interface Selecao {
  selecao: string;
  sigla: string;
  selecao_id: number;
  clube_id: number;
  grupo: string;
  competicao: string | null;
  url_escudo: string | null;
  metricas_coletivas: MetricasColetivas;
  /** Elo 0–100 normalizado entre as 48 seleções (eloratings.net). */
  rating_elo_100: number | null;
  /** Elo bruto eloratings.net. */
  elo_rating?: number | null;
  elo_rank?: number | null;
  elo_atualizado_em?: string | null;
  /** Jogos de mata-mata já finalizados. */
  jogos_mata_mata?: number | null;
  /** Rating 0–100 por scouts da Copa (percentis das métricas/jogo). */
  rating_scouts_100?: number | null;
  /** Elo 0–100 só com resultados de eliminatórias. */
  rating_ko_100?: number | null;
  /** Elo bruto calculado só no mata-mata. */
  elo_ko?: number | null;
  /** Rating principal: fusão Elo mundial + scouts + Elo KO. */
  rating_copa_100?: number | null;
  confrontos_agendados: ConfrontoAgendado[];
}

export interface Jogador {
  jogador: string;
  selecao: string;
  selecao_id: number;
  posicao_id: number;
  bucket_posicao: string;
  competicao: string;
  rating_recomendacao: number;
  mins_played: number;
  goals: number;
  goal_assist: number;
}

/** Jogador convocado para a Copa 2026 — fonte: cartola_mercado_oficial.json + FotMob. */
export interface JogadorMercado {
  atleta_id: number;
  apelido: string;
  posicao_id: number;
  bucket_posicao: string;
  status_id: number;
  clube_id: number;
  selecao: string;
  sigla: string;
  grupo: string;
  url_escudo: string | null;
  foto_url: string | null;
  rating_recomendacao: number;
  mins_played: number;
  jogos_num: number;
  goals: number;
  goal_assist: number;
  clean_sheet: number;
  media_geral: number | null;
  media_base: number | null;
  proximo_adversario_sigla: string | null;
  proximo_adversario_escudo: string | null;
  proximo_adversario_data: string | null;
  /** False após fim dos grupos se a seleção não classificou para o mata-mata. */
  ativo_playoffs?: boolean;
  /** Métricas acumuladas na fase de grupos (Cartola Copa). */
  copa_jogos_num?: number;
  copa_mins_played?: number;
  copa_goals?: number;
  copa_goal_assist?: number;
  copa_clean_sheet?: number;
  copa_pontos_total?: number;
  copa_media_geral?: number | null;
  copa_media_base?: number | null;
  copa_fd?: number;
  copa_ds?: number;
  copa_de?: number;
  copa_gs?: number;
  copa_gcc?: number;
  copa_xg?: number;
  copa_xa?: number;
  copa_int?: number;
  copa_c?: number;
  copa_br?: number;
  copa_ge?: number;
  copa_de_pct?: number | null;
}

export interface CelulaPontuacao {
  valor: number | null;
  cor: string;
}

export interface PerformanceBucket {
  cedido: CelulaPontuacao;
  conquistado: CelulaPontuacao;
}

/** Performance por bucket (GOL, LAT, ZAG, MEI, ATA) de uma seleção. */
export type PerformancePorSigla = Record<string, PerformanceBucket>;

/**
 * Pontuação cruzada cedido/conquistado — somente Copa do Mundo 2026.
 * Valor `null` quando a seleção ainda não estreou.
 */
export type PontuacaoCedida = Record<string, PerformancePorSigla | null>;

export interface LinhaClassificacao {
  posicao: number;
  selecao: string;
  sigla: string;
  url_escudo: string | null;
  P: number;
  J: number;
  V: number;
  E: number;
  D: number;
  GM: number;
  GS: number;
  SG: number;
  aprov: number;
}

export type ClassificacaoGrupos = Record<string, LinhaClassificacao[]>;

/** Odds de jogador — marcar, assistir, marcar ou assistir e clean sheet. */
export interface OddsJogadorEntry {
  event_id: number;
  /** Sigla Cartola do adversário na partida das odds (ex.: CAT = Qatar). */
  adversario_sigla?: string | null;
  /** Data do confronto no calendário WC2026 (YYYY-MM-DD, âncora Brasil). */
  data_confronto?: string | null;
  rodada?: number | null;
  g_pct?: number | null;
  casa_g?: string | null;
  odds_g?: number | null;
  a_pct?: number | null;
  casa_a?: string | null;
  odds_a?: number | null;
  ga_pct?: number | null;
  casa_ga?: string | null;
  odds_ga?: number | null;
  sg_pct?: number | null;
  casa_sg?: string | null;
  odds_sg?: number | null;
}

export interface OddsJogadoresData {
  atualizado_em: string;
  /** Data de referência do calendário usada na compilação (YYYY-MM-DD, America/Sao_Paulo). */
  referencia_data?: string;
  total_jogadores: number;
  odds: Record<string, OddsJogadorEntry>;
}

export interface ParticipanteMataMata {
  rotulo: string;
  nome_fotmob: string;
  selecao: string | null;
  sigla: string | null;
  url_escudo: string | null;
  tbd: boolean;
  team_id: number | null;
}

export interface ConfrontoMataMata {
  draw_order: number | null;
  stage: string;
  match_id: string;
  mandante: ParticipanteMataMata;
  visitante: ParticipanteMataMata;
  placar_mandante: number | null;
  placar_visitante: number | null;
  mandante_venceu: boolean;
  visitante_venceu: boolean;
  finalizada: boolean;
  em_andamento: boolean;
  data: string;
  hora: string;
  utc_time: string;
}

export interface FaseMataMata {
  stage: string;
  confrontos: ConfrontoMataMata[];
}

export interface DadosMataMata {
  modo: string;
  atualizado_em: string | null;
  fases: FaseMataMata[];
  final: ConfrontoMataMata | null;
  disputa_bronze: ConfrontoMataMata | null;
}
