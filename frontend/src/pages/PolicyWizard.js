import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { getCreditPolicy, updateCreditPolicy, apiErrorMessage } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Check, ArrowLeft, ArrowRight, Loader2, Wand2 } from "lucide-react";

const STEPS = [
  "Product", "Borrower Eligibility", "Financial Thresholds", "Banking Rules", "Bureau Rules",
  "Loan Amount", "ROI Slabs", "Tenure", "Decision Matrix", "Review & Activate",
];

export default function PolicyWizard() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const isAdmin = ["admin", "credit_manager"].includes(user?.role);
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [f, setF] = useState(null);

  useEffect(() => {
    getCreditPolicy().then((p) => {
      setF({
        policy_name: p.policy_name, product_type: p.product_type,
        min_vintage_months: p.rules.min_vintage_months, min_cibil: p.rules.min_cibil,
        max_foir: p.rules.max_foir, min_dscr: p.rules.min_dscr, min_net_cashflow: p.rules.min_net_cashflow,
        min_avg_credits: p.rules.min_avg_credits, min_annual_turnover: p.rules.min_annual_turnover,
        max_cheque_bounces: p.rules.max_cheque_bounces,
        absolute_max: p.loan_amount_rules.absolute_max, turnover_multiple: p.loan_amount_rules.turnover_multiple,
        collateral_coverage: p.loan_amount_rules.collateral_coverage,
        roi_rules: p.roi_rules, tenure_rules: p.tenure_rules,
        approve_pd_max: p.decision_matrix.approve_pd_max, review_pd_max: p.decision_matrix.review_pd_max,
      });
    }).catch((e) => toast.error(apiErrorMessage(e))).finally(() => setLoading(false));
  }, []);

  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));
  const setRoi = (i, key, v) => setF((p) => ({ ...p, roi_rules: p.roi_rules.map((r, idx) => idx === i ? { ...r, [key]: Number(v) } : r) }));
  const setTenure = (g, v) => setF((p) => ({ ...p, tenure_rules: { ...p.tenure_rules, [g]: Number(v) } }));

  const activate = async () => {
    setSaving(true);
    try {
      const payload = {
        policy_name: f.policy_name, product_type: f.product_type,
        rules: {
          min_vintage_months: Number(f.min_vintage_months), min_cibil: Number(f.min_cibil),
          max_foir: Number(f.max_foir), min_dscr: Number(f.min_dscr), min_net_cashflow: Number(f.min_net_cashflow),
          min_avg_credits: Number(f.min_avg_credits), min_annual_turnover: Number(f.min_annual_turnover),
          max_cheque_bounces: Number(f.max_cheque_bounces),
        },
        loan_amount_rules: { absolute_max: Number(f.absolute_max), turnover_multiple: Number(f.turnover_multiple), collateral_coverage: Number(f.collateral_coverage) },
        roi_rules: f.roi_rules, tenure_rules: f.tenure_rules,
        decision_matrix: { approve_pd_max: Number(f.approve_pd_max), review_pd_max: Number(f.review_pd_max) },
      };
      const updated = await updateCreditPolicy(payload);
      toast.success(`Policy configured and activated as ${updated.version}`);
      navigate("/credit-policy");
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setSaving(false); }
  };

  if (loading || !f) return <div className="space-y-4"><Skeleton className="h-8 w-56" /><Skeleton className="h-80 w-full" /></div>;

  const Field = ({ k, label, step: st = "any" }) => (
    <div className="space-y-1.5"><Label className="text-[12px]">{label}</Label>
      <Input className="tnum h-9" type="number" step={st} value={f[k]} onChange={(e) => set(k, e.target.value)} data-testid={`wiz-${k}`} /></div>
  );

  return (
    <div className="animate-fade-up">
      <button onClick={() => navigate("/credit-policy")} className="inline-flex items-center gap-1.5 text-[13px] text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" strokeWidth={1.8} /> Credit Policy
      </button>
      <div className="mt-3 flex items-center gap-2">
        <Wand2 className="h-5 w-5 text-accent-foreground" strokeWidth={1.8} />
        <h1 className="text-[24px] font-semibold tracking-tight text-foreground">Policy Configuration Wizard</h1>
      </div>
      <p className="mt-0.5 text-[13px] text-muted-foreground">Configure the full credit policy in ten guided steps. Activating creates a new version.</p>

      {/* Stepper */}
      <div className="mt-5 flex flex-wrap gap-1.5">
        {STEPS.map((s, i) => (
          <button key={s} onClick={() => setStep(i)} className={`flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-[12px] transition-colors ${i === step ? "border-primary bg-primary text-primary-foreground" : i < step ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-border bg-card text-muted-foreground"}`} data-testid={`wiz-step-${i}`}>
            <span className="tnum">{i < step ? <Check className="h-3.5 w-3.5" /> : i + 1}</span>{s}
          </button>
        ))}
      </div>

      <div className="mt-4 rounded-lg border border-border bg-card p-5 min-h-[280px]">
        <h2 className="text-[15px] font-semibold text-foreground">{step + 1}. {STEPS[step]}</h2>
        <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {step === 0 && (<><Field k="policy_name" label="Policy Name" /><Field k="product_type" label="Product Type" /></>)}
          {step === 1 && (<><Field k="min_vintage_months" label="Min Business Vintage (months)" /></>)}
          {step === 2 && (<><Field k="max_foir" label="Max FOIR (0-1)" /><Field k="min_dscr" label="Min DSCR" /><Field k="min_net_cashflow" label="Min Net Cash Flow (₹)" /><Field k="min_annual_turnover" label="Min Annual Turnover (₹)" /></>)}
          {step === 3 && (<><Field k="min_avg_credits" label="Min Avg Monthly Credits (₹)" /><Field k="max_cheque_bounces" label="Max Cheque Bounces" /></>)}
          {step === 4 && (<><Field k="min_cibil" label="Min CIBIL Score" /></>)}
          {step === 5 && (<><Field k="absolute_max" label="Absolute Max Loan (₹)" /><Field k="turnover_multiple" label="Turnover Multiple" /><Field k="collateral_coverage" label="Collateral Coverage (x)" /></>)}
          {step === 6 && (
            <div className="sm:col-span-2 lg:col-span-3">
              <table className="w-full text-left"><thead><tr className="border-b border-border">{["Grade", "PD ≤ (0-1)", "ROI %"].map((h) => <th key={h} className="label-eyebrow px-2 py-2">{h}</th>)}</tr></thead>
                <tbody>{f.roi_rules.map((r, i) => (
                  <tr key={r.grade} className="border-b border-border last:border-0">
                    <td className="px-2 py-2 text-[13px] font-medium">{r.grade}</td>
                    <td className="px-2 py-2"><Input className="tnum h-8 w-28" type="number" step="0.01" value={r.pd_max} onChange={(e) => setRoi(i, "pd_max", e.target.value)} /></td>
                    <td className="px-2 py-2"><Input className="tnum h-8 w-28" type="number" step="0.1" value={r.roi} onChange={(e) => setRoi(i, "roi", e.target.value)} /></td>
                  </tr>))}</tbody></table>
            </div>
          )}
          {step === 7 && Object.keys(f.tenure_rules).map((g) => (
            <div key={g} className="space-y-1.5"><Label className="text-[12px]">Grade {g} max tenure (months)</Label>
              <Input className="tnum h-9" type="number" value={f.tenure_rules[g]} onChange={(e) => setTenure(g, e.target.value)} /></div>
          ))}
          {step === 8 && (<><Field k="approve_pd_max" label="Approve if PD ≤ (0-1)" /><Field k="review_pd_max" label="Review if PD ≤ (0-1)" /></>)}
          {step === 9 && (
            <div className="sm:col-span-2 lg:col-span-3 text-[13px] text-muted-foreground">
              <p>Review the configuration, then activate. This creates a new policy version and applies to all new decisions. Historical decisions retain their original policy version.</p>
              <div className="mt-3 grid grid-cols-2 sm:grid-cols-3 gap-2">
                {[["Policy", f.policy_name], ["Max FOIR", f.max_foir], ["Min DSCR", f.min_dscr], ["Min CIBIL", f.min_cibil], ["Min Vintage", `${f.min_vintage_months} mo`], ["Absolute Max", `₹${Number(f.absolute_max).toLocaleString("en-IN")}`], ["Approve PD ≤", f.approve_pd_max], ["Review PD ≤", f.review_pd_max]].map(([k, v]) => (
                  <div key={k} className="rounded-md border border-border bg-secondary/40 px-3 py-2"><div className="label-eyebrow">{k}</div><div className="mt-0.5 tnum text-foreground">{v}</div></div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="mt-4 flex items-center justify-between">
        <Button variant="outline" size="sm" disabled={step === 0} onClick={() => setStep((s) => s - 1)}><ArrowLeft className="mr-1.5 h-4 w-4" />Back</Button>
        {step < STEPS.length - 1 ? (
          <Button size="sm" onClick={() => setStep((s) => s + 1)} data-testid="wiz-next">Next<ArrowRight className="ml-1.5 h-4 w-4" /></Button>
        ) : (
          <Button size="sm" onClick={activate} disabled={saving || !isAdmin} data-testid="wiz-activate">
            {saving ? <><Loader2 className="mr-1.5 h-4 w-4 animate-spin" />Activating…</> : "Activate Policy"}
          </Button>
        )}
      </div>
      {!isAdmin && step === STEPS.length - 1 && <p className="mt-2 text-right text-[12px] text-amber-700">Only administrators can activate a policy.</p>}
    </div>
  );
}
