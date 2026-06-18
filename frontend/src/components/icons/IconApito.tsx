/** Ícone de apito (cobrador de pênalti) — traço compatível com lucide-react. */

type Props = {
  className?: string;
  size?: number;
};

export function IconApito({ className, size = 14 }: Props) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden
    >
      <path d="M14 9.5V16a3 3 0 1 1-6 0V9.5l6-3 6 3z" />
      <circle cx="8" cy="7" r="2.5" />
      <path d="M5 10v1.5a5 5 0 0 0 10 0V10" />
    </svg>
  );
}
