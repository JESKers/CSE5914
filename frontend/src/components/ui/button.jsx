import { cn } from "@/lib/utils";

const VARIANTS = {
  primary: "bg-blue-600 text-white hover:bg-blue-700",
  outline: "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50",
  ghost: "text-slate-600 hover:bg-slate-100",
};

export function Button({ variant = "primary", className, ...props }) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center rounded-md px-4 py-2 text-sm font-medium transition-colors disabled:opacity-50",
        VARIANTS[variant],
        className
      )}
      {...props}
    />
  );
}
