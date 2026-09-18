import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { askBrain, getBrainChat, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import { Brain, Send, Loader2, User } from "lucide-react";

const PRESETS = [
  "Why was this application approved?",
  "Why this amount and not the requested amount?",
  "What are the key risks?",
  "Which policy rules were triggered?",
];

function Bubble({ role, content }) {
  const isUser = role === "user";
  return (
    <div className={`flex gap-2.5 ${isUser ? "flex-row-reverse" : ""}`} data-testid={`chat-msg-${role}`}>
      <span className={`mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-md border ${isUser ? "border-border bg-secondary" : "border-accent-foreground/30 bg-accent/40"}`}>
        {isUser ? <User className="h-3.5 w-3.5 text-muted-foreground" strokeWidth={1.8} /> : <Brain className="h-3.5 w-3.5 text-accent-foreground" strokeWidth={1.8} />}
      </span>
      <div className={`max-w-[80%] rounded-lg px-3.5 py-2.5 text-[13px] leading-relaxed whitespace-pre-wrap ${
        isUser ? "bg-primary text-primary-foreground" : "border border-border bg-card text-foreground"
      }`}>
        {content}
      </div>
    </div>
  );
}

export function AskBrainTab({ applicationId }) {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const scrollRef = useRef(null);

  useEffect(() => {
    getBrainChat(applicationId)
      .then((m) => setMessages(m.map((x) => ({ role: x.role, content: x.content }))))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [applicationId]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, sending]);

  const send = async (text) => {
    const q = (text ?? input).trim();
    if (!q || sending) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", content: q }]);
    setSending(true);
    try {
      const res = await askBrain(applicationId, { question: q });
      setMessages((m) => [...m, { role: "assistant", content: res.answer }]);
    } catch (err) {
      toast.error(apiErrorMessage(err, "Credit Brain assistant is unavailable"));
      setMessages((m) => [...m, { role: "assistant", content: "I couldn't generate an answer right now. Please try again." }]);
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="animate-fade-up" data-testid="ask-brain-content">
      <div className="flex items-center gap-2 rounded-lg border border-border bg-card px-4 py-3">
        <Brain className="h-4 w-4 text-accent-foreground" strokeWidth={1.8} />
        <span className="text-[13px] text-muted-foreground">Ask Credit Brain about this application. Answers are grounded only in this application's assessment and cite the figures used.</span>
      </div>

      <div className="mt-4 rounded-lg border border-border bg-card flex flex-col" style={{ height: "560px" }}>
        <div ref={scrollRef} className="flex-1 overflow-y-auto thin-scroll p-4 space-y-4">
          {loading ? (
            <div className="space-y-3"><Skeleton className="h-12 w-2/3" /><Skeleton className="h-16 w-3/4 ml-auto" /></div>
          ) : messages.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center text-center">
              <div className="grid h-12 w-12 place-items-center rounded-xl border border-border bg-secondary">
                <Brain className="h-6 w-6 text-accent-foreground" strokeWidth={1.6} />
              </div>
              <h3 className="mt-3 text-[15px] font-semibold text-foreground">Ask about this credit decision</h3>
              <p className="mt-1 max-w-sm text-[13px] text-muted-foreground">Try one of the questions below or type your own. Credit Brain answers only from this application's data.</p>
            </div>
          ) : (
            messages.map((m, i) => <Bubble key={i} role={m.role} content={m.content} />)
          )}
          {sending && (
            <div className="flex items-center gap-2 text-[12px] text-muted-foreground" data-testid="chat-thinking">
              <Loader2 className="h-3.5 w-3.5 animate-spin" /> Credit Brain is thinking…
            </div>
          )}
        </div>

        <div className="border-t border-border p-3">
          <div className="mb-2 flex flex-wrap gap-2">
            {PRESETS.map((p) => (
              <button
                key={p}
                type="button"
                disabled={sending}
                onClick={() => send(p)}
                data-testid={`preset-${p.slice(0, 10).toLowerCase().replace(/[^a-z]+/g, "-")}`}
                className="rounded-full border border-border bg-secondary/60 px-3 py-1 text-[12px] text-muted-foreground hover:border-accent-foreground/40 hover:text-foreground transition-colors disabled:opacity-50"
              >
                {p}
              </button>
            ))}
          </div>
          <div className="flex items-end gap-2">
            <Textarea
              data-testid="ask-brain-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
              placeholder="Ask about the decision, amount, risks, or policy…"
              rows={2}
              className="resize-none text-[13px]"
            />
            <Button onClick={() => send()} disabled={sending || !input.trim()} data-testid="ask-brain-send" className="h-9">
              {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" strokeWidth={1.8} />}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
