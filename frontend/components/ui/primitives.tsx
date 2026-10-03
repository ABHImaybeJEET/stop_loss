import React from "react";

/** Shared terminal primitives: Card, SectionCard, Button, Badge, Skeleton, Input, Textarea. */

export function cn(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(" ");
}

/* ─── Card ─── */

export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("border border-line bg-white", className)} {...props} />;
}

export function SectionCard({
  id,
  title,
  icon,
  aside,
  children,
  className,
}: {
  id: string;
  title: string;
  icon?: React.ReactNode;
  aside?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section aria-labelledby={`${id}-title`} className={cn("border border-line bg-white", className)}>
      <header className="flex min-h-[40px] items-center justify-between gap-3 border-b border-line px-3 py-2 sm:px-4">
        <h3
          id={`${id}-title`}
          className="flex items-center gap-2 font-mono text-2xs font-bold uppercase tracking-widest text-ink"
        >
          {icon}
          {title}
        </h3>
        {aside}
      </header>
      <div className="p-3 sm:p-4">{children}</div>
    </section>
  );
}

/* ─── Button ─── */

type ButtonVariant = "primary" | "secondary" | "ghost";
type ButtonSize = "sm" | "md";

const BUTTON_VARIANTS: Record<ButtonVariant, string> = {
  primary: "bg-ink text-white border border-ink hover:bg-ink-soft disabled:bg-muted-soft disabled:border-muted-soft",
  secondary: "bg-white text-ink border border-line-strong hover:border-ink disabled:text-muted-soft disabled:hover:border-line-strong",
  ghost: "bg-transparent text-muted border border-transparent hover:text-ink hover:bg-subtle disabled:text-muted-soft",
};
const BUTTON_SIZES: Record<ButtonSize, string> = {
  sm: "h-7 px-2.5 text-2xs",
  md: "h-9 px-3.5 text-xs",
};

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "secondary", size = "md", className, type = "button", ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      className={cn(
        "inline-flex items-center justify-center gap-1.5 font-semibold uppercase tracking-wider transition-colors disabled:cursor-not-allowed",
        BUTTON_VARIANTS[variant],
        BUTTON_SIZES[size],
        className,
      )}
      {...props}
    />
  );
});

/* ─── Badge ─── */

type BadgeTone = "neutral" | "gain" | "loss" | "solid" | "outline";

const BADGE_TONES: Record<BadgeTone, string> = {
  neutral: "bg-subtle text-muted border-line",
  gain: "bg-gain-soft text-gain border-gain/20",
  loss: "bg-loss-soft text-loss border-loss/20",
  solid: "bg-ink text-white border-ink",
  outline: "bg-white text-ink border-line-strong",
};

export function Badge({
  tone = "neutral",
  className,
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { tone?: BadgeTone }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 whitespace-nowrap border px-1.5 py-0.5 font-mono text-2xs font-semibold uppercase tracking-wider",
        BADGE_TONES[tone],
        className,
      )}
      {...props}
    />
  );
}

/* ─── Skeleton ─── */

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden="true" className={cn("animate-pulse bg-subtle", className)} />;
}

export function SkeletonLines({ lines = 3 }: { lines?: number }) {
  return (
    <div className="space-y-2" aria-hidden="true">
      {Array.from({ length: lines }, (_, i) => (
        <Skeleton key={i} className={cn("h-3", i === lines - 1 ? "w-2/3" : "w-full")} />
      ))}
    </div>
  );
}

/* ─── Inputs ─── */

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  function Input({ className, ...props }, ref) {
    return (
      <input
        ref={ref}
        className={cn(
          "h-9 w-full border border-line-strong bg-white px-3 text-sm text-ink placeholder:text-muted-soft focus:border-ink",
          className,
        )}
        {...props}
      />
    );
  },
);

export const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(
  function Textarea({ className, ...props }, ref) {
    return (
      <textarea
        ref={ref}
        className={cn(
          "w-full resize-none border border-line-strong bg-white px-3 py-2 text-sm text-ink placeholder:text-muted-soft focus:border-ink",
          className,
        )}
        {...props}
      />
    );
  },
);
