import { describe, expect, it } from "vitest";
import { jogadorAtivoNoHub, oddsVigentes } from "./copaJogador";

describe("oddsVigentes", () => {
  it("bloqueia odds de jogadores de seleções eliminadas", () => {
    const hoje = new Date().toLocaleDateString("en-CA", { timeZone: "America/Sao_Paulo" });
    const jogadorEliminado = {
      atleta_id: 1,
      ativo_playoffs: false,
      proximo_adversario_sigla: "ARG",
      proximo_adversario_data: hoje,
      bucket_posicao: "ATA",
      copa_jogos_num: 4,
    } as any;

    const odds = {
      data_confronto: hoje,
      adversario_sigla: "ARG",
      g_pct: 12,
    } as any;

    expect(oddsVigentes(jogadorEliminado, odds)).toBe(false);
  });

  it("aceita odds de jogadores ainda ativos na competição", () => {
    const hoje = new Date().toLocaleDateString("en-CA", { timeZone: "America/Sao_Paulo" });
    const jogadorAtivo = {
      atleta_id: 2,
      ativo_playoffs: true,
      proximo_adversario_sigla: "ARG",
      proximo_adversario_data: hoje,
      bucket_posicao: "ATA",
      copa_jogos_num: 4,
    } as any;

    const odds = {
      data_confronto: hoje,
      adversario_sigla: "ARG",
      g_pct: 12,
    } as any;

    expect(oddsVigentes(jogadorAtivo, odds)).toBe(true);
  });

  it("oculta jogadores cuja seleção não participa das oitavas", () => {
    const jogadorForaOitavas = {
      atleta_id: 3,
      ativo_playoffs: true,
      selecao: "URUGUAY",
      sigla: "URU",
      bucket_posicao: "ATA",
      copa_jogos_num: 4,
    } as any;

    const dadosMataMata = {
      fases: [
        {
          stage: "1/8",
          confrontos: [
            {
              finalizada: false,
              mandante: { sigla: "BRA", selecao: "BRAZIL", tbd: false },
              visitante: { sigla: "ARG", selecao: "ARGENTINA", tbd: false },
            },
          ],
        },
      ],
      final: null,
      disputa_bronze: null,
    } as any;

    expect(jogadorAtivoNoHub(jogadorForaOitavas, dadosMataMata)).toBe(false);
  });
});
