import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription,
} from "@/components/ui/sheet";
import { FileText, FunctionSquare, Gauge, Link2 } from "lucide-react";

const kebab = (s) => String(s).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");

export function EvidenceMetric({ label, value, evidence, onOpen }) {
  const clickable = !!evidence;
  return (
    <button
      type="button"
      disabled={!clickable}
      onClick={() => clickable && onOpen({ ...evidence, value })}
      data-testid={`evidence-metric-${kebab(label)}`}
      className={`group w-full text-left rounded-md border px-3 py-2 transition-colors ${
        clickable
          ? "border-border bg-secondary/40 hover:border-accent-foreground/40 hover:bg-accent/40 cursor-pointer"
          : "border-border bg-secondary/40 cursor-default"
      }`}
    >
      <div className="flex items-center justify-between">
        <span className="label-eyebrow">{label}</span>
        {clickable && <Link2 className="h-3 w-3 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" strokeWidth={1.8} />}
      </div>
      <div className="metric-num mt-1 text-[15px] font-semibold text-foreground">{value}</div>
    </button>
  );
}

export function EvidenceSheet({ item, onClose }) {
  const open = !!item;
  const conf = item?.confidence != null ? Math.round(item.confidence * 100) : null;
  return (
    <Sheet open={open} onOpenChange={(o) => !o && onClose()}>
      <SheetContent className="w-full sm:max-w-md overflow-y-auto thin-scroll" data-testid="evidence-sheet">
        {item && (
          <>
            <SheetHeader>
              <SheetTitle className="text-[16px]">{item.label}</SheetTitle>
              <SheetDescription>Evidence chain — how this figure was derived and where it came from.</SheetDescription>
            </SheetHeader>

            <div className="mt-5 space-y-5">
              <div className="rounded-lg border border-border bg-secondary/40 px-4 py-3">
                <div className="label-eyebrow">Value</div>
                <div className="metric-num mt-1 text-[24px] font-semibold text-foreground" data-testid="evidence-value">{item.value}</div>
              </div>

              <div>
                <div className="flex items-center gap-2 text-[13px] font-semibold text-foreground">
                  <FunctionSquare className="h-4 w-4 text-accent-foreground" strokeWidth={1.8} /> Calculation
                </div>
                <div className="mt-2 rounded-md border border-border bg-card px-3 py-2.5">
                  <div className="text-[12px] text-muted-foreground">{item.formula}</div>
                  <div className="tnum mt-1.5 text-[13px] font-medium text-foreground">{item.calculation}</div>
                </div>
                {item.inputs?.length > 0 && (
                  <div className="mt-3 space-y-1.5">
                    {item.inputs.map((inp, i) => (
                      <div key={i} className="flex items-center justify-between border-b border-border/60 pb-1.5 last:border-0">
                        <span className="text-[12px] text-muted-foreground">{inp.label}</span>
                        <span className="tnum text-[13px] font-medium text-foreground">{inp.value}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div>
                <div className="flex items-center gap-2 text-[13px] font-semibold text-foreground">
                  <FileText className="h-4 w-4 text-accent-foreground" strokeWidth={1.8} /> Source Document
                </div>
                <div className="mt-2 flex items-center justify-between rounded-md border border-border bg-card px-3 py-2.5">
                  <div className="flex items-center gap-2 min-w-0">
                    <FileText className="h-4 w-4 shrink-0 text-muted-foreground/70" strokeWidth={1.8} />
                    <span className="text-[13px] font-medium text-foreground truncate" data-testid="evidence-source">{item.source}</span>
                  </div>
                  <span className="tnum shrink-0 rounded border border-border bg-secondary px-2 py-0.5 text-[11px] font-medium text-muted-foreground">{item.page}</span>
                </div>
              </div>

              {conf != null && (
                <div>
                  <div className="flex items-center gap-2 text-[13px] font-semibold text-foreground">
                    <Gauge className="h-4 w-4 text-accent-foreground" strokeWidth={1.8} /> Extraction Confidence
                  </div>
                  <div className="mt-2 flex items-center gap-3">
                    <div className="h-2 flex-1 rounded-full bg-secondary overflow-hidden">
                      <div className={`h-full rounded-full ${conf >= 95 ? "bg-emerald-500" : conf >= 90 ? "bg-accent-foreground/80" : "bg-amber-500"}`} style={{ width: `${conf}%` }} />
                    </div>
                    <span className="tnum text-[13px] font-semibold text-foreground" data-testid="evidence-confidence">{conf}%</span>
                  </div>
                </div>
              )}
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
