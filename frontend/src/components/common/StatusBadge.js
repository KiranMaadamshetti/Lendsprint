import { cn } from "@/lib/utils";

const DECISION_STYLES = {
  approve: "bg-emerald-50 text-emerald-700 border-emerald-200",
  review: "bg-amber-50 text-amber-700 border-amber-200",
  reject: "bg-red-50 text-red-700 border-red-200",
  pending: "bg-slate-100 text-slate-600 border-slate-200",
};

const DECISION_LABEL = {
  approve: "Approve",
  review: "Review",
  reject: "Reject",
  pending: "Pending",
};

export function DecisionBadge({ decision, size = "sm", className }) {
  const key = decision || "pending";
  return (
    <span
      data-testid={`decision-badge-${key}`}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border font-semibold uppercase tracking-wide",
        size === "lg" ? "px-3 py-1 text-[13px]" : "px-2 py-0.5 text-[11px]",
        DECISION_STYLES[key],
        className
      )}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current opacity-70" />
      {DECISION_LABEL[key]}
    </span>
  );
}

export function StatusBadge({ status }) {
  const decided = status === "decided";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-[11px] font-medium",
        decided ? "bg-slate-50 text-slate-700 border-slate-200" : "bg-blue-50 text-blue-700 border-blue-200"
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", decided ? "bg-slate-500" : "bg-blue-500")} />
      {decided ? "Decided" : "Pending"}
    </span>
  );
}

export function DocStatusBadge({ status }) {
  const ok = status === "processed";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-[11px] font-medium",
        ok ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-amber-50 text-amber-700 border-amber-200"
      )}
    >
      {ok ? "Processed" : "Pending"}
    </span>
  );
}
