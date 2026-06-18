/** Badges de cobrador (escanteio / falta / pênalti) ao lado do nome do jogador. */

import type { CobradorAtleta } from "@/lib/cobradoresCopa";
import { tooltipTipoCobranca } from "@/lib/cobradoresCopa";

const ICONES = {
  escanteio: "/assets/icons/cobrador-escanteio.png",
  falta: "/assets/icons/cobrador-falta.png",
  penalti: "/assets/icons/cobrador-penalti.png",
} as const;

type Props = {
  cobrador: CobradorAtleta | undefined;
};

function IconeCobrador({
  src,
  alt,
  title,
}: {
  src: string;
  alt: string;
  title: string;
}) {
  return (
    <img
      src={src}
      alt={alt}
      title={title}
      className="h-[15px] w-[15px] shrink-0 object-contain opacity-90"
      loading="lazy"
      decoding="async"
    />
  );
}

export function IconesCobrador({ cobrador }: Props) {
  if (!cobrador?.penalti && !cobrador?.escanteio && !cobrador?.falta && !cobrador?.bola_parada) {
    return null;
  }

  const escanteio = cobrador.escanteio ?? cobrador.bola_parada;
  const falta = cobrador.falta ?? cobrador.bola_parada;
  const ordemEscanteio = cobrador.ordem_escanteio ?? cobrador.ordem_bola_parada;
  const ordemFalta = cobrador.ordem_falta ?? cobrador.ordem_bola_parada;

  return (
    <span className="inline-flex items-center gap-0.5 align-middle">
      {escanteio ? (
        <IconeCobrador
          src={ICONES.escanteio}
          alt="Cobrador de escanteio"
          title={tooltipTipoCobranca("escanteio", ordemEscanteio)}
        />
      ) : null}
      {falta ? (
        <IconeCobrador
          src={ICONES.falta}
          alt="Cobrador de falta"
          title={tooltipTipoCobranca("falta", ordemFalta)}
        />
      ) : null}
      {cobrador.penalti ? (
        <IconeCobrador
          src={ICONES.penalti}
          alt="Cobrador de pênalti"
          title={tooltipTipoCobranca("penalti", cobrador.ordem_penalti)}
        />
      ) : null}
    </span>
  );
}
