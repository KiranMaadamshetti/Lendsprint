import { useEffect, useState } from "react";
import { toast } from "sonner";
import { getCreditBrain, apiErrorMessage } from "@/lib/api";
import { formatINR, formatLakh } from "@/lib/format";
import { Skeleton } from "@/components/ui/skeleton";
import { TrendingUp, TrendingDown, ShieldCheck, AlertTriangle, Brain, GitCompareArrows, FileCheck2, FileX2, CheckCircle2 } from "lucide-react";
import { EvidenceMetric, EvidenceSheet } from "@/components/application/EvidencePanel";

const SEV_DOT = { critical: "bg-red-500", review: "bg-amber-500", warning: "bg-amber-500", info: "bg-emerald-500" };
const CONTRA_STYLE = {
  critical: { border: "border-red-200", bg: "bg-red-50", text: "text-red-700", chip: "bg-red-100 text-red-700" },
  review: { border: "border-amber-200", bg: "bg-amber-50", text: "text-amber-700", chip: "bg-amber-100 text-amber-700" },
};

function Contradiction({ c }) {
  const st = CONTRA_STYLE[c.severity] || CONTRA_STYLE.review;
  return (
    <div className={`rounded-md border ${st.border} ${st.bg} px-3 py-2.5`} data-testid={`contradiction-${c.code}`}>
      <div className="flex items-center justify-between gap-2">
        <div className={`text-[13px] font-semibold ${st.text}`}>{c.label}</div>
        <span className={`shrink-0 rounded px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${st.chip}`}>{c.severity} · {c.variance_pct}%</span>
      </div>
      <div className="mt-1 text-[12px] text-foreground/80">{c.detail}</div>
      <div className="mt-2 flex flex-wrap gap-3">
        {c.values.map((v, i) => (
          <div key={i} className="rounded border border-border bg-card px-2 py-1">
            <div className="label-eyebrow">{v.label}</div>
            <div className="tnum text-[12px] font-medium text-foreground">{v.value}</div>
          </div>
        ))}
      </div>
      <div className="mt-1.5 text-[11px] text-muted-foreground">Sources: {c.sources.join(" · ")}</div>
    </div>
  );
}

function Signal({ s, positive }) {
  return (
    <div className="flex items-start gap-3 rounded-md border border-border px-3 py-2.5">
      <span className={`mt-1 h-2 w-2 shrink-0 rounded-full ${positive ? "bg-emerald-500" : SEV_DOT[s.severity] || "bg-amber-500"}`} />
      <div className="min-w-0 flex-1">
        <div className="text-[13px] font-medium text-foreground">{s.label}</div>
        <div className="text-[12px] text-muted-foreground">{s.evidence}</div>
        <div className="mt-0.5 text-[11px] text-muted-foreground/80">Source: {s.source}</div>
      </div>
      {positive ? <TrendingUp className="h-4 w-4 text-emerald-600" strokeWidth={1.8} /> : <TrendingDown className="h-4 w-4 text-red-500" strokeWidth={1.8} />}
    </div>
  );
}

export function CreditBrainTab({ applicationId }) {
  const [brain, setBrain] = useState(null);
  const [readiness, setReadiness] = useState(null);
  const [loading, setLoading] = useState(true);
  const [evItem, setEvItem] = useState(null);

  useEffect(() => {
    getCreditBrain(applicationId)
      .then((d) => { setBrain(d.credit_brain); setReadiness(d.readiness); })
      .catch((e) => toast.error(apiErrorMessage(e)))
      .finally(() => setLoading(false));
  }, [applicationId]);

  if (loading) return <div className="space-y-3"><Skeleton className="h-40 w-full" /><Skeleton className="h-64 w-full" /></div>;
  if (!brain) return null;

  const f = brain.financials;
  const ev = brain.evidence || {};
  const contradictions = brain.contradictions || [];
  const maxTrend = Math.max(...brain.cash_flow_trend.map((t) => t.value), 1);

  return (
    <div className="space-y-4 animate-fade-up" data-testid="credit-brain-content">
      <div className="flex items-center gap-2 rounded-lg border border-border bg-card px-4 py-3">
        <Brain className="h-4 w-4 text-accent-foreground" strokeWidth={1.8} />
        <span className="text-[13px] text-muted-foreground">Credit Brain provides structured evidence only. Click any figure to trace its source, page and calculation.</span>
      </div>

      <div className="rounded-lg border border-border bg-card p-5">
        <h3 className="text-[14px] font-semibold text-foreground">Financial Health</h3>
        <div className="mt-3 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
          <EvidenceMetric label="Annual Turnover" value={formatINR(f.annual_turnover)} evidence={ev.annual_turnover} onOpen={setEvItem} />
          <EvidenceMetric label="Avg Monthly Credits" value={formatLakh(f.avg_monthly_credits)} evidence={ev.avg_monthly_credits} onOpen={setEvItem} />
          <EvidenceMetric label="Avg Monthly Balance" value={formatLakh(f.avg_monthly_balance)} evidence={ev.avg_monthly_balance} onOpen={setEvItem} />
          <EvidenceMetric label="Net Cash Flow" value={formatLakh(f.net_cash_flow)} evidence={ev.net_cash_flow} onOpen={setEvItem} />
          <EvidenceMetric label="Existing EMI" value={formatINR(f.existing_emi)} evidence={ev.existing_emi} onOpen={setEvItem} />
          <EvidenceMetric label="FOIR (pre-loan)" value={`${(f.foir_before * 100).toFixed(1)}%`} evidence={ev.foir_before} onOpen={setEvItem} />
          <EvidenceMetric label="DSCR" value={`${f.dscr}x`} evidence={ev.dscr} onOpen={setEvItem} />
          <EvidenceMetric label="Banking History" value={`${f.banking_history_months} mo`} evidence={ev.banking_history_months} onOpen={setEvItem} />
          <EvidenceMetric label="Business Vintage" value={`${f.business_vintage_months} mo`} evidence={ev.business_vintage_months} onOpen={setEvItem} />
          <EvidenceMetric label="CIBIL" value={f.cibil} evidence={ev.cibil} onOpen={setEvItem} />
          <EvidenceMetric label="Cheque Bounces" value={f.cheque_bounces} evidence={ev.cheque_bounces} onOpen={setEvItem} />
          <EvidenceMetric label="NACH Bounces" value={f.nach_bounces} evidence={ev.nach_bounces} onOpen={setEvItem} />
        </div>
      </div>

      {readiness && (
        <div className="rounded-lg border border-border bg-card p-5" data-testid="doc-readiness">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {readiness.ready
                ? <FileCheck2 className="h-4 w-4 text-emerald-600" strokeWidth={1.8} />
                : <FileX2 className="h-4 w-4 text-red-600" strokeWidth={1.8} />}
              <h3 className="text-[14px] font-semibold text-foreground">Document Readiness</h3>
            </div>
            <span className={`rounded px-2 py-0.5 text-[11px] font-semibold ${readiness.ready ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-600"}`} data-testid="readiness-status">
              {readiness.ready ? "Ready to decide" : "Decision blocked"}
            </span>
          </div>
          {!readiness.ready && (
            <div className="mt-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-700">
              Missing mandatory document(s): <span className="font-semibold">{readiness.missing.join(", ")}</span>. The decision engine is blocked until these are uploaded and classified.
            </div>
          )}
          <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-2">
            {readiness.checklist.map((c) => (
              <div key={c.label} className="flex items-center justify-between rounded-md border border-border px-3 py-2">
                <div className="flex items-center gap-2">
                  {c.present
                    ? <CheckCircle2 className="h-4 w-4 text-emerald-600" strokeWidth={1.8} />
                    : <AlertTriangle className="h-4 w-4 text-red-500" strokeWidth={1.8} />}
                  <span className="text-[13px] text-foreground">{c.label}</span>
                </div>
                <div className="flex items-center gap-2">
                  {c.mandatory && <span className="rounded bg-secondary px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">Mandatory</span>}
                  {!c.verifiable && <span className="rounded bg-secondary px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">Attested</span>}
                  <span className={`text-[12px] font-medium ${c.present ? "text-emerald-700" : "text-red-600"}`}>{c.present ? "Present" : "Missing"}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="rounded-lg border border-border bg-card p-5" data-testid="contradictions-panel">
        <div className="flex items-center gap-2">
          <GitCompareArrows className="h-4 w-4 text-accent-foreground" strokeWidth={1.8} />
          <h3 className="text-[14px] font-semibold text-foreground">Contradictions & Data Integrity</h3>
        </div>
        <p className="mt-0.5 text-[12px] text-muted-foreground">Cross-source checks comparing figures across GST, ITR and banking documents.</p>
        <div className="mt-3 space-y-2">
          {contradictions.length ? (
            contradictions.map((c) => <Contradiction key={c.code} c={c} />)
          ) : (
            <div className="flex items-center gap-2 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2.5" data-testid="no-contradictions">
              <CheckCircle2 className="h-4 w-4 text-emerald-600" strokeWidth={1.8} />
              <span className="text-[13px] text-emerald-800">No material contradictions detected across GST, ITR and banking sources.</span>
            </div>
          )}
        </div>
      </div>


      <div className="rounded-lg border border-border bg-card p-5">
        <h3 className="text-[14px] font-semibold text-foreground">Cash Flow Trend</h3>
        <div className="mt-4 flex items-end gap-3 h-32">
          {brain.cash_flow_trend.map((t) => (
            <div key={t.month} className="flex h-full flex-1 flex-col items-center justify-end gap-1.5">
              <div className="w-full rounded-t bg-accent-foreground/80" style={{ height: `${Math.max(8, (t.value / maxTrend) * 82)}%` }} title={formatLakh(t.value)} />
              <span className="text-[11px] text-muted-foreground">{t.month}</span>
            </div>
          ))}
        </div>
        <div className="mt-3 text-[12px] text-muted-foreground">Average net cash flow: <span className="font-medium text-foreground">{formatLakh(f.net_cash_flow)}</span> · Trend: <span className="font-medium text-foreground">Stable</span></div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="rounded-lg border border-border bg-card p-5">
          <div className="flex items-center gap-2"><ShieldCheck className="h-4 w-4 text-emerald-600" strokeWidth={1.8} /><h3 className="text-[14px] font-semibold text-foreground">Positive Signals</h3></div>
          <div className="mt-3 space-y-2">
            {brain.positive_signals.length ? brain.positive_signals.map((s, i) => <Signal key={i} s={s} positive />) : <div className="text-[13px] text-muted-foreground">None material.</div>}
          </div>
        </div>
        <div className="rounded-lg border border-border bg-card p-5">
          <div className="flex items-center gap-2"><AlertTriangle className="h-4 w-4 text-amber-600" strokeWidth={1.8} /><h3 className="text-[14px] font-semibold text-foreground">Risk Signals</h3></div>
          <div className="mt-3 space-y-2">
            {brain.risk_signals.length ? brain.risk_signals.map((s, i) => <Signal key={i} s={s} positive={false} />) : <div className="text-[13px] text-muted-foreground">None material.</div>}
          </div>
        </div>
      </div>

      <EvidenceSheet item={evItem} onClose={() => setEvItem(null)} />
    </div>
  );
}
