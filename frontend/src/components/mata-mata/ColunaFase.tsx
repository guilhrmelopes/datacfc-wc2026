import { CardConfronto } from "@/components/mata-mata/CardConfronto";
import type { ConfrontoMataMata } from "@/types/dados";

interface Props {
  rotulo: string;
  confrontos: ConfrontoMataMata[];
  alturaReferencia: number;
  alinhamento?: "inicio" | "fim";
}

export function ColunaFase({
  rotulo,
  confrontos,
  alturaReferencia,
  alinhamento = "inicio",
}: Props) {
  return (
    <div className="flex shrink-0 flex-col items-center">
      <p className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-[var(--color-muted)]">
        {rotulo}
      </p>
      <div
        className="flex w-full flex-col justify-around"
        style={{ minHeight: alturaReferencia }}
      >
        {confrontos.map((confronto) => (
          <div
            key={`${confronto.stage}-${confronto.draw_order}-${confronto.match_id}`}
            className={`flex ${alinhamento === "fim" ? "justify-end" : "justify-start"}`}
          >
            <CardConfronto confronto={confronto} />
          </div>
        ))}
      </div>
    </div>
  );
}

interface PropsLado {
  fases: { stage: string; rotulo: string; confrontos: ConfrontoMataMata[] }[];
  alturaReferencia: number;
  alinhamento: "inicio" | "fim";
}

export function LadoChaveamento({ fases, alturaReferencia, alinhamento }: PropsLado) {
  return (
    <div className="flex gap-3">
      {fases.map((fase) => (
        <ColunaFase
          key={fase.stage}
          rotulo={fase.rotulo}
          confrontos={fase.confrontos}
          alturaReferencia={alturaReferencia}
          alinhamento={alinhamento}
        />
      ))}
    </div>
  );
}
