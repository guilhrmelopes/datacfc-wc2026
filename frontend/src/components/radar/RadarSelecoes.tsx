import { useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { PontuacaoCedida, Selecao } from "@/types/dados";
import { FiltrosScouts } from "./FiltrosScouts";
import { Recorrencia } from "./Recorrencia";
import { TabelaScouts } from "./TabelaScouts";

interface Props {
  selecoes: Selecao[];
  pontuacaoCedida: PontuacaoCedida;
}

export function RadarSelecoes({ selecoes, pontuacaoCedida }: Props) {
  const [aba, setAba] = useState("scouts");
  const [competicao, setCompeticao] = useState("TODAS");
  const [grupo, setGrupo] = useState("TODOS");

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
            competicao={competicao}
            grupo={grupo}
            onCompeticaoChange={setCompeticao}
            onGrupoChange={setGrupo}
          />
        )}
      </div>

      <TabsContent value="scouts">
        <TabelaScouts selecoes={selecoes} competicao={competicao} grupo={grupo} />
      </TabsContent>
      <TabsContent value="recorrencia">
        <Recorrencia selecoes={selecoes} pontuacaoCedida={pontuacaoCedida} />
      </TabsContent>
    </Tabs>
  );
}
