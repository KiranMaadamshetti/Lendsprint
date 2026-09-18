import { useEffect, useState } from "react";
import { toast } from "sonner";
import { getCreditBrain, apiErrorMessage } from "@/lib/api";
import { formatINR, formatLakh } from "@/lib/format";
import { Skeleton } from "@/components/ui/skeleton";
import { TrendingUp, TrendingDown, ShieldCheck, AlertTriangle, Brain } from "lucide-react";

const SEV_DOT = { critical: "bg-red-500", review: "bg-amber-500", warning: "bg-amber-500", info: "bg-emerald-500" };

function Metric({ label, value }) {
  return (
    <div className="rounded-md border border-border bg-secondary/40 px-3 py-2">
      <div className="label-eyebrow">{label}</div>
      <div className="metric-num mt-1 text-[15px] font-semibold text-foreground">{value}</div>
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
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getCreditBrain(applicationId)
      .then((d) => setBrain(d.credit_brain))
      .catch((e) => toast.error(apiErrorMessage(e)))
      .finally(() => setLoading(false));
  }, [applicationId]);

  if (loading) return <div className="space-y-3"><Skeleton className="h-40 w-full" /><Skeleton className="h-64 w-full" /></div>;
  if (!brain) return null;

  const f = brain.financials;
  const maxTrend = Math.max(...brain.cash_flow_trend.map((t) => t.value), 1);

  return (
    <div className="space-y-4 animate-fade-up" data-testid="credit-brain-content">
      <div className="flex items-center gap-2 rounded-lg border border-border bg-card px-4 py-3">
        <Brain className="h-4 w-4 text-accent-foreground" strokeWidth={1.8} />
        <span className="text-[13px] text-muted-foreground">Credit Brain provides structured evidence only. It does not override the Credit Policy.</span>
      </div>

      <div className="rounded-lg border border-border bg-card p-5">
        <h3 className="text-[14px] font-semibold text-foreground">Financial Health</h3>
        <div className="mt-3 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
          <Metric label="Annual Turnover" value={formatINR(f.annual_turnover)} />
          <Metric label="Avg Monthly Credits" value={formatLakh(f.avg_monthly_credits)} />
          <Metric label="Avg Monthly Balance" value={formatLakh(f.avg_monthly_balance)} />
          <Metric label="Net Cash Flow" value={formatLakh(f.net_cash_flow)} />
          <Metric label="Existing EMI" value={formatINR(f.existing_emi)} />
          <Metric label="FOIR (pre-loan)" value={`${(f.foir_before * 100).toFixed(1)}%`} />
          <Metric label="DSCR" value={`${f.dscr}x`} />
          <Metric label="Banking History" value={`${f.banking_history_months} mo`} />
          <Metric label="Business Vintage" value={`${f.business_vintage_months} mo`} />
          <Metric label="CIBIL" value={f.cibil} />
          <Metric label="Cheque Bounces" value={f.cheque_bounces} />
          <Metric label="NACH Bounces" value={f.nach_bounces} />
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
    </div>
  );
}
