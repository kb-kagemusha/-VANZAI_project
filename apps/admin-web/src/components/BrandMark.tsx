export function BrandMark({ size = 48 }: { size?: number }) {
  return (
    <svg
      className="brand-mark"
      width={size}
      height={size}
      viewBox="0 0 32 32"
      overflow="hidden"
      shapeRendering="geometricPrecision"
      role="img"
      aria-label="VANZAI"
    >
      <rect width="32" height="32" rx="8" fill="#1b2530" />
      <path fill="#f8efe1" d="M18 8h8.5v3H20.5l4.5 7H18v3h8.5v3H18v3h4.8l-4.5-7H26.5V24h-8.5V8z" />
      <path fill="#d98f2b" d="M6.5 9h2.8l4 8.2L17.2 9H19.8l-5.8 14h-2.6L6.5 9z" />
    </svg>
  );
}
