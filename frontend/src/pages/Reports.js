import { useEffect, useState } from "react";
import { toast } from "sonner";
import {
  PieChart, Pie, Cell, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid,
} from "recharts";
import { getReportsSummary, apiErrorMessage } from "@/lib/api";
import { Skeleton } from "@/components/ui/skeleton";
import { BarChart3, CheckCircle2, Gauge, Timer, RefreshCw } from "lucide-react";

const DECISION_COLORS = { approve: "#059669", review: "#d97706", reject: "#dc2626" };
const NAVY = "#1e2a52";
const INDIGO = "#4338ca";

function KpiCard({ icon: Icon, label, value }) {
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="flex items-center justify-between">
        <span className="label-eyebrow">{label}</span>
        <Icon className="h-4 w-4 text-muted-foreground/70" strokeWidth={1.8} />
      </div>
      <div className="metric-num mt-2 text-[28px] font-semibold leading-none text-foreground">{value}</div>
    </div>
  );
}

function Panel({ title, subtitle, children, testid }) {
  return (
    <div className="rounded-lg border border-border bg-card p-5" data-testid={testid}>
      <h3 className="text-[14px] font-semibold text-foreground">{title}</h3>
      {subtitle && <p className="mt-0.5 text-[12px] text-muted-foreground">{subtitle}</p>}
      <div className="mt-4">{children}</div>
    </div>
  );
}

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-md border border-border bg-card px-3 py-2 text-[12px] shadow-sm">
      {label && <div className="font-medium text-foreground">{label}</div>}
      {payload.map((p, i) => (
        <div key={i} className="tnum text-muted-foreground">
          {p.name}: <span className="font-medium text-foreground">{p.value}</span>
        </div>
      ))}
    </div>
  );
}

export default function Reports() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getReportsSummary()
      .then(setData)
      .catch((e) => toast.error(apiErrorMessage(e)))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-56" />
        <div className="grid grid-cols-4 gap-3">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-24" />)}</div>
        <Skeleton className="h-80 w-full" />
      </div>
    );
  }

  const t = data?.totals;
  const hasData = t && t.decisions > 0;

  return (
    <div className="animate-fade-up">
      <div>
        <h1 className="text-[24px] font-semibold tracking-tight text-foreground">Reports</h1>
        <p className="mt-0.5 text-[13px] text-muted-foreground">Portfolio approval, risk mix and turnaround across the loan book</p>
      </div>

      {!hasData ? (
        <div className="mt-10 flex flex-col items-center rounded-lg border border-border bg-card py-16 text-center" data-testid="reports-empty">
          <BarChart3 className="h-8 w-8 text-muted-foreground" strokeWidth={1.5} />
          <h3 className="mt-3 text-[15px] font-semibold text-foreground">No decision data yet</h3>
          <p className="mt-1 max-w-sm text-[13px] text-muted-foreground">
            Run decisions or load the sample portfolio from the Dashboard to populate portfolio reports.
          </p>
        </div>
      ) : (
        <>
          <div className="mt-5 grid grid-cols-2 xl:grid-cols-4 gap-3">
            <KpiCard icon={CheckCircle2} label="Approval Rate" value={`${t.approval_rate}%`} />
            <KpiCard icon={Gauge} label="Average PD" value={`${t.avg_pd}%`} />
            <KpiCard icon={Timer} label="Average TAT" value={`${t.avg_tat} min`} />
            <KpiCard icon={RefreshCw} label="Analyst Overrides" value={t.overrides} />
          </div>

          <div className="mt-4 grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Panel title="Decision Mix" subtitle="Distribution of credit decisions" testid="chart-decision-mix">
              <div className="flex items-center gap-6">
                <ResponsiveContainer width={200} height={200}>
                  <PieChart>
                    <Pie data={data.decision_mix} dataKey="value" nameKey="name" innerRadius={55} outerRadius={85} paddingAngle={2} stroke="none">
                      {data.decision_mix.map((e) => <Cell key={e.key} fill={DECISION_COLORS[e.key]} />)}
                    </Pie>
                    <Tooltip content={<ChartTooltip />} />
                  </PieChart>
                </ResponsiveContainer>
                <div className="space-y-2">
                  {data.decision_mix.map((e) => (
                    <div key={e.key} className="flex items-center gap-2 text-[13px]">
                      <span className="h-2.5 w-2.5 rounded-sm" style={{ background: DECISION_COLORS[e.key] }} />
                      <span className="text-muted-foreground w-16">{e.name}</span>
                      <span className="tnum font-medium text-foreground">{e.value}</span>
                    </div>
                  ))}
                </div>
              </div>
            </Panel>

            <Panel title="PD Distribution" subtitle="Applications by probability-of-default band" testid="chart-pd-distribution">
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={data.pd_distribution} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#eef0f5" vertical={false} />
                  <XAxis dataKey="bucket" tick={{ fontSize: 12, fill: "#6b7280" }} axisLine={false} tickLine={false} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 12, fill: "#6b7280" }} axisLine={false} tickLine={false} />
                  <Tooltip content={<ChartTooltip />} cursor={{ fill: "#f4f4f8" }} />
                  <Bar dataKey="count" name="Applications" fill={INDIGO} radius={[4, 4, 0, 0]} maxBarSize={48} />
                </BarChart>
              </ResponsiveContainer>
            </Panel>

            <Panel title="Approval Rate by Loan Type" subtitle="Share approved within each product" testid="chart-approval-type">
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={data.approval_by_type} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#eef0f5" vertical={false} />
                  <XAxis dataKey="type" tick={{ fontSize: 12, fill: "#6b7280" }} axisLine={false} tickLine={false} />
                  <YAxis unit="%" tick={{ fontSize: 12, fill: "#6b7280" }} axisLine={false} tickLine={false} />
                  <Tooltip content={<ChartTooltip />} cursor={{ fill: "#f4f4f8" }} />
                  <Bar dataKey="rate" name="Approval rate" fill="#059669" radius={[4, 4, 0, 0]} maxBarSize={48} />
                </BarChart>
              </ResponsiveContainer>
            </Panel>

            <Panel title="Average TAT by Loan Type" subtitle="Submission to decision (minutes)" testid="chart-tat-type">
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={data.tat_by_type} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#eef0f5" vertical={false} />
                  <XAxis dataKey="type" tick={{ fontSize: 12, fill: "#6b7280" }} axisLine={false} tickLine={false} />
                  <YAxis unit="m" tick={{ fontSize: 12, fill: "#6b7280" }} axisLine={false} tickLine={false} />
                  <Tooltip content={<ChartTooltip />} cursor={{ fill: "#f4f4f8" }} />
                  <Bar dataKey="avg_tat" name="Avg TAT" fill={NAVY} radius={[4, 4, 0, 0]} maxBarSize={48} />
                </BarChart>
              </ResponsiveContainer>
            </Panel>
          </div>
        </>
      )}
    </div>
  );
}
