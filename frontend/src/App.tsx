import { useEffect, useState } from "react";
import { Analytics } from "@vercel/analytics/react";
import { Cabecalho } from "@/components/layout/Cabecalho";
import { FaseGrupos } from "@/components/fase-grupos/FaseGrupos";
import { MataMata } from "@/components/mata-mata/MataMata";
import { MercadoJogadores } from "@/components/mercado/MercadoJogadores";
import { RadarSelecoes } from "@/components/radar/RadarSelecoes";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { registrarVisualizacao } from "@/lib/ga4";
import {
  carregarDadosRadar,
  carregarDadosMercado,
  carregarDadosFase,
  carregarDadosMataMata,
  type DadosMercado,
} from "@/lib/data";
import type { DadosMataMata, JogadorMercado, PontuacaoCedida, Selecao } from "@/types/dados";

type AbaAtiva = "radar" | "fase" | "mata" | "mercado";

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

  useEffect(() => {
    registrarVisualizacao(aba);
  }, [aba]);

  useEffect(() => {
    void carregarDadosMercado();
  }, []);

  const radar = useAbaDados(aba, "radar", carregarDadosRadar);
  const fase = useAbaDados(aba, "fase", carregarDadosFase);
  const mata = useAbaDados<DadosMataMata>(aba, "mata", carregarDadosMataMata);
  const mercado = useAbaDados<DadosMercado>(aba, "mercado", carregarDadosMercado);

  return (
    <div className="mx-auto min-h-screen max-w-[1600px] px-4 py-6 sm:px-6">
      <div
        role="status"
        className="mb-4 border-b border-[var(--color-border)] pb-3 text-sm text-[var(--color-muted)]"
      >
        Copa 2026 encerrada — esta é uma demo congelada do Data CFC. Os dados não são mais atualizados.
      </div>
      <Cabecalho />
      <Tabs value={aba} onValueChange={(v) => setAba(v as AbaAtiva)}>
        <TabsList className="mb-2 flex flex-wrap">
          <TabsTrigger value="fase">Fase de Grupos</TabsTrigger>
          <TabsTrigger value="mata">Mata-mata</TabsTrigger>
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

        <TabsContent value="mata">
          {mata.carregando && SPINNER}
          {mata.erro && ERRO(mata.erro)}
          {mata.dados && <MataMata dados={mata.dados} />}
        </TabsContent>

        <TabsContent value="radar">
          {radar.carregando && SPINNER}
          {radar.erro && ERRO(radar.erro)}
          {radar.dados && (
            <RadarSelecoes
              selecoes={radar.dados.selecoes as Selecao[]}
              pontuacaoCedida={radar.dados.pontuacaoCedida as PontuacaoCedida}
              classificacao={radar.dados.classificacao}
              mataMata={radar.dados.mataMata}
            />
          )}
        </TabsContent>

        <TabsContent value="mercado">
          {mercado.carregando && SPINNER}
          {mercado.erro && ERRO(mercado.erro)}
          {mercado.dados && (
            <MercadoJogadores
              jogadores={mercado.dados.jogadores as JogadorMercado[]}
              selecoes={mercado.dados.selecoes as Selecao[]}
              confrontosCopa={mercado.dados.confrontosCopa}
              partidasProcessadas={mercado.dados.partidasProcessadas}
              oddsJogadores={mercado.dados.oddsJogadores}
              mlContextoRodada={mercado.dados.mlContextoRodada}
              cobradoresCopa={mercado.dados.cobradoresCopa}
              rodadaCartolaAtual={mercado.dados.rodadaCartolaAtual}
              pontuacaoCedida={mercado.dados.pontuacaoCedida as PontuacaoCedida}
              mataMata={mercado.dados.mataMata}
            />
          )}
        </TabsContent>
      </Tabs>
      <Analytics />
    </div>
  );
}
