import { PdGauge } from "@/components/common/PdGauge";
import { Button } from "@/components/ui/button";
import { formatLakh, formatDateTime } from "@/lib/format";
import { FileSearch, Loader2, TrendingUp, TrendingDown, ArrowRight, Wallet, Scale, Coins, ShieldAlert, PenLine } from "lucide-react";

const STEPS = [
  "Reading documents",
  "Extracting financial data",
  "Analysing cash flow",
  "Evaluating risk signals",
  "Generating decision",
  "Preparing credit memo",
];

const DECISION_COPY = {
  approve: "Recommended based on the available financial evidence.",
  review: "Manual analyst review recommended before final disposition.",
  reject: "Not recommended based on the available financial evidence.",
};

const DECISION_TEXT = {
  approve: "text-emerald-600",
  review: "text-amber-600",
  reject: "text-red-600",
};

function Processing({ stepIdx }) {
  return (
    <div className="rounded-lg border border-border bg-card p-8" data-testid="decision-processing">
      <div className="mx-auto max-w-md">
        <div className="flex items-center gap-2 text-[13px] font-medium text-foreground">
          <Loader2 className="h-4 w-4 animate-spin text-accent-foreground" />
          Running decision engine…
        </div>
        <div className="mt-5 space-y-2.5">
          {STEPS.map((s, i) => {
            const done = i < stepIdx;
            const active = i === stepIdx;
            return (
              <div key={s} className="flex items-center gap-3 text-[13px]">
                <span className={`grid h-5 w-5 place-items-center rounded-full border text-[10px] ${
                  done ? "border-emerald-500 bg-emerald-500 text-white" : active ? "border-accent-foreground text-accent-foreground" : "border-border text-muted-foreground"
                }`}>
                  {done ? "✓" : i + 1}
                </span>
                <span className={done || active ? "text-foreground" : "text-muted-foreground"}>{s}</span>
                {active && <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function EmptyDecision({ onRun, hasDocuments }) {
  return (
    <div className="rounded-lg border border-border bg-card p-12 text-center" data-testid="decision-empty">
      <div className="mx-auto grid h-14 w-14 place-items-center rounded-xl border border-border bg-secondary">
        <FileSearch className="h-6 w-6 text-muted-foreground" strokeWidth={1.6} />
      </div>
      <h3 className="mt-4 text-[16px] font-semibold text-foreground">Decision not generated</h3>
      <p className="mx-auto mt-1 max-w-sm text-[13px] text-muted-foreground">
        Run the decision engine to analyse the submitted documents and produce an explainable credit decision.
      </p>
      <Button className="mt-5" onClick={onRun} data-testid="run-decision-empty-btn">Run Decision</Button>
      {!hasDocuments && <p className="mt-3 text-[12px] text-amber-700">Upload at least one document first.</p>}
    </div>
  );
}

function CashCard({ icon: Icon, label, value, accent }) {
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="flex items-center gap-2">
        <Icon className={`h-4 w-4 ${accent}`} strokeWidth={1.8} />
        <span className="label-eyebrow">{label}</span>
      </div>
      <div className="metric-num mt-2 text-[24px] font-semibold text-foreground">{value}</div>
    </div>
  );
}

export function DecisionTab({ decision, running, stepIdx, onRun, hasDocuments, onOverrideClick }) {
  if (running) return <Processing stepIdx={stepIdx} />;
  if (!decision) return <EmptyDecision onRun={onRun} hasDocuments={hasDocuments} />;

  const cf = decision.cash_flow_summary;
  const override = decision.override;
  const gradeColor = decision.risk_grade === "A" ? "text-emerald-600" : decision.risk_grade === "B" ? "text-accent-foreground" : "text-amber-600";

  const loanTerms = decision.recommended_amount != null ? [
    { label: "Requested", value: formatLakh(decision.requested_amount) },
    { label: "Eligible", value: formatLakh(decision.eligible_amount) },
    { label: "Recommended", value: formatLakh(decision.recommended_amount) },
    { label: "ROI", value: `${decision.roi?.toFixed(2)}%` },
    { label: "Tenure", value: `${decision.tenure_months} mo` },
    { label: "EMI", value: `₹${(decision.emi || 0).toLocaleString("en-IN")}` },
  ] : null;

  const wfMax = decision.eligibility_waterfall ? Math.max(...decision.eligibility_waterfall.map((w) => w.value), 1) : 1;

  return (
    <div className="space-y-4 animate-fade-up">
      {override && (
        <div className="flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3" data-testid="override-banner">
          <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" strokeWidth={1.8} />
          <div className="text-[13px] text-amber-900">
            <span className="font-semibold">Analyst override applied.</span>{" "}
            Model recommended <span className="font-medium uppercase">{override.model_decision}</span>; final decision set to{" "}
            <span className="font-medium uppercase">{decision.decision}</span> by {override.by} on {formatDateTime(override.at)}.
            <div className="mt-1 text-amber-800">Reason: {override.reason}</div>
          </div>
        </div>
      )}

      {/* Decision + gauge */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 rounded-lg border border-border bg-card p-6">
          <div className="flex items-start justify-between">
            <div className="label-eyebrow">Credit Decision</div>
            <Button size="sm" variant="outline" onClick={onOverrideClick} data-testid="override-btn">
              <PenLine className="mr-1.5 h-3.5 w-3.5" strokeWidth={1.8} />Override
            </Button>
          </div>
          <div className="mt-2 flex items-center gap-3">
            <span className={`text-[30px] font-bold tracking-tight ${DECISION_TEXT[decision.decision]}`} data-testid="decision-result">
              {decision.decision.toUpperCase()}
            </span>
            {decision.risk_grade && <span className={`rounded-md border border-border px-2 py-0.5 text-[13px] font-semibold ${gradeColor}`}>Grade {decision.risk_grade}</span>}
            {override && <span className="rounded border border-border bg-secondary px-2 py-0.5 text-[11px] font-medium text-muted-foreground">Overridden</span>}
          </div>
          <p className="mt-1 text-[13px] text-muted-foreground">{DECISION_COPY[decision.decision]}</p>
          <div className="mt-5 flex flex-wrap gap-x-8 gap-y-2 border-t border-border pt-4 text-[12px]">
            <div><span className="text-muted-foreground">Model</span><div className="tnum mt-0.5 font-medium text-foreground">{decision.model_version}</div></div>
            <div><span className="text-muted-foreground">Policy</span><div className="tnum mt-0.5 font-medium text-foreground">{decision.policy_version || "—"}</div></div>
            <div><span className="text-muted-foreground">Generated</span><div className="mt-0.5 font-medium text-foreground">{formatDateTime(decision.created_at)}</div></div>
            <div><span className="text-muted-foreground">TAT</span><div className="tnum mt-0.5 font-medium text-foreground">{decision.tat_minutes} min</div></div>
          </div>
        </div>
        <div className="rounded-lg border border-border bg-card p-6 flex flex-col items-center justify-center">
          <PdGauge pd={decision.pd_score} decision={decision.model_decision || decision.decision} size={210} />
        </div>
      </div>

      {/* Loan terms */}
      {loanTerms && (
        <div className="rounded-lg border border-border bg-card p-5" data-testid="loan-terms">
          <h3 className="text-[14px] font-semibold text-foreground">Recommended Loan Structure</h3>
          <div className="mt-3 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            {loanTerms.map((t) => (
              <div key={t.label} className="rounded-md border border-border bg-secondary/40 px-3 py-2">
                <div className="label-eyebrow">{t.label}</div>
                <div className="metric-num mt-1 text-[17px] font-semibold text-foreground">{t.value}</div>
              </div>
            ))}
          </div>
          <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-[12px] text-muted-foreground">
            <span>Total interest: <span className="tnum font-medium text-foreground">₹{(decision.total_interest || 0).toLocaleString("en-IN")}</span></span>
            <span>Total repayment: <span className="tnum font-medium text-foreground">₹{(decision.total_repayment || 0).toLocaleString("en-IN")}</span></span>
            <span>Processing fee: <span className="tnum font-medium text-foreground">₹{(decision.processing_fee || 0).toLocaleString("en-IN")}</span></span>
            <span>Post-loan FOIR: <span className="tnum font-medium text-foreground">{((decision.post_loan_foir || 0) * 100).toFixed(1)}%</span></span>
          </div>
        </div>
      )}

      {/* Eligibility waterfall */}
      {decision.eligibility_waterfall && (
        <div className="rounded-lg border border-border bg-card p-5" data-testid="eligibility-waterfall">
          <h3 className="text-[14px] font-semibold text-foreground">Loan Eligibility Calculation</h3>
          <p className="mt-0.5 text-[12px] text-muted-foreground">Evidence-based waterfall — the recommended amount reflects the binding constraint.</p>
          <div className="mt-4 space-y-2">
            {decision.eligibility_waterfall.map((w, i) => {
              const last = i === decision.eligibility_waterfall.length - 1;
              return (
                <div key={w.label} className="flex items-center gap-3">
                  <span className="w-[150px] shrink-0 text-[12px] text-muted-foreground">{w.label}</span>
                  <div className="flex-1 h-6 rounded bg-secondary overflow-hidden">
                    <div className={`h-full rounded ${last ? "bg-emerald-500" : "bg-accent-foreground/70"}`} style={{ width: `${Math.max(4, (w.value / wfMax) * 100)}%` }} />
                  </div>
                  <span className="tnum w-[90px] text-right text-[13px] font-medium text-foreground">{formatLakh(w.value)}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Cash flow */}
      <div>
        <h3 className="text-[14px] font-semibold text-foreground">Cash Flow Summary</h3>
        <div className="mt-3 grid grid-cols-1 sm:grid-cols-3 gap-3">
          <CashCard icon={Wallet} label="Monthly Income" value={formatLakh(cf.income)} accent="text-emerald-600" />
          <CashCard icon={Coins} label="Monthly Obligations" value={formatLakh(cf.obligations)} accent="text-amber-600" />
          <CashCard icon={Scale} label="Net Cash Flow" value={formatLakh(cf.net)} accent="text-accent-foreground" />
        </div>
      </div>

      {/* Why this decision */}
      <div className="rounded-lg border border-border bg-card p-5" data-testid="explainability">
        <div className="flex items-center gap-2">
          <ArrowRight className="h-4 w-4 text-accent-foreground" strokeWidth={2} />
          <h3 className="text-[14px] font-semibold text-foreground">
            {decision.decision === "approve" ? "Why approved?" : decision.decision === "review" ? "Why review?" : "Why rejected?"}
          </h3>
        </div>
        {decision.policy_evaluation?.triggered?.length > 0 && (
          <div className="mt-2 text-[12px] text-muted-foreground">Policy rules triggered: <span className="tnum font-medium text-foreground">{decision.policy_evaluation.triggered.join(", ")}</span></div>
        )}
        <div className="mt-4 space-y-2.5">
          {decision.reason_codes.map((r, i) => {
            const positive = r.direction === "positive";
            return (
              <div key={r.code} className="flex items-center gap-3 rounded-md border border-border px-3 py-2.5" data-testid={`reason-${r.code}`}>
                <span className="tnum grid h-6 w-6 shrink-0 place-items-center rounded bg-secondary text-[11px] font-semibold text-muted-foreground">{String(i + 1).padStart(2, "0")}</span>
                <div className="min-w-0 flex-1">
                  <div className="text-[13px] font-medium text-foreground">{r.label}</div>
                  <div className="text-[11px] text-muted-foreground uppercase tracking-wide">{r.code}</div>
                </div>
                <div className={`flex items-center gap-1.5 text-[13px] font-semibold tnum ${positive ? "text-emerald-600" : "text-red-600"}`}>
                  {positive ? <TrendingUp className="h-4 w-4" strokeWidth={2} /> : <TrendingDown className="h-4 w-4" strokeWidth={2} />}
                  {r.weight > 0 ? `+${r.weight.toFixed(2)}` : r.weight.toFixed(2)}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
