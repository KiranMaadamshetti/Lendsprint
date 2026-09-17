import { useState } from "react";
import { formatDateTime } from "@/lib/format";
import { ChevronRight, Cpu, User, Settings2 } from "lucide-react";

const ACTOR_ICON = { "Decision Engine": Cpu, System: Settings2 };

function AuditRow({ event }) {
  const [open, setOpen] = useState(false);
  const Icon = ACTOR_ICON[event.actor] || User;
  const hasPayload = event.payload && Object.keys(event.payload).length > 0;
  return (
    <div className="border-b border-border last:border-0">
      <button
        onClick={() => hasPayload && setOpen((o) => !o)}
        className={`flex w-full items-start gap-3 px-4 py-3 text-left transition-colors ${hasPayload ? "hover:bg-secondary/40 cursor-pointer" : "cursor-default"}`}
        data-testid={`audit-row-${event.id}`}
      >
        <div className="mt-0.5">
          {hasPayload ? (
            <ChevronRight className={`h-4 w-4 text-muted-foreground transition-transform ${open ? "rotate-90" : ""}`} strokeWidth={2} />
          ) : (
            <span className="inline-block h-4 w-4" />
          )}
        </div>
        <div className="tnum w-[150px] shrink-0 text-[12px] text-muted-foreground">{formatDateTime(event.created_at)}</div>
        <div className="min-w-0 flex-1">
          <div className="text-[13px] font-medium text-foreground">{event.event}</div>
        </div>
        <div className="flex shrink-0 items-center gap-1.5 text-[12px] text-muted-foreground">
          <Icon className="h-3.5 w-3.5" strokeWidth={1.8} />
          {event.actor}
        </div>
      </button>
      {open && hasPayload && (
        <div className="px-4 pb-3 pl-[52px]">
          <pre className="tnum overflow-x-auto thin-scroll rounded-md border border-border bg-slate-50 px-3 py-2.5 text-[12px] leading-relaxed text-slate-700">
{JSON.stringify(event.payload, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

export function AuditTab({ events }) {
  return (
    <div className="rounded-lg border border-border bg-card animate-fade-up" data-testid="audit-content">
      <div className="border-b border-border px-4 py-3">
        <h3 className="text-[14px] font-semibold text-foreground">Audit Trail</h3>
        <p className="mt-0.5 text-[12px] text-muted-foreground">
          Decision activity is recorded in an immutable-style audit trail. Expand a row to view the technical payload.
        </p>
      </div>
      <div className="hidden sm:flex items-center gap-3 border-b border-border px-4 py-2">
        <span className="inline-block h-4 w-4" />
        <span className="label-eyebrow w-[150px]">Timestamp</span>
        <span className="label-eyebrow flex-1">Event</span>
        <span className="label-eyebrow">Actor</span>
      </div>
      {events.length === 0 ? (
        <div className="px-4 py-12 text-center text-[13px] text-muted-foreground">No audit events recorded yet.</div>
      ) : (
        events.map((e) => <AuditRow key={e.id} event={e} />)
      )}
    </div>
  );
}
