export function BrandMark({ size = 22 }: { size?: number }) {
  return (
    <span
      className="grid place-items-center rounded-md bg-ink"
      style={{ width: size, height: size }}
      aria-hidden
    >
      <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
        <path d="M2 7a5 5 0 1 1 8.5 3.5" stroke="#FBFAF6" strokeWidth="1.6" strokeLinecap="round" />
        <path
          d="M10.5 7.5L10.5 10.5L7.5 10.5"
          stroke="#FBFAF6"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </span>
  );
}

export function Brand({ className = "" }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2.5 font-medium tracking-tight ${className}`}>
      <BrandMark />
      <b className="text-[17px] font-medium">CrewLoop</b>
    </span>
  );
}

export function ArrowIcon({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 14 14" fill="none" aria-hidden>
      <path
        d="M3 7h8M7.5 3.5L11 7l-3.5 3.5"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
