import React from "react";

interface StopLossLogoProps {
  /** Height of the logo in pixels. Width scales proportionally. */
  height?: number;
  /** Show just the icon (no wordmark text). */
  iconOnly?: boolean;
  /** CSS class for the wrapper */
  className?: string;
}

/**
 * StopLoss brand logo — shield with upward arrow + "stoploss" wordmark.
 * Rendered as inline SVG for crispness at any resolution.
 */
export default function StopLossLogo({
  height = 28,
  iconOnly = false,
  className = "",
}: StopLossLogoProps) {
  // Icon aspect ratio is roughly 1:1.6 (w:h), full logo with text is ~4.5:1
  const iconWidth = height * 0.625;
  const totalWidth = iconOnly ? iconWidth : height * 4.2;

  return (
    <svg
      width={totalWidth}
      height={height}
      viewBox={iconOnly ? "0 0 100 160" : "0 0 460 110"}
      fill="currentColor"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-label="StopLoss logo"
    >
      {iconOnly ? (
        /* ─── Icon Only ─── */
        <g fill="currentColor">
          {/* Shield body — open-top V/U shape */}
          <path d="M15 45 L15 105 Q15 135 50 145 Q85 135 85 105 L85 45 L72 45 L72 105 Q72 125 50 132 Q28 125 28 105 L28 45 Z" />
          {/* Arrow shaft */}
          <rect x="43" y="5" width="14" height="120" />
          {/* Arrow head */}
          <polygon points="50,0 28,32 42,32 42,5 58,5 58,32 72,32" />
          {/* Base platform */}
          <rect x="20" y="148" width="60" height="12" rx="1" />
          {/* Stem connecting shield to base */}
          <rect x="43" y="135" width="14" height="16" />
        </g>
      ) : (
        /* ─── Full Logo: Icon + Wordmark ─── */
        <g>
          {/* Shield icon (scaled to fit the left portion) */}
          <g transform="translate(5, 5) scale(0.62)">
            {/* Shield body */}
            <path d="M15 45 L15 105 Q15 135 50 145 Q85 135 85 105 L85 45 L72 45 L72 105 Q72 125 50 132 Q28 125 28 105 L28 45 Z" />
            {/* Arrow shaft */}
            <rect x="43" y="5" width="14" height="120" />
            {/* Arrow head */}
            <polygon points="50,0 28,32 42,32 42,5 58,5 58,32 72,32" />
            {/* Base platform */}
            <rect x="20" y="148" width="60" height="12" rx="1" />
            {/* Stem */}
            <rect x="43" y="135" width="14" height="16" />
          </g>

          {/* "stoploss" wordmark */}
          <text
            x="82"
            y="74"
            fontFamily="Inter, system-ui, -apple-system, 'Segoe UI', sans-serif"
            fontWeight="800"
            fontSize="52"
            letterSpacing="-1"
            fill="currentColor"
          >
            stoploss
          </text>
        </g>
      )}
    </svg>
  );
}
