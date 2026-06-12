import { useEffect, useState } from "react";
import { Cabecalho } from "@/components/layout/Cabecalho";
import { FaseGrupos } from "@/components/fase-grupos/FaseGrupos";
import { MercadoJogadores } from "@/components/mercado/MercadoJogadores";
import { RadarSelecoes } from "@/components/radar/RadarSelecoes";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  carregarDadosRadar,
  carregarDadosMercado,
  carregarDadosFase,
  type DadosMercado,
} from "@/lib/data";
import type { JogadorMercado, PontuacaoCedida, Selecao } from "@/types/dados";

type AbaAtiva = "radar" | "fase" | "mercado";

const SPINNER = (
  <div className="flex min-h-[200px] items-center justify-center">
    <p className="text-sm text-[var(--color-muted)]">Carregando…</p>
  </div>
);

const ERRO = (msg: string) => (
  <div className="py-8 text-center text-sm text-red-400">
    Erro: {msg}. Execute o pipeline Python e confira /public/data.
  </div>
);

function useAbaDados<T>(aba: AbaAtiva, abaAlvo: AbaAtiva, loader: () => Promise<T>) {
  const [dados, setDados] = useState<T | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);
  const [carregou, setCarregou] = useState(false);

  useEffect(() => {
    if (aba !== abaAlvo || carregou) return;
    setCarregando(true);
    loader()
      .then((d) => { setDados(d); setCarregou(true); })
      .catch((e: Error) => setErro(e.message))
      .finally(() => setCarregando(false));
  }, [aba, abaAlvo, carregou, loader]);

  return { dados, erro, carregando };
}

export default function App() {
  const [aba, setAba] = useState<AbaAtiva>("radar");

  const radar = useAbaDados(aba, "radar", carregarDadosRadar);
  const fase = useAbaDados(aba, "fase", carregarDadosFase);
  const mercado = useAbaDados<DadosMercado>(aba, "mercado", carregarDadosMercado);

  return (
    <div className="mx-auto min-h-screen max-w-[1600px] px-4 py-6 sm:px-6">
      <Cabecalho />
      <Tabs value={aba} onValueChange={(v) => setAba(v as AbaAtiva)}>
        <TabsList className="mb-2 flex flex-wrap">
          <TabsTrigger value="fase">Fase de Grupos</TabsTrigger>
          <TabsTrigger value="radar">HUB Seleções</TabsTrigger>
          <TabsTrigger value="mercado">HUB Jogadores</TabsTrigger>
        </TabsList>

        <TabsContent value="fase">
          {fase.carregando && SPINNER}
          {fase.erro && ERRO(fase.erro)}
          {fase.dados && (
            <FaseGrupos classificacao={fase.dados.classificacao} />
          )}
        </TabsContent>

        <TabsContent value="radar">
          {radar.carregando && SPINNER}
          {radar.erro && ERRO(radar.erro)}
          {radar.dados && (
            <RadarSelecoes
              selecoes={radar.dados.selecoes as Selecao[]}
              pontuacaoCedida={radar.dados.pontuacaoCedida as PontuacaoCedida}
            />
          )}
        </TabsContent>

        <TabsContent value="mercado">
          {mercado.carregando && SPINNER}
          {mercado.erro && ERRO(mercado.erro)}
          {mercado.dados && (
            <MercadoJogadores
              jogadores={mercado.dados.jogadores as JogadorMercado[]}
              oddsJogadores={mercado.dados.oddsJogadores}
              pontuacaoCedida={mercado.dados.pontuacaoCedida as PontuacaoCedida}
            />
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
