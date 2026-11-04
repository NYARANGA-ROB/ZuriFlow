import { APP_NAME } from "@/constants/branding";
import { cn } from "@/lib/utils";

// Reusable product wordmark. Theme-aware text styling; pass className for size
// (e.g. "text-2xl" or "text-lg").
export function BrandLogo({
  className,
  inverse = false,
  mark = false,
}: {
  className?: string;
  inverse?: boolean;
  mark?: boolean;
}) {
  if (mark) {
    return (
      <span
        aria-label={APP_NAME}
        className={cn(
          "inline-flex aspect-square min-w-[1.75rem] items-center justify-center rounded-md bg-primary px-1.5 text-sm font-bold text-primary-foreground",
          className,
        )}
      >
        Z
      </span>
    );
  }

  return (
    <span
      className={cn(
        "select-none text-xl font-semibold tracking-tight",
        inverse ? "text-zinc-50" : "text-foreground",
        className,
      )}
    >
      {APP_NAME}
    </span>
  );
}
