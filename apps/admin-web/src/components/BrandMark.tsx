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
      <path fill="#f8efe1" d="M16 9h9v2.4H18.6l4.2 5.4H16v2.4h9v2.4H16v2.4h4.4l-4.2-5.4H25V23h-9V9z" />
      <path fill="#d98f2b" d="M7 9h3l4.2 8.4L18.4 9H21l-6.2 14h-2.8L7 9z" />
    </svg>
  );
}
