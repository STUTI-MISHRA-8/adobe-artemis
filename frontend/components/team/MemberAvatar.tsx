import { cn } from "@/lib/utils";

function initials(name: string) {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "")).toUpperCase() || "?";
}

export function MemberAvatar({
  name,
  color,
  size = "sm",
  className,
}: {
  name: string;
  color: string;
  size?: "xs" | "sm" | "md";
  className?: string;
}) {
  const sizeClasses = { xs: "h-5 w-5 text-[9px]", sm: "h-7 w-7 text-xs", md: "h-9 w-9 text-sm" }[size];
  return (
    <div
      title={name}
      className={cn("flex shrink-0 items-center justify-center rounded-full font-semibold text-white ring-2 ring-background", sizeClasses, className)}
      style={{ backgroundColor: color }}
    >
      {initials(name)}
    </div>
  );
}
