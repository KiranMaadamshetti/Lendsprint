import { useState } from "react";
import { ChevronRight, ScrollText } from "lucide-react";
import { formatINR } from "@/lib/format";

const SEV = {
  critical: "bg-red-50 text-red-700 border-red-200",
  review: "bg-amber-50 text-amber-700 border-amber-200",
  warning: "bg-amber-50 text-amber-700 border-amber-200",
  info: "bg-slate-50 text-slate-600 border-slate-200",
};

function fmtVal(v, unit) {
  if (unit === "inr") return formatINR(v);
  if (unit === "pct") return `${(v * 100).toFixed(1)}%`;
  if (unit === "x") return `${v}x`;
  return v;
}

function Row({ r }) {
  const [open, setOpen] = useState(false);
  const pass = r.result === "PASS";
  return (
    <div className="border-b border-border last:border-0">
      <button onClick={() => setOpen((o) => !o)} className="flex w-full items-center gap-3 px-4 py-2.5 text-left hover:bg-secondary/40 transition-colors" data-testid={`policy-rule-${r.id}`}>
        <ChevronRight className={`h-4 w-4 text-muted-foreground transition-transform ${open ? "rotate-90" : ""}`} strokeWidth={2} />
        <span className="tnum w-[130px] shrink-0 text-[12px] text-muted-foreground">{r.id}</span>
        <span className="min-w-0 flex-1 text-[13px] font-medium text-foreground truncate">{r.name}</span>
        <span className="tnum hidden sm:block w-[90px] text-right text-[13px] text-foreground">{fmtVal(r.actual, r.unit)}</span>
        <span className="tnum hidden md:block w-[90px] text-right text-[12px] text-muted-foreground">{r.operator} {fmtVal(r.threshold, r.unit)}</span>
        <span className={`w-[64px] text-center rounded-md border px-1.5 py-0.5 text-[11px] font-semibold ${pass ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-red-50 text-red-700 border-red-200"}`}>{r.result}</span>
        <span className={`hidden lg:inline-block rounded border px-1.5 py-0.5 text-[10px] uppercase ${SEV[r.severity]}`}>{r.severity}</span>
      </button>
      {open && (
        <div className="px-4 pb-3 pl-11 text-[12px] text-muted-foreground">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 rounded-md border border-border bg-secondary/40 p-3">
            <div><div className="label-eyebrow">Metric</div><div className="mt-0.5 text-foreground">{r.metric}</div></div>
            <div><div className="label-eyebrow">Actual</div><div className="mt-0.5 tnum text-foreground">{fmtVal(r.actual, r.unit)}</div></div>
            <div><div className="label-eyebrow">Policy</div><div className="mt-0.5 tnum text-foreground">{r.operator} {fmtVal(r.threshold, r.unit)}</div></div>
            <div><div className="label-eyebrow">Impact</div><div className={`mt-0.5 font-medium ${pass ? "text-emerald-700" : "text-red-700"}`}>{r.impact}</div></div>
          </div>
        </div>
      )}
    </div>
  );
}

export function PolicyTab({ decision }) {
  const pe = decision?.policy_evaluation;
  if (!pe) {
    return (
      <div className="rounded-lg border border-border bg-card p-12 text-center" data-testid="policy-empty">
        <ScrollText className="mx-auto h-8 w-8 text-muted-foreground" strokeWidth={1.5} />
        <h3 className="mt-3 text-[15px] font-semibold text-foreground">No policy evaluation yet</h3>
        <p className="mt-1 text-[13px] text-muted-foreground">Run the decision engine to evaluate this application against the active credit policy.</p>
      </div>
    );
  }
  const overallStyle = pe.overall === "PASS" ? "bg-emerald-50 text-emerald-700 border-emerald-200"
    : pe.overall === "REVIEW" ? "bg-amber-50 text-amber-700 border-amber-200" : "bg-red-50 text-red-700 border-red-200";
  const stats = [
    ["Rules Evaluated", pe.rules_evaluated], ["Passed", pe.passed],
    ["Review", pe.review], ["Warnings", pe.warnings], ["Critical Failures", pe.critical_failures],
  ];
  return (
    <div className="space-y-4 animate-fade-up" data-testid="policy-content">
      <div className="rounded-lg border border-border bg-card p-5">
        <div className="flex items-center justify-between">
          <div>
            <div className="label-eyebrow">Policy Evaluation</div>
            <div className="mt-1 text-[13px] text-muted-foreground">{pe.policy_name} · {pe.policy_version}</div>
          </div>
          <span className={`rounded-md border px-3 py-1 text-[13px] font-semibold ${overallStyle}`} data-testid="policy-overall">{pe.overall}</span>
        </div>
        <div className="mt-4 grid grid-cols-2 sm:grid-cols-5 gap-3">
          {stats.map(([k, v]) => (
            <div key={k} className="rounded-md border border-border bg-secondary/40 px-3 py-2">
              <div className="label-eyebrow">{k}</div>
              <div className="metric-num mt-1 text-[20px] font-semibold text-foreground">{v}</div>
            </div>
          ))}
        </div>
      </div>
      <div className="rounded-lg border border-border bg-card">
        <div className="hidden sm:flex items-center gap-3 border-b border-border px-4 py-2">
          <span className="inline-block h-4 w-4" />
          <span className="label-eyebrow w-[130px]">Rule</span>
          <span className="label-eyebrow flex-1">Name</span>
          <span className="label-eyebrow w-[90px] text-right">Actual</span>
          <span className="label-eyebrow hidden md:block w-[90px] text-right">Policy</span>
          <span className="label-eyebrow w-[64px] text-center">Result</span>
          <span className="label-eyebrow hidden lg:block">Severity</span>
        </div>
        {pe.rules.map((r) => <Row key={r.id} r={r} />)}
      </div>
    </div>
  );
}
