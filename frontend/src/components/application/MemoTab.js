import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { formatINR, LOAN_TYPE_LABEL } from "@/lib/format";
import { Copy, Check, FileText } from "lucide-react";

export function MemoTab({ application, decision, onRun }) {
  const [copied, setCopied] = useState(false);

  if (!decision) {
    return (
      <div className="rounded-lg border border-border bg-card p-12 text-center" data-testid="memo-empty">
        <FileText className="mx-auto h-8 w-8 text-muted-foreground" strokeWidth={1.5} />
        <h3 className="mt-3 text-[15px] font-semibold text-foreground">No credit memo yet</h3>
        <p className="mx-auto mt-1 max-w-sm text-[13px] text-muted-foreground">
          Run the decision engine to generate an AI-drafted credit memo from the application documents.
        </p>
        <Button className="mt-5" onClick={onRun}>Run Decision</Button>
      </div>
    );
  }

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(decision.memo_text);
      setCopied(true);
      toast.success("Copied to clipboard");
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error("Unable to copy memo");
    }
  };

  const facts = [
    ["Borrower", application.borrower_name],
    ["Loan Type", LOAN_TYPE_LABEL[application.loan_type]],
    ["Requested Amount", formatINR(application.loan_amount)],
    ["Decision", decision.decision.toUpperCase()],
    ["PD Score", `${(decision.pd_score * 100).toFixed(1)}%`],
  ];

  return (
    <div className="rounded-lg border border-border bg-card animate-fade-up" data-testid="memo-content">
      <div className="flex items-start justify-between gap-4 border-b border-border px-6 py-4">
        <div>
          <h3 className="text-[15px] font-semibold text-foreground">AI-Drafted Credit Memo</h3>
          <p className="mt-0.5 text-[12px] text-muted-foreground">Generated from application documents and decision signals.</p>
        </div>
        <Button size="sm" variant="outline" onClick={copy} data-testid="copy-memo-btn">
          {copied ? <><Check className="mr-1.5 h-4 w-4 text-emerald-600" />Copied</> : <><Copy className="mr-1.5 h-4 w-4" strokeWidth={1.8} />Copy Memo</>}
        </Button>
      </div>

      <div className="px-6 py-5">
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 rounded-md border border-border bg-secondary/40 px-4 py-3">
          {facts.map(([k, v]) => (
            <div key={k}>
              <div className="label-eyebrow">{k}</div>
              <div className="mt-0.5 text-[13px] font-medium text-foreground truncate">{v}</div>
            </div>
          ))}
        </div>

        <article className="mt-6 max-w-3xl space-y-4 text-[14px] leading-relaxed text-foreground/90">
          {decision.memo_text.split("\n\n").map((para, i) => (
            <p key={i}>{para}</p>
          ))}
        </article>

        <div className="mt-6 border-t border-border pt-3 text-[11px] text-muted-foreground">
          AI-generated draft. Subject to credit policy and analyst review.
        </div>
      </div>
    </div>
  );
}
