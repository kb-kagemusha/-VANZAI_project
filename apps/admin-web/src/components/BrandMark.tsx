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
      <path fill="#f8efe1" d="M16 9L25.5 9L25.5 11.5L20 20.5L25.5 20.5L25.5 23L16 23L16 20.5L21.5 11.5L16 11.5Z" />
      <path fill="#d98f2b" d="M6.5 9L9.5 9L14 17.8L18.5 9L21.5 9L14.8 23.5L12 23.5Z" />
    </svg>
  );
}
