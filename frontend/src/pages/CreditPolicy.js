import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { getCreditPolicy, updateCreditPolicy, simulatePolicy, getPolicyVersions, apiErrorMessage } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { DecisionBadge } from "@/components/common/StatusBadge";
import { Save, FlaskConical, ScrollText, Loader2, Wand2, ShieldCheck } from "lucide-react";

const RULE_FIELDS = [
  ["max_foir", "Max FOIR", "0-1"],
  ["min_dscr", "Min DSCR", "x"],
  ["min_cibil", "Min CIBIL", "score"],
  ["min_vintage_months", "Min Vintage (mo)", "mo"],
  ["min_avg_credits", "Min Avg Credits (₹)", "inr"],
  ["min_annual_turnover", "Min Annual Turnover (₹)", "inr"],
  ["max_cheque_bounces", "Max Cheque Bounces", "count"],
];

export default function CreditPolicy() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const isAdmin = ["admin", "credit_manager"].includes(user?.role);
  const [policy, setPolicy] = useState(null);
  const [versions, setVersions] = useState([]);
  const [rules, setRules] = useState({});
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [sim, setSim] = useState({ max_foir: "", min_cibil: "", min_dscr: "", approve_pd_max: "" });
  const [simResult, setSimResult] = useState(null);
  const [simulating, setSimulating] = useState(false);

  const load = async () => {
    try {
      const [p, v] = await Promise.all([getCreditPolicy(), getPolicyVersions()]);
      setPolicy(p); setRules(p.rules); setVersions(v);
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const save = async () => {
    setSaving(true);
    try {
      const numeric = {};
      Object.entries(rules).forEach(([k, val]) => { numeric[k] = Number(val); });
      const updated = await updateCreditPolicy({ rules: numeric });
      toast.success(`Policy activated as ${updated.version}`);
      await load();
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setSaving(false); }
  };

  const runSim = async () => {
    setSimulating(true);
    try {
      const rulesOv = {}; const dm = {};
      if (sim.max_foir) rulesOv.max_foir = Number(sim.max_foir);
      if (sim.min_cibil) rulesOv.min_cibil = Number(sim.min_cibil);
      if (sim.min_dscr) rulesOv.min_dscr = Number(sim.min_dscr);
      if (sim.approve_pd_max) dm.approve_pd_max = Number(sim.approve_pd_max);
      const res = await simulatePolicy({ rules: rulesOv, decision_matrix: dm });
      setSimResult(res);
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setSimulating(false); }
  };

  if (loading) return <div className="space-y-4"><Skeleton className="h-8 w-56" /><Skeleton className="h-64 w-full" /></div>;

  return (
    <div className="animate-fade-up">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-[24px] font-semibold tracking-tight text-foreground">Credit Policy</h1>
          <p className="mt-0.5 text-[13px] text-muted-foreground">Configurable lending rules that power every decision</p>
        </div>
        {isAdmin && (
          <div className="flex items-center gap-2">
            <Button size="sm" variant="outline" onClick={() => navigate("/credit-policy/wizard")} data-testid="open-wizard-btn">
              <Wand2 className="mr-1.5 h-4 w-4" strokeWidth={1.8} />New policy (Wizard)
            </Button>
            <Button size="sm" onClick={save} disabled={saving} data-testid="save-policy-btn">
              {saving ? <><Loader2 className="mr-1.5 h-4 w-4 animate-spin" />Saving…</> : <><Save className="mr-1.5 h-4 w-4" strokeWidth={1.8} />Save &amp; Activate</>}
            </Button>
          </div>
        )}
      </div>

      {/* Policy header */}
      <div className="mt-5 rounded-lg border border-border bg-card p-5">
        <div className="flex items-center gap-2"><ScrollText className="h-4 w-4 text-accent-foreground" strokeWidth={1.8} /><h2 className="text-[15px] font-semibold text-foreground">{policy.policy_name}</h2></div>
        <div className="mt-3 grid grid-cols-2 sm:grid-cols-5 gap-3">
          {[["Version", policy.version], ["Status", policy.status], ["Product", policy.product_type], ["Effective", policy.effective_from], ["Created by", policy.created_by]].map(([k, v]) => (
            <div key={k}><div className="label-eyebrow">{k}</div><div className="mt-0.5 text-[13px] font-medium text-foreground capitalize">{v}</div></div>
          ))}
        </div>
      </div>

      <div className="mt-4 grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Financial rules */}
        <div className="lg:col-span-2 rounded-lg border border-border bg-card p-5">
          <h3 className="text-[14px] font-semibold text-foreground">Financial &amp; Eligibility Thresholds</h3>
          <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
            {RULE_FIELDS.map(([key, label]) => (
              <div key={key} className="space-y-1.5">
                <Label className="text-[12px]">{label}</Label>
                <Input className="tnum h-9" value={rules[key] ?? ""} disabled={!isAdmin}
                  onChange={(e) => setRules((r) => ({ ...r, [key]: e.target.value }))}
                  data-testid={`policy-${key}`} />
              </div>
            ))}
          </div>
          <div className="mt-5">
            <h4 className="text-[13px] font-semibold text-foreground">ROI &amp; Tenure Slabs</h4>
            <div className="mt-2 overflow-x-auto thin-scroll">
              <table className="w-full text-left">
                <thead><tr className="border-b border-border">{["Grade", "PD ≤", "ROI", "Max Tenure"].map((h) => <th key={h} className="label-eyebrow px-2 py-2">{h}</th>)}</tr></thead>
                <tbody>
                  {policy.roi_rules.map((s) => (
                    <tr key={s.grade} className="border-b border-border last:border-0">
                      <td className="px-2 py-2 text-[13px] font-medium text-foreground">{s.grade}</td>
                      <td className="px-2 py-2 tnum text-[13px] text-muted-foreground">{(s.pd_max * 100).toFixed(0)}%</td>
                      <td className="px-2 py-2 tnum text-[13px] text-foreground">{s.roi.toFixed(2)}%</td>
                      <td className="px-2 py-2 tnum text-[13px] text-muted-foreground">{policy.tenure_rules[s.grade]} mo</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Simulator */}
        <div className="rounded-lg border border-border bg-card p-5" data-testid="policy-simulator">
          <div className="flex items-center gap-2"><FlaskConical className="h-4 w-4 text-accent-foreground" strokeWidth={1.8} /><h3 className="text-[14px] font-semibold text-foreground">Policy Simulator</h3></div>
          <p className="mt-1 text-[12px] text-muted-foreground">Preview portfolio impact before activating. Nothing is saved.</p>
          <div className="mt-3 space-y-2.5">
            {[["max_foir", "Max FOIR (0-1)"], ["min_cibil", "Min CIBIL"], ["min_dscr", "Min DSCR"], ["approve_pd_max", "Approve PD max (0-1)"]].map(([k, l]) => (
              <div key={k} className="space-y-1"><Label className="text-[12px]">{l}</Label>
                <Input className="tnum h-9" value={sim[k]} placeholder="unchanged" onChange={(e) => setSim((s) => ({ ...s, [k]: e.target.value }))} data-testid={`sim-${k}`} /></div>
            ))}
          </div>
          <Button size="sm" variant="outline" className="mt-3 w-full" onClick={runSim} disabled={simulating} data-testid="simulate-btn">
            {simulating ? <><Loader2 className="mr-1.5 h-4 w-4 animate-spin" />Simulating…</> : "Simulate"}
          </Button>
          {simResult && (
            <div className="mt-4 space-y-3" data-testid="sim-result">
              <div className="grid grid-cols-2 gap-2 text-[12px]">
                {["current_mix", "proposed_mix"].map((m) => (
                  <div key={m} className="rounded-md border border-border bg-secondary/40 p-2">
                    <div className="label-eyebrow">{m === "current_mix" ? "Current" : "Proposed"}</div>
                    <div className="mt-1 tnum text-foreground">A {simResult[m].approve} · R {simResult[m].review} · X {simResult[m].reject}</div>
                  </div>
                ))}
              </div>
              {simResult.changes.length > 0 ? simResult.changes.map((c) => (
                <div key={c.reference} className="flex items-center justify-between rounded-md border border-border px-2.5 py-1.5 text-[12px]">
                  <span className="truncate text-foreground">{c.borrower}</span>
                  <span className="flex items-center gap-1"><DecisionBadge decision={c.from} /> → <DecisionBadge decision={c.to} /></span>
                </div>
              )) : <div className="text-[12px] text-muted-foreground">No decision changes under the proposed thresholds.</div>}
            </div>
          )}
        </div>
      </div>

      {/* Approval authority */}
      <div className="mt-4 rounded-lg border border-border bg-card p-5" data-testid="approval-authority">
        <div className="flex items-center gap-2"><ShieldCheck className="h-4 w-4 text-accent-foreground" strokeWidth={1.8} /><h3 className="text-[14px] font-semibold text-foreground">Approval Authority &amp; Escalation</h3></div>
        <p className="mt-0.5 text-[12px] text-muted-foreground">Recommended amounts above a role's limit require escalation before approval.</p>
        <div className="mt-3 overflow-x-auto thin-scroll">
          <table className="w-full min-w-[420px] text-left">
            <thead><tr className="border-b border-border">{["Role", "From", "Up to"].map((h) => <th key={h} className="label-eyebrow px-3 py-2">{h}</th>)}</tr></thead>
            <tbody>
              {(policy.approval_authority || []).map((a) => (
                <tr key={a.role} className="border-b border-border last:border-0">
                  <td className="px-3 py-2 text-[13px] font-medium text-foreground">{a.label || a.role}</td>
                  <td className="px-3 py-2 tnum text-[13px] text-muted-foreground">₹{Number(a.min).toLocaleString("en-IN")}</td>
                  <td className="px-3 py-2 tnum text-[13px] text-foreground">₹{Number(a.max).toLocaleString("en-IN")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Version history */}
      <div className="mt-4 rounded-lg border border-border bg-card">
        <div className="border-b border-border px-4 py-3"><h3 className="text-[14px] font-semibold text-foreground">Version History</h3></div>
        <div className="overflow-x-auto thin-scroll">
          <table className="w-full min-w-[520px] text-left">
            <thead><tr className="border-b border-border">{["Version", "Status", "Created By", "Effective", "Created"].map((h) => <th key={h} className="label-eyebrow px-4 py-2.5">{h}</th>)}</tr></thead>
            <tbody>
              {versions.map((v) => (
                <tr key={v.id} className="border-b border-border last:border-0">
                  <td className="px-4 py-2.5 tnum text-[13px] font-medium text-foreground">{v.version}</td>
                  <td className="px-4 py-2.5"><span className={`rounded-md border px-2 py-0.5 text-[11px] font-medium ${v.status === "active" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-50 text-slate-600 border-slate-200"}`}>{v.status}</span></td>
                  <td className="px-4 py-2.5 text-[13px] text-muted-foreground">{v.created_by}</td>
                  <td className="px-4 py-2.5 text-[13px] text-muted-foreground">{v.effective_from}</td>
                  <td className="px-4 py-2.5 text-[13px] text-muted-foreground">{new Date(v.created_at).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" })}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
