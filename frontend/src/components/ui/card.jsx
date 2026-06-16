import { cn } from "@/lib/utils";

export function Card({ className, ...props }) {
  return (
    <div
      className={cn("rounded-xl border border-slate-200 bg-white shadow-sm", className)}
      {...props}
    />
  );
}

export function CardHeader({ className, ...props }) {
  return <div className={cn("border-b border-slate-100 px-4 py-3", className)} {...props} />;
}

export function CardBody({ className, ...props }) {
  return <div className={cn("px-4 py-3", className)} {...props} />;
}
