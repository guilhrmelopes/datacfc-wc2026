import { useMemo, useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { DadosMataMata, PontuacaoCedida, Selecao } from "@/types/dados";
import type { ClassificacaoGruposParseada } from "@/lib/classificacaoGrupos";
import {
  selecoesVivasHub,
  type ModoRatingSelecao,
} from "@/lib/ratingSelecao";
import { FiltrosScouts } from "./FiltrosScouts";
import { Recorrencia } from "./Recorrencia";
import { TabelaScouts } from "./TabelaScouts";

interface Props {
  selecoes: Selecao[];
  pontuacaoCedida: PontuacaoCedida;
  classificacao: ClassificacaoGruposParseada;
  mataMata?: DadosMataMata | null;
}

export function RadarSelecoes({
  selecoes,
  pontuacaoCedida,
  classificacao,
  mataMata = null,
}: Props) {
  const [aba, setAba] = useState("scouts");
  const [escopo, setEscopo] = useState<"vivas" | "todas">("vivas");
  const [modoRating, setModoRating] = useState<ModoRatingSelecao>("copa");

  const vivas = useMemo(() => selecoesVivasHub(mataMata), [mataMata]);
  const mostrarEscopoVivas = Boolean(vivas && vivas.size > 0 && vivas.size <= 16);

  const selecoesTabela = useMemo(() => {
    if (mostrarEscopoVivas && escopo === "vivas" && vivas) {
      return selecoes.filter((s) => s.selecao && vivas.has(s.selecao));
    }
    return selecoes;
  }, [selecoes, escopo, vivas, mostrarEscopoVivas]);

  return (
    <Tabs value={aba} onValueChange={setAba}>
      <div className="flex flex-wrap items-center gap-3">
        <TabsList>
          <TabsTrigger value="scouts" className="text-sm">
            Scouts
          </TabsTrigger>
          <TabsTrigger value="recorrencia" className="text-sm">
            Recorrência
          </TabsTrigger>
        </TabsList>
        {aba === "scouts" && (
          <FiltrosScouts
            escopo={escopo}
            modoRating={modoRating}
            onEscopoChange={setEscopo}
            onModoRatingChange={setModoRating}
            mostrarEscopoVivas={mostrarEscopoVivas}
          />
        )}
      </div>

      <TabsContent value="scouts">
        <TabelaScouts
          selecoes={selecoesTabela}
          competicao="TODAS"
          grupo="TODOS"
          modoRating={modoRating}
        />
      </TabsContent>
      <TabsContent value="recorrencia">
        <Recorrencia
          selecoes={selecoes}
          pontuacaoCedida={pontuacaoCedida}
          classificacao={classificacao}
        />
      </TabsContent>
    </Tabs>
  );
}
