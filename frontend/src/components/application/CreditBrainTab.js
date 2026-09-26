import { useEffect, useState } from "react";
import { toast } from "sonner";
import { getCreditBrain, apiErrorMessage } from "@/lib/api";
import { formatINR, formatLakh } from "@/lib/format";
import { Skeleton } from "@/components/ui/skeleton";
import { TrendingUp, TrendingDown, ShieldCheck, AlertTriangle, Brain, GitCompareArrows, FileCheck2, FileX2, CheckCircle2, Landmark, Banknote, AlertOctagon, ArrowDownRight, ArrowUpRight, Radar, CalendarDays } from "lucide-react";
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

const BAND_STYLE = {
  Low: { text: "text-emerald-700", bg: "bg-emerald-50", ring: "border-emerald-200" },
  Moderate: { text: "text-amber-700", bg: "bg-amber-50", ring: "border-amber-200" },
  High: { text: "text-red-700", bg: "bg-red-50", ring: "border-red-200" },
};
const barColor = (s) => (s >= 70 ? "bg-emerald-500" : s >= 45 ? "bg-amber-500" : "bg-red-500");
const RATING_STYLE = {
  excellent: "bg-emerald-100 text-emerald-800",
  good: "bg-emerald-50 text-emerald-700",
  average: "bg-amber-50 text-amber-700",
  review: "bg-amber-100 text-amber-800",
  critical: "bg-red-100 text-red-700",
};

function RiskRadar({ radar }) {
  const st = BAND_STYLE[radar.band] || BAND_STYLE.Moderate;
  return (
    <div className={`rounded-lg border ${st.ring} ${st.bg} p-5`} data-testid="risk-radar">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2"><Radar className={`h-4 w-4 ${st.text}`} strokeWidth={1.8} /><h3 className="text-[14px] font-semibold text-foreground">Risk Radar</h3></div>
        <span className={`rounded-full px-2.5 py-1 text-[12px] font-semibold ${st.text}`} data-testid="risk-radar-band">{radar.band} Risk</span>
      </div>
      <div className="mt-3 flex items-center gap-5">
        <div className="shrink-0 text-center">
          <div className={`metric-num text-[34px] font-bold leading-none ${st.text}`} data-testid="risk-radar-score">{radar.overall}</div>
          <div className="label-eyebrow mt-1">/ 100</div>
        </div>
        <div className="flex-1 space-y-2">
          {radar.factors.map((fac) => (
            <div key={fac.label} className="flex items-center gap-3">
              <span className="w-[120px] shrink-0 text-[12px] text-muted-foreground">{fac.label}</span>
              <div className="flex-1 h-2 rounded-full bg-white/70 overflow-hidden"><div className={`h-full rounded-full ${barColor(fac.score)}`} style={{ width: `${fac.score}%` }} /></div>
              <span className="tnum w-[34px] text-right text-[12px] font-medium text-foreground">{fac.score}</span>
              <span className="hidden sm:block w-[120px] text-[11px] text-muted-foreground truncate">{fac.note}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function MonthTable({ rows }) {
  return (
    <div className="mt-4">
      <div className="flex items-center gap-1.5 label-eyebrow mb-1.5"><CalendarDays className="h-3.5 w-3.5 text-accent-foreground" strokeWidth={2} />Month-wise Summary</div>
      <div className="overflow-x-auto">
        <table className="w-full text-[12px]" data-testid="monthly-breakdown">
          <thead>
            <tr className="border-b border-border text-left text-muted-foreground">
              <th className="py-2 pr-3 font-medium">Month</th>
              <th className="py-2 pr-3 font-medium text-right">Credits</th>
              <th className="py-2 pr-3 font-medium text-right">Debits</th>
              <th className="py-2 pr-3 font-medium text-right">Closing Balance</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className="border-b border-border/60" data-testid={`month-row-${i}`}>
                <td className="py-2 pr-3 font-medium text-foreground">{r.month}</td>
                <td className="tnum py-2 pr-3 text-right text-emerald-700">{r.credits != null ? formatLakh(r.credits) : "—"}</td>
                <td className="tnum py-2 pr-3 text-right text-red-600">{r.debits != null ? formatLakh(r.debits) : "—"}</td>
                <td className="tnum py-2 pr-3 text-right text-foreground">{r.closing_balance != null ? formatLakh(r.closing_balance) : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
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
  const cibil = brain.cibil_report;
  const cibilRating = brain.cibil_rating;
  const banking = brain.banking_analysis;
  const maxTrend = Math.max(...brain.cash_flow_trend.map((t) => t.value), 1);

  return (
    <div className="space-y-4 animate-fade-up" data-testid="credit-brain-content">
      <div className="flex items-center justify-between gap-3 rounded-lg border border-border bg-card px-4 py-3">
        <div className="flex items-center gap-2">
          <Brain className="h-4 w-4 text-accent-foreground" strokeWidth={1.8} />
          <span className="text-[13px] text-muted-foreground">Credit Brain provides structured evidence only. Click any figure to trace its source, page and calculation.</span>
        </div>
        {brain.extraction_source === "ai" ? (
          <span className="shrink-0 rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] font-semibold text-emerald-700" data-testid="extraction-badge">
            AI-extracted from documents{brain.extraction_confidence != null ? ` · ${Math.round(brain.extraction_confidence * 100)}% confidence` : ""}
          </span>
        ) : (
          <span className="shrink-0 rounded-full bg-secondary px-2.5 py-1 text-[11px] font-medium text-muted-foreground" data-testid="extraction-badge">
            Estimated · no parsed documents
          </span>
        )}
      </div>

      {brain.risk_radar && <RiskRadar radar={brain.risk_radar} />}

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

      {cibil && (
        <div className="rounded-lg border border-border bg-card p-5" data-testid="cibil-report">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Landmark className="h-4 w-4 text-accent-foreground" strokeWidth={1.8} />
              <h3 className="text-[14px] font-semibold text-foreground">Credit Bureau (CIBIL) Analysis</h3>
            </div>
            <div className="flex items-center gap-2">
              {cibilRating && (
                <span className={`rounded-full px-2.5 py-1 text-[12px] font-semibold ${RATING_STYLE[cibilRating.severity] || "bg-secondary text-muted-foreground"}`} data-testid="cibil-rating">
                  {cibilRating.rating}
                </span>
              )}
              <span className={`tnum rounded-full px-2.5 py-1 text-[12px] font-semibold ${(cibil.score || 0) >= 730 ? "bg-emerald-50 text-emerald-700" : (cibil.score || 0) >= 680 ? "bg-amber-50 text-amber-700" : "bg-red-50 text-red-600"}`} data-testid="cibil-score">
                Score {cibil.score ?? "—"}
              </span>
            </div>
          </div>
          {(cibilRating?.reason || cibil.summary) && <p className="mt-1.5 text-[12px] text-muted-foreground">{cibilRating?.reason || cibil.summary}</p>}
          <div className="mt-3 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <div className="rounded-md border border-border bg-secondary/40 px-3 py-2"><div className="label-eyebrow">Active Loans</div><div className="metric-num mt-1 text-[15px] font-semibold text-foreground">{cibil.total_active_loans ?? "—"}</div></div>
            <div className="rounded-md border border-border bg-secondary/40 px-3 py-2"><div className="label-eyebrow">Sanctioned</div><div className="metric-num mt-1 text-[15px] font-semibold text-foreground">{cibil.total_sanctioned != null ? formatLakh(cibil.total_sanctioned) : "—"}</div></div>
            <div className="rounded-md border border-border bg-secondary/40 px-3 py-2"><div className="label-eyebrow">Outstanding</div><div className="metric-num mt-1 text-[15px] font-semibold text-foreground">{cibil.total_outstanding != null ? formatLakh(cibil.total_outstanding) : "—"}</div></div>
            <div className={`rounded-md border px-3 py-2 ${(cibil.total_overdue || 0) > 0 ? "border-red-200 bg-red-50" : "border-border bg-secondary/40"}`}><div className="label-eyebrow">Overdue</div><div className={`metric-num mt-1 text-[15px] font-semibold ${(cibil.total_overdue || 0) > 0 ? "text-red-600" : "text-foreground"}`}>{cibil.total_overdue != null ? formatLakh(cibil.total_overdue) : "—"}</div></div>
            <div className={`rounded-md border px-3 py-2 ${(cibil.max_dpd || 0) >= 30 ? "border-red-200 bg-red-50" : "border-border bg-secondary/40"}`}><div className="label-eyebrow">Max DPD</div><div className={`metric-num mt-1 text-[15px] font-semibold ${(cibil.max_dpd || 0) >= 30 ? "text-red-600" : "text-foreground"}`}>{cibil.max_dpd != null ? `${cibil.max_dpd}d` : "—"}</div></div>
            <div className="rounded-md border border-border bg-secondary/40 px-3 py-2"><div className="label-eyebrow">Enquiries (6m)</div><div className="metric-num mt-1 text-[15px] font-semibold text-foreground">{cibil.enquiries_6m ?? "—"}</div></div>
          </div>
          {Array.isArray(cibil.tradelines) && cibil.tradelines.length > 0 && (
            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-[12px]" data-testid="cibil-tradelines">
                <thead>
                  <tr className="border-b border-border text-left text-muted-foreground">
                    <th className="py-2 pr-3 font-medium">Lender</th>
                    <th className="py-2 pr-3 font-medium">Type</th>
                    <th className="py-2 pr-3 font-medium text-right">Sanctioned</th>
                    <th className="py-2 pr-3 font-medium text-right">Outstanding</th>
                    <th className="py-2 pr-3 font-medium text-right">EMI</th>
                    <th className="py-2 pr-3 font-medium text-right">DPD</th>
                    <th className="py-2 pr-3 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {cibil.tradelines.map((t, i) => (
                    <tr key={i} className="border-b border-border/60" data-testid={`tradeline-${i}`}>
                      <td className="py-2 pr-3 font-medium text-foreground">{t.lender}</td>
                      <td className="py-2 pr-3 text-muted-foreground">{t.loan_type}</td>
                      <td className="tnum py-2 pr-3 text-right text-foreground">{t.sanctioned != null ? formatLakh(t.sanctioned) : "—"}</td>
                      <td className="tnum py-2 pr-3 text-right text-foreground">{t.outstanding != null ? formatLakh(t.outstanding) : "—"}</td>
                      <td className="tnum py-2 pr-3 text-right text-foreground">{t.emi != null ? formatINR(t.emi) : "—"}</td>
                      <td className={`tnum py-2 pr-3 text-right font-semibold ${(t.dpd || 0) >= 30 ? "text-red-600" : (t.dpd || 0) > 0 ? "text-amber-600" : "text-emerald-600"}`}>{t.dpd != null ? `${t.dpd}d` : "0d"}</td>
                      <td className="py-2 pr-3"><span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${/(overdue|default|npa)/i.test(t.status || "") ? "bg-red-100 text-red-700" : /closed/i.test(t.status || "") ? "bg-secondary text-muted-foreground" : "bg-emerald-100 text-emerald-700"}`}>{t.status || "Active"}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {banking && (
        <div className="rounded-lg border border-border bg-card p-5" data-testid="banking-analysis">
          <div className="flex items-center gap-2">
            <Banknote className="h-4 w-4 text-accent-foreground" strokeWidth={1.8} />
            <h3 className="text-[14px] font-semibold text-foreground">Bank Statement Analysis</h3>
          </div>
          {banking.cash_flow_pattern && <p className="mt-1.5 text-[12px] text-muted-foreground">{banking.cash_flow_pattern}</p>}
          <div className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="rounded-md border border-border bg-secondary/40 px-3 py-2"><div className="label-eyebrow">Avg Balance</div><div className="metric-num mt-1 text-[15px] font-semibold text-foreground">{banking.avg_monthly_balance != null ? formatLakh(banking.avg_monthly_balance) : "—"}</div></div>
            <div className="rounded-md border border-border bg-secondary/40 px-3 py-2"><div className="label-eyebrow">EMIs / month</div><div className="metric-num mt-1 text-[15px] font-semibold text-foreground">{banking.total_emi_count ?? "—"}</div></div>
            <div className="rounded-md border border-border bg-secondary/40 px-3 py-2"><div className="label-eyebrow">EMI Outflow</div><div className="metric-num mt-1 text-[15px] font-semibold text-foreground">{banking.total_emi_outflow != null ? formatINR(banking.total_emi_outflow) : "—"}</div></div>
            <div className="rounded-md border border-border bg-secondary/40 px-3 py-2"><div className="label-eyebrow">Inflow / Outflow</div><div className="metric-num mt-1 text-[15px] font-semibold text-foreground">{banking.inflow_outflow_ratio != null ? `${Number(banking.inflow_outflow_ratio).toFixed(2)}x` : "—"}</div></div>
          </div>

          {Array.isArray(banking.monthly_breakdown) && banking.monthly_breakdown.length > 0 && (
            <MonthTable rows={banking.monthly_breakdown} />
          )}

          {Array.isArray(banking.emis) && banking.emis.length > 0 && (
            <div className="mt-4">
              <div className="label-eyebrow mb-1.5">EMIs / Loan Instalments Detected</div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {banking.emis.map((e, i) => (
                  <div key={i} className="flex items-center justify-between rounded-md border border-border px-3 py-1.5" data-testid={`emi-row-${i}`}>
                    <span className="text-[12px] text-foreground truncate">{e.beneficiary}</span>
                    <span className="tnum text-[12px] font-medium text-foreground">{formatINR(e.amount)}<span className="ml-1 text-[10px] text-muted-foreground">/{e.frequency || "mo"}</span></span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="mt-4 grid grid-cols-1 lg:grid-cols-2 gap-4">
            {Array.isArray(banking.top_credit_sources) && banking.top_credit_sources.length > 0 && (
              <div>
                <div className="flex items-center gap-1.5 label-eyebrow mb-1.5"><ArrowUpRight className="h-3.5 w-3.5 text-emerald-600" strokeWidth={2} />Top Credit Sources (money in)</div>
                <div className="space-y-1.5">
                  {banking.top_credit_sources.map((c, i) => (
                    <div key={i} className="flex items-center justify-between rounded-md border border-border px-3 py-1.5">
                      <span className="text-[12px] text-foreground truncate">{c.party}{c.txn_count ? <span className="ml-1 text-[10px] text-muted-foreground">×{c.txn_count}</span> : null}</span>
                      <span className="tnum text-[12px] font-medium text-emerald-700">{formatLakh(c.total_amount)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {Array.isArray(banking.top_debit_destinations) && banking.top_debit_destinations.length > 0 && (
              <div>
                <div className="flex items-center gap-1.5 label-eyebrow mb-1.5"><ArrowDownRight className="h-3.5 w-3.5 text-red-500" strokeWidth={2} />Top Debit Destinations (money out)</div>
                <div className="space-y-1.5">
                  {banking.top_debit_destinations.map((c, i) => (
                    <div key={i} className="flex items-center justify-between rounded-md border border-border px-3 py-1.5">
                      <span className="text-[12px] text-foreground truncate">{c.party}{c.txn_count ? <span className="ml-1 text-[10px] text-muted-foreground">×{c.txn_count}</span> : null}</span>
                      <span className="tnum text-[12px] font-medium text-red-600">{formatLakh(c.total_amount)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="mt-4">
            <div className="flex items-center gap-1.5 label-eyebrow mb-1.5"><AlertOctagon className="h-3.5 w-3.5 text-red-500" strokeWidth={2} />Anomalous / Red-Flag Transactions</div>
            {Array.isArray(banking.anomalies) && banking.anomalies.length > 0 ? (
              <div className="space-y-2">
                {banking.anomalies.map((a, i) => {
                  const st = CONTRA_STYLE[(a.severity || "review").toLowerCase()] || CONTRA_STYLE.review;
                  return (
                    <div key={i} className={`rounded-md border ${st.border} ${st.bg} px-3 py-2.5`} data-testid={`anomaly-${i}`}>
                      <div className="flex items-center justify-between gap-2">
                        <div className={`text-[13px] font-semibold ${st.text}`}>{a.type}</div>
                        <div className="flex items-center gap-2">
                          {a.amount != null && <span className="tnum text-[12px] font-medium text-foreground">{formatLakh(a.amount)}</span>}
                          <span className={`rounded px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${st.chip}`}>{a.severity || "review"}</span>
                        </div>
                      </div>
                      <div className="mt-1 text-[12px] text-foreground/80">{a.description}</div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="flex items-center gap-2 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2.5" data-testid="no-anomalies">
                <CheckCircle2 className="h-4 w-4 text-emerald-600" strokeWidth={1.8} />
                <span className="text-[13px] text-emerald-800">No anomalous or high-risk transactions detected in the bank statement.</span>
              </div>
            )}
          </div>
        </div>
      )}

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
