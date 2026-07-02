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
      <path fill="#d98f2b" d="M7 9h3l4.2 8.4L18.4 9H21l-6.2 14h-2.8L7 9z" />
      <path fill="#f8efe1" d="M17.5 18.2 21 23h-2.8l-2.2-3.4-2.2 3.4H11l3.5-4.8 3-4.2h2.8l-2.8 4z" />
    </svg>
  );
}
