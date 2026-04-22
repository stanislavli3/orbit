import type { ReactNode } from 'react';

interface PageTitleProps {
  title: string;
  subtitle?: ReactNode;
  icon?: ReactNode;
  actions?: ReactNode;
  underlineColor?: string;
}

// Hand-drawn style wobbly underline — generated path, looks pen-sketched
function Squiggle({ color }: { color: string }) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 220 12"
      className="mt-1 ml-[2px] h-[10px] w-[220px] -rotate-[0.5deg]"
      fill="none"
      preserveAspectRatio="none"
    >
      <path
        d="M2 7 Q 20 2, 42 6 T 84 5 Q 108 9, 132 4 T 178 6 Q 198 3, 216 7"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function PageTitle({
  title,
  subtitle,
  icon,
  actions,
  underlineColor = '#C66A4E',
}: PageTitleProps) {
  return (
    <div className="flex items-start justify-between mb-6">
      <div className="flex items-start gap-3">
        {icon && <div className="mt-0.5">{icon}</div>}
        <div className="flex flex-col">
          <h1 className="font-display text-[28px] leading-[1.15] font-medium text-[#2B2824] tracking-tight">
            {title}
          </h1>
          <Squiggle color={underlineColor} />
          {subtitle && (
            <p className="mt-2 text-sm text-[#8B7F73] max-w-[640px]">
              {subtitle}
            </p>
          )}
        </div>
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}
