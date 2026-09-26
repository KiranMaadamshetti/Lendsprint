import { useState } from "react";
import { Button } from "@/components/ui/button";
import { formatLakh, formatINR, DOC_TYPE_LABEL } from "@/lib/format";
import {
  FileText, ScanLine, Brain, Gavel, Layers, BadgeCheck, ChevronRight,
  Route, ArrowRight, CheckCircle2, XCircle, AlertTriangle,
} from "lucide-react";

const STATUS_STYLE = {
  ok: { dot: "bg-emerald-500", ring: "border-emerald-500/40", text: "text-emerald-600", icon: CheckCircle2 },
  warn: { dot: "bg-amber-500", ring: "border-amber-500/40", text: "text-amber-600", icon: AlertTriangle },
  bad: { dot: "bg-red-500", ring: "border-red-500/40", text: "text-red-600", icon: XCircle },
  idle: { dot: "bg-muted-foreground/40", ring: "border-border", text: "text-muted-foreground", icon: ChevronRight },
};

function Row({ k, v }) {
  return (
    <div className="flex items-center justify-between border-b border-border/60 py-1.5 last:border-0">
      <span className="text-[12px] text-muted-foreground">{k}</span>
      <span className="tnum text-[13px] font-medium text-foreground text-right">{v}</span>
    </div>
  );
}

export function DecisionTraceTab({ application, documents = [], decision, onRun }) {
  const [active, setActive] = useState("documents");

  if (!decision) {
    return (
      <div className="rounded-lg border border-border bg-card p-12 text-center" data-testid="trace-empty">
        <div className="mx-auto grid h-14 w-14 place-items-center rounded-xl border border-border bg-secondary">
          <Route className="h-6 w-6 text-muted-foreground" strokeWidth={1.6} />
        </div>
        <h3 className="mt-4 text-[16px] font-semibold text-foreground">No decision trace yet</h3>
        <p className="mx-auto mt-1 max-w-sm text-[13px] text-muted-foreground">
          Run the decision engine to generate the end-to-end trace from documents through to the final decision.
        </p>
        <Button className="mt-5" onClick={onRun} data-testid="trace-run-btn">Run Decision</Button>
      </div>
    );
  }

  const brain = decision.credit_brain || {};
  const f = brain.financials || {};
  const ev = brain.evidence || {};
  const pe = decision.policy_evaluation || {};
  const wf = decision.eligibility_waterfall || [];

  const confVals = Object.values(ev).map((e) => e.confidence).filter((c) => c != null);
  const avgConf = confVals.length ? Math.round((confVals.reduce((a, b) => a + b, 0) / confVals.length) * 100) : null;
  const contradictions = brain.contradictions || [];

  const gradeStatus = decision.risk_grade === "A" ? "ok" : decision.risk_grade === "B" ? "ok" : "warn";
  const policyStatus = pe.overall === "PASS" ? "ok" : pe.overall === "REVIEW" ? "warn" : "bad";
  const decStatus = decision.decision === "approve" ? "ok" : decision.decision === "review" ? "warn" : "bad";

  const stages = [
    {
      id: "documents", label: "Documents", icon: FileText,
      status: documents.length ? "ok" : "warn",
      summary: `${documents.length} ingested`,
    },
    {
      id: "extraction", label: "Extraction", icon: ScanLine,
      status: contradictions.length ? (contradictions.some((c) => c.severity === "critical") ? "bad" : "warn") : (avgConf == null ? "idle" : avgConf >= 92 ? "ok" : "warn"),
      summary: contradictions.length ? `${contradictions.length} contradiction${contradictions.length > 1 ? "s" : ""}` : (avgConf != null ? `${avgConf}% confidence` : "—"),
    },
    {
      id: "brain", label: "Credit Brain", icon: Brain,
      status: gradeStatus,
      summary: `PD ${(decision.pd_score * 100).toFixed(1)}% · ${decision.risk_grade}`,
    },
    {
      id: "policy", label: "Policy", icon: Gavel,
      status: policyStatus,
      summary: `${pe.passed || 0}/${pe.rules_evaluated || 0} · ${pe.overall || "—"}`,
    },
    {
      id: "structuring", label: "Structuring", icon: Layers,
      status: decision.recommended_amount > 0 ? "ok" : "bad",
      summary: `${formatLakh(decision.recommended_amount)}`,
    },
    {
      id: "decision", label: "Decision", icon: BadgeCheck,
      status: decStatus,
      summary: decision.decision.toUpperCase(),
    },
  ];

  return (
    <div className="space-y-4 animate-fade-up" data-testid="decision-trace-content">
      <div className="flex items-center gap-2 rounded-lg border border-border bg-card px-4 py-3">
        <Route className="h-4 w-4 text-accent-foreground" strokeWidth={1.8} />
        <span className="text-[13px] text-muted-foreground">Follow the full decision chain. Click any stage to inspect what happened and the evidence carried forward.</span>
      </div>

      {/* Flow */}
      <div className="rounded-lg border border-border bg-card p-5">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-stretch">
          {stages.map((s, i) => {
            const st = STATUS_STYLE[s.status];
            const isActive = active === s.id;
            const Icon = s.icon;
            return (
              <div key={s.id} className="flex flex-1 items-center gap-3 lg:flex-col lg:gap-2">
                <button
                  type="button"
                  onClick={() => setActive(s.id)}
                  data-testid={`trace-node-${s.id}`}
                  style={{ animationDelay: `${i * 70}ms` }}
                  className={`animate-fade-up w-full rounded-lg border p-3 text-left transition-all ${
                    isActive ? `${st.ring} bg-accent/40 shadow-sm` : "border-border bg-secondary/30 hover:border-accent-foreground/30 hover:bg-accent/20"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className={`grid h-8 w-8 place-items-center rounded-md border ${st.ring} bg-card`}>
                      <Icon className={`h-4 w-4 ${st.text}`} strokeWidth={1.8} />
                    </span>
                    <span className={`h-2 w-2 rounded-full ${st.dot}`} />
                  </div>
                  <div className="mt-2 text-[13px] font-semibold text-foreground">{s.label}</div>
                  <div className="tnum text-[11px] text-muted-foreground">{s.summary}</div>
                </button>
                {i < stages.length - 1 && (
                  <ArrowRight className="h-4 w-4 shrink-0 rotate-90 text-muted-foreground/50 lg:rotate-0" strokeWidth={2} />
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Detail */}
      <div className="rounded-lg border border-border bg-card p-5" data-testid="trace-detail">
        {active === "documents" && (
          <div>
            <h3 className="text-[14px] font-semibold text-foreground">Documents ingested</h3>
            <p className="mt-0.5 text-[12px] text-muted-foreground">Source files fed into the extraction pipeline.</p>
            {documents.length ? (
              <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-2">
                {documents.map((d) => (
                  <div key={d.id} className="flex items-center gap-2.5 rounded-md border border-border px-3 py-2">
                    <FileText className="h-4 w-4 text-muted-foreground/70" strokeWidth={1.8} />
                    <div className="min-w-0">
                      <div className="text-[13px] font-medium text-foreground truncate">{d.filename}</div>
                      <div className="text-[11px] text-muted-foreground">{DOC_TYPE_LABEL[d.doc_type] || d.doc_type}</div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="mt-3 text-[13px] text-amber-700">No documents were attached to this application.</div>
            )}
          </div>
        )}

        {active === "extraction" && (
          <div>
            <h3 className="text-[14px] font-semibold text-foreground">Extracted financials</h3>
            <p className="mt-0.5 text-[12px] text-muted-foreground">Structured fields derived from the documents{avgConf != null ? `, averaging ${avgConf}% extraction confidence` : ""}.</p>
            <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-x-6">
              <Row k="Annual turnover" v={formatINR(f.annual_turnover)} />
              <Row k="Avg monthly credits" v={formatLakh(f.avg_monthly_credits)} />
              <Row k="Avg monthly balance" v={formatLakh(f.avg_monthly_balance)} />
              <Row k="Existing EMI" v={formatINR(f.existing_emi)} />
              <Row k="CIBIL" v={f.cibil} />
              <Row k="Business vintage" v={`${f.business_vintage_months} mo`} />
              <Row k="Cheque bounces" v={f.cheque_bounces} />
              <Row k="NACH bounces" v={f.nach_bounces} />
            </div>
            {contradictions.length > 0 && (
              <div className="mt-4">
                <div className="text-[12px] font-semibold text-red-600">Contradictions detected</div>
                <ul className="mt-1.5 space-y-1">
                  {contradictions.map((c) => (
                    <li key={c.code} className="text-[12px] text-muted-foreground">
                      • <span className="font-medium text-foreground">{c.label}</span> — {c.variance_pct}% variance ({c.sources.join(" vs ")})
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {active === "brain" && (
          <div>
            <h3 className="text-[14px] font-semibold text-foreground">Credit Brain assessment</h3>
            <p className="mt-0.5 text-[12px] text-muted-foreground">Risk read derived from the extracted evidence.</p>
            <div className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="rounded-md border border-border bg-secondary/40 px-3 py-2"><div className="label-eyebrow">PD Score</div><div className="metric-num mt-1 text-[15px] font-semibold text-foreground">{(decision.pd_score * 100).toFixed(1)}%</div></div>
              <div className="rounded-md border border-border bg-secondary/40 px-3 py-2"><div className="label-eyebrow">Risk Grade</div><div className="metric-num mt-1 text-[15px] font-semibold text-foreground">{decision.risk_grade}</div></div>
              <div className="rounded-md border border-border bg-secondary/40 px-3 py-2"><div className="label-eyebrow">FOIR (pre)</div><div className="metric-num mt-1 text-[15px] font-semibold text-foreground">{(f.foir_before * 100).toFixed(1)}%</div></div>
              <div className="rounded-md border border-border bg-secondary/40 px-3 py-2"><div className="label-eyebrow">DSCR</div><div className="metric-num mt-1 text-[15px] font-semibold text-foreground">{f.dscr}x</div></div>
            </div>
            <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <div className="text-[12px] font-semibold text-emerald-700">Positive signals</div>
                <ul className="mt-1.5 space-y-1">
                  {(brain.positive_signals || []).map((s, i) => <li key={i} className="text-[12px] text-muted-foreground">• {s.label}</li>)}
                  {!(brain.positive_signals || []).length && <li className="text-[12px] text-muted-foreground">None material.</li>}
                </ul>
              </div>
              <div>
                <div className="text-[12px] font-semibold text-red-600">Risk signals</div>
                <ul className="mt-1.5 space-y-1">
                  {(brain.risk_signals || []).map((s, i) => <li key={i} className="text-[12px] text-muted-foreground">• {s.label}</li>)}
                  {!(brain.risk_signals || []).length && <li className="text-[12px] text-muted-foreground">None material.</li>}
                </ul>
              </div>
            </div>
          </div>
        )}

        {active === "policy" && (
          <div>
            <h3 className="text-[14px] font-semibold text-foreground">Policy evaluation · {decision.policy_version}</h3>
            <p className="mt-0.5 text-[12px] text-muted-foreground">
              Overall <span className={`font-semibold ${STATUS_STYLE[policyStatus].text}`}>{pe.overall}</span> — {pe.passed}/{pe.rules_evaluated} rules passed.
              {pe.triggered?.length ? <> Triggered: <span className="tnum font-medium text-foreground">{pe.triggered.join(", ")}</span>.</> : null}
            </p>
            <div className="mt-3 space-y-1.5">
              {(pe.rules || []).map((r) => (
                <div key={r.id} className="flex items-center justify-between rounded-md border border-border px-3 py-2">
                  <div className="min-w-0">
                    <div className="text-[12px] font-medium text-foreground">{r.name}</div>
                    <div className="tnum text-[11px] text-muted-foreground">{r.id} · actual {r.actual} {r.operator} {r.threshold}</div>
                  </div>
                  <span className={`shrink-0 rounded px-2 py-0.5 text-[11px] font-semibold ${r.result === "PASS" ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-600"}`}>{r.result}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {active === "structuring" && (
          <div>
            <h3 className="text-[14px] font-semibold text-foreground">Loan structuring</h3>
            <p className="mt-0.5 text-[12px] text-muted-foreground">Eligibility waterfall and the resulting recommended terms.</p>
            <div className="mt-3 space-y-2">
              {wf.map((w, i) => {
                const max = Math.max(...wf.map((x) => x.value), 1);
                const last = i === wf.length - 1;
                return (
                  <div key={w.label} className="flex items-center gap-3">
                    <span className="w-[140px] shrink-0 text-[12px] text-muted-foreground">{w.label}</span>
                    <div className="flex-1 h-5 rounded bg-secondary overflow-hidden">
                      <div className={`h-full rounded ${last ? "bg-emerald-500" : "bg-accent-foreground/70"}`} style={{ width: `${Math.max(4, (w.value / max) * 100)}%` }} />
                    </div>
                    <span className="tnum w-[80px] text-right text-[12px] font-medium text-foreground">{formatLakh(w.value)}</span>
                  </div>
                );
              })}
            </div>
            <div className="mt-4 grid grid-cols-3 sm:grid-cols-4 gap-3">
              <div className="rounded-md border border-border bg-secondary/40 px-3 py-2"><div className="label-eyebrow">ROI</div><div className="metric-num mt-1 text-[15px] font-semibold text-foreground">{decision.roi?.toFixed(2)}%</div></div>
              <div className="rounded-md border border-border bg-secondary/40 px-3 py-2"><div className="label-eyebrow">Tenure</div><div className="metric-num mt-1 text-[15px] font-semibold text-foreground">{decision.tenure_months} mo</div></div>
              <div className="rounded-md border border-border bg-secondary/40 px-3 py-2"><div className="label-eyebrow">EMI</div><div className="metric-num mt-1 text-[15px] font-semibold text-foreground">₹{(decision.emi || 0).toLocaleString("en-IN")}</div></div>
              <div className="rounded-md border border-border bg-secondary/40 px-3 py-2"><div className="label-eyebrow">Post-loan FOIR</div><div className="metric-num mt-1 text-[15px] font-semibold text-foreground">{((decision.post_loan_foir || 0) * 100).toFixed(1)}%</div></div>
            </div>
          </div>
        )}

        {active === "decision" && (
          <div>
            <h3 className="text-[14px] font-semibold text-foreground">Final decision</h3>
            <p className="mt-0.5 text-[12px] text-muted-foreground">The disposition rendered from the policy outcome and structuring.</p>
            <div className="mt-3 flex items-center gap-3">
              <span className={`text-[28px] font-bold tracking-tight ${STATUS_STYLE[decStatus].text}`}>{decision.decision.toUpperCase()}</span>
              {decision.risk_grade && <span className="rounded-md border border-border px-2 py-0.5 text-[13px] font-semibold text-foreground">Grade {decision.risk_grade}</span>}
              {decision.override && <span className="rounded border border-border bg-secondary px-2 py-0.5 text-[11px] font-medium text-muted-foreground">Overridden</span>}
            </div>
            <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-x-6">
              <Row k="Requested" v={formatLakh(decision.requested_amount)} />
              <Row k="Recommended" v={formatLakh(decision.recommended_amount)} />
              <Row k="Required authority" v={decision.required_authority || "—"} />
              <Row k="Policy version" v={decision.policy_version || "—"} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
