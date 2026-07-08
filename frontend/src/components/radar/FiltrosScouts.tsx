import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { ModoRatingSelecao } from "@/lib/ratingSelecao";

export const GRUPOS_FILTRO = [
  "TODOS",
  "A",
  "B",
  "C",
  "D",
  "E",
  "F",
  "G",
  "H",
  "I",
  "J",
  "K",
  "L",
] as const;

const CLASSE_SELECT_COMPACTO = "h-8 min-w-[160px] text-sm";

interface Props {
  escopo: "vivas" | "todas";
  modoRating: ModoRatingSelecao;
  onEscopoChange: (valor: "vivas" | "todas") => void;
  onModoRatingChange: (valor: ModoRatingSelecao) => void;
  mostrarEscopoVivas?: boolean;
}

export function FiltrosScouts({
  escopo,
  modoRating,
  onEscopoChange,
  onModoRatingChange,
  mostrarEscopoVivas = false,
}: Props) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      {mostrarEscopoVivas && (
        <Select
          value={escopo}
          onValueChange={(v) => onEscopoChange(v as "vivas" | "todas")}
        >
          <SelectTrigger className={CLASSE_SELECT_COMPACTO}>
            <SelectValue placeholder="Escopo" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="vivas">Em disputa</SelectItem>
            <SelectItem value="todas">Todas</SelectItem>
          </SelectContent>
        </Select>
      )}

      <Select
        value={modoRating}
        onValueChange={(v) => onModoRatingChange(v as ModoRatingSelecao)}
      >
        <SelectTrigger className={`${CLASSE_SELECT_COMPACTO} min-w-[200px]`}>
          <SelectValue placeholder="Rating" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="copa">Rating Copa do Mundo</SelectItem>
          <SelectItem value="ko">Rating Mata-mata</SelectItem>
        </SelectContent>
      </Select>
    </div>
  );
}
