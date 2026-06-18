/** Badges de cobrador (pênalti / bola parada) ao lado do nome do jogador. */

import { Flag } from "lucide-react";
import { IconApito } from "@/components/icons/IconApito";
import type { CobradorAtleta } from "@/lib/cobradoresCopa";
import { tooltipCobrador } from "@/lib/cobradoresCopa";

type Props = {
  cobrador: CobradorAtleta | undefined;
};

export function IconesCobrador({ cobrador }: Props) {
  if (!cobrador?.penalti && !cobrador?.bola_parada) {
    return null;
  }

  const tooltip = tooltipCobrador(cobrador);

  return (
    <span className="inline-flex items-center gap-0.5" title={tooltip}>
      {cobrador.bola_parada ? (
        <Flag
          className="h-3.5 w-3.5 shrink-0 text-sky-400/90"
          aria-label="Cobrador de bola parada"
          strokeWidth={2.25}
        />
      ) : null}
      {cobrador.penalti ? (
        <IconApito size={14} className="shrink-0 text-amber-400/90" />
      ) : null}
    </span>
  );
}
