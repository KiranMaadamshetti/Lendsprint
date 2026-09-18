import { useEffect, useState, useCallback, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import {
  getApplication,
  getAuditTrail,
  runDecision,
  overrideDecision,
  uploadDocuments,
  deleteDocument,
  fetchDocumentBlob,
  documentDownloadUrl,
  apiErrorMessage,
} from "@/lib/api";
import { formatINR, formatDate, formatFileSize, LOAN_TYPE_LABEL, DOC_TYPE_LABEL } from "@/lib/format";
import { DecisionBadge, StatusBadge, DocStatusBadge } from "@/components/common/StatusBadge";
import { DecisionTab } from "@/components/application/DecisionTab";
import { MemoTab } from "@/components/application/MemoTab";
import { AuditTab } from "@/components/application/AuditTab";
import { CreditBrainTab } from "@/components/application/CreditBrainTab";
import { PolicyTab } from "@/components/application/PolicyTab";
import { AskBrainTab } from "@/components/application/AskBrainTab";
import { DecisionTraceTab } from "@/components/application/DecisionTraceTab";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription,
} from "@/components/ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  ArrowLeft, Play, RotateCw, FileText, Download, Trash2, UploadCloud, Loader2, Plus, Eye, Sparkles,
} from "lucide-react";

import { getMyAuthority, applicationAction } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export default function ApplicationDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const fileInput = useRef(null);
  const [data, setData] = useState(null);
  const [audit, setAudit] = useState([]);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [tab, setTab] = useState("overview");
  const [running, setRunning] = useState(false);
  const [stepIdx, setStepIdx] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [useAi, setUseAi] = useState(false);
  const { user } = useAuth();
  const [authority, setAuthority] = useState(null);
  const [acting, setActing] = useState("");

  useEffect(() => { getMyAuthority().then(setAuthority).catch(() => {}); }, []);

  const perms = new Set(authority?.permissions || []);
  const maxAuth = authority?.max_authority ?? 0;

  const doAction = async (action) => {
    setActing(action);
    try {
      const res = await applicationAction(id, { action });
      setData((d) => ({ ...d, application: { ...d.application, status: res.status } }));
      const a = await getAuditTrail(id);
      setAudit(a);
      toast.success(res.event);
    } catch (err) {
      toast.error(apiErrorMessage(err));
    } finally {
      setActing("");
    }
  };

  // override dialog
  const [ovOpen, setOvOpen] = useState(false);
  const [ovDecision, setOvDecision] = useState("review");
  const [ovReason, setOvReason] = useState("");
  const [ovSaving, setOvSaving] = useState(false);

  // pdf preview
  const [preview, setPreview] = useState({ open: false, url: null, name: "", loading: false });

  const load = useCallback(async () => {
    try {
      const [d, a] = await Promise.all([getApplication(id), getAuditTrail(id)]);
      setData(d);
      setAudit(a);
    } catch (err) {
      if (err?.response?.status === 404) setNotFound(true);
      else toast.error(apiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  const runDecisionFlow = async () => {
    if (running) return;
    if (!data?.documents?.length) {
      toast.error("Upload at least one document before running the decision");
      setTab("documents");
      return;
    }
    setTab("decision");
    setRunning(true);
    setStepIdx(0);
    const timer = setInterval(() => setStepIdx((i) => Math.min(i + 1, 5)), 430);
    try {
      const [dec] = await Promise.all([runDecision(id, useAi), sleep(2500)]);
      clearInterval(timer);
      setStepIdx(6);
      const newStatus = { approve: "approved", review: "review", reject: "rejected" }[dec.decision] || "decided";
      setData((d) => ({ ...d, decision: dec, application: { ...d.application, status: newStatus } }));
      const a = await getAuditTrail(id);
      setAudit(a);
      toast.success(useAi ? "Decision generated · AI memo drafted" : "Decision generated");
    } catch (err) {
      clearInterval(timer);
      toast.error(apiErrorMessage(err, "Decision could not be generated"));
    } finally {
      setRunning(false);
    }
  };

  const openOverride = () => {
    setOvDecision(data?.decision?.decision || "review");
    setOvReason("");
    setOvOpen(true);
  };

  const submitOverride = async () => {
    if (ovReason.trim().length < 3) return toast.error("Please provide a reason for the override");
    setOvSaving(true);
    try {
      const dec = await overrideDecision(id, { decision: ovDecision, reason: ovReason.trim() });
      setData((d) => ({ ...d, decision: dec }));
      const a = await getAuditTrail(id);
      setAudit(a);
      setOvOpen(false);
      toast.success("Decision overridden");
    } catch (err) {
      toast.error(apiErrorMessage(err, "Unable to override decision"));
    } finally {
      setOvSaving(false);
    }
  };

  const handleUpload = async (fileList) => {
    const items = Array.from(fileList)
      .filter((f) => f.type === "application/pdf" || f.name.toLowerCase().endsWith(".pdf"))
      .map((f) => ({ file: f, docType: "bank_statement" }));
    if (!items.length) return toast.error("Only PDF files are allowed");
    setUploading(true);
    try {
      await uploadDocuments(id, items);
      toast.success("Documents uploaded");
      await load();
    } catch (err) {
      toast.error(apiErrorMessage(err, "Document upload failed"));
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (docId) => {
    try {
      await deleteDocument(docId);
      toast.success("Document removed");
      await load();
    } catch (err) {
      toast.error(apiErrorMessage(err));
    }
  };

  const openPreview = async (doc) => {
    setPreview({ open: true, url: null, name: doc.filename, loading: true });
    try {
      const blob = await fetchDocumentBlob(doc.id);
      const url = URL.createObjectURL(blob);
      setPreview({ open: true, url, name: doc.filename, loading: false });
    } catch (err) {
      setPreview({ open: false, url: null, name: "", loading: false });
      toast.error(err?.response?.status === 404
        ? "This sample document has no stored file to preview. Upload a real PDF to preview it."
        : apiErrorMessage(err, "Unable to preview document"));
    }
  };

  const closePreview = () => {
    if (preview.url) URL.revokeObjectURL(preview.url);
    setPreview({ open: false, url: null, name: "", loading: false });
  };

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  if (notFound) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-center" data-testid="app-not-found">
        <h2 className="text-[18px] font-semibold text-foreground">Application not found</h2>
        <p className="mt-1 text-[13px] text-muted-foreground">This application may have been removed or the link is invalid.</p>
        <Button className="mt-5" onClick={() => navigate("/dashboard")}>Back to Dashboard</Button>
      </div>
    );
  }

  const { application, documents, decision } = data;

  const summary = [
    { label: "Requested Amount", value: formatINR(application.loan_amount) },
    { label: "Documents", value: documents.length },
    { label: "Decision Status", value: decision ? decision.decision[0].toUpperCase() + decision.decision.slice(1) : "Pending" },
    { label: "PD Score", value: decision ? `${(decision.pd_score * 100).toFixed(1)}%` : "—" },
    { label: "Decision TAT", value: decision ? `${decision.tat_minutes} min` : "—" },
  ];

  return (
    <div className="animate-fade-up">
      <button
        onClick={() => navigate("/dashboard")}
        className="inline-flex items-center gap-1.5 text-[13px] text-muted-foreground hover:text-foreground transition-colors"
        data-testid="back-to-dashboard"
      >
        <ArrowLeft className="h-4 w-4" strokeWidth={1.8} /> Dashboard
      </button>

      {/* Identity header */}
      <div className="mt-3 flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <span className="tnum text-[13px] font-medium text-muted-foreground">{application.reference}</span>
            <StatusBadge status={application.status} />
            {decision && <DecisionBadge decision={decision.decision} />}
          </div>
          <h1 className="mt-1.5 text-[24px] font-semibold tracking-tight text-foreground">{application.borrower_name}</h1>
          <div className="mt-0.5 flex items-center gap-3 text-[13px] text-muted-foreground">
            <span>{LOAN_TYPE_LABEL[application.loan_type]}</span>
            <span className="h-1 w-1 rounded-full bg-border" />
            <span className="tnum">{formatINR(application.loan_amount)}</span>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 rounded-md border border-border bg-card px-3 h-9" title="Draft the credit memo with the live LLM">
            <Sparkles className={`h-4 w-4 ${useAi ? "text-accent-foreground" : "text-muted-foreground"}`} strokeWidth={1.8} />
            <Label htmlFor="ai-memo" className="text-[12px] font-medium text-foreground cursor-pointer">AI memo</Label>
            <Switch id="ai-memo" checked={useAi} onCheckedChange={setUseAi} data-testid="ai-memo-toggle" />
          </div>
          <Button onClick={runDecisionFlow} disabled={running} data-testid="run-decision-header-btn">
            {running ? (
              <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Running Decision…</>
            ) : decision ? (
              <><RotateCw className="mr-1.5 h-4 w-4" strokeWidth={1.8} />Re-run Decision</>
            ) : (
              <><Play className="mr-1.5 h-4 w-4" strokeWidth={1.8} />Run Decision</>
            )}
          </Button>
        </div>
      </div>

      {/* Summary strip */}
      <div className="mt-5 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        {summary.map((s) => (
          <div key={s.label} className="rounded-lg border border-border bg-card px-4 py-3">
            <div className="label-eyebrow">{s.label}</div>
            <div className="metric-num mt-1.5 text-[20px] font-semibold text-foreground">{s.value}</div>
          </div>
        ))}
      </div>

      {/* Committee action bar */}
      {decision && (perms.has("approve") || perms.has("review")) && !["approved", "rejected"].includes(application.status) && (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-card px-4 py-3" data-testid="committee-bar">
          <div className="text-[12px] text-muted-foreground">
            {decision.required_authority && (
              <>Required approval authority: <span className="font-medium text-foreground">{decision.required_authority}</span>. </>
            )}
            {perms.has("approve") && decision.recommended_amount > maxAuth && (
              <span className="text-amber-700 font-medium" data-testid="escalation-note">Escalation required — exceeds your approval authority.</span>
            )}
          </div>
          <div className="flex items-center gap-2">
            {perms.has("review") && (
              <Button size="sm" variant="outline" disabled={!!acting} onClick={() => doAction("send_review")} data-testid="action-send-review">Send for Review</Button>
            )}
            {perms.has("escalate") && (
              <Button size="sm" variant="outline" disabled={!!acting} onClick={() => doAction("escalate")} data-testid="action-escalate">Escalate</Button>
            )}
            {perms.has("reject") && (
              <Button size="sm" variant="outline" className="border-red-200 text-red-700 hover:bg-red-50" disabled={!!acting} onClick={() => doAction("reject")} data-testid="action-reject">Reject</Button>
            )}
            {perms.has("approve") && (
              <Button size="sm" disabled={!!acting || decision.recommended_amount > maxAuth} onClick={() => doAction("approve")} data-testid="action-approve">
                {acting === "approve" ? <><Loader2 className="mr-1.5 h-4 w-4 animate-spin" />Approving…</> : "Approve"}
              </Button>
            )}
          </div>
        </div>
      )}

      {/* Tabs */}
      <Tabs value={tab} onValueChange={setTab} className="mt-6">
        <TabsList className="w-full justify-start rounded-none border-b border-border bg-transparent p-0 h-auto gap-1">
          {[
            ["overview", "Overview"],
            ["documents", "Documents"],
            ["brain", "Credit Brain"],
            ["policy", "Policy"],
            ["decision", "Decision"],
            ["trace", "Trace"],
            ["memo", "Credit Memo"],
            ["ask", "Ask Brain"],
            ["audit", "Audit Trail"],
          ].map(([v, label]) => (
            <TabsTrigger
              key={v}
              value={v}
              data-testid={`tab-${v}`}
              className="rounded-none border-b-2 border-transparent bg-transparent px-3 py-2.5 text-[13px] font-medium text-muted-foreground data-[state=active]:border-primary data-[state=active]:text-foreground data-[state=active]:shadow-none data-[state=active]:bg-transparent"
            >
              {label}
            </TabsTrigger>
          ))}
        </TabsList>

        {/* Overview */}
        <TabsContent value="overview" className="mt-5">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="rounded-lg border border-border bg-card p-5">
              <h3 className="text-[14px] font-semibold text-foreground">Borrower Information</h3>
              <dl className="mt-4 space-y-3">
                {[
                  ["Borrower", application.borrower_name],
                  ["Loan Type", LOAN_TYPE_LABEL[application.loan_type]],
                  ["Requested", formatINR(application.loan_amount)],
                  ["Application Date", formatDate(application.created_at)],
                ].map(([k, v]) => (
                  <div key={k} className="flex items-center justify-between border-b border-border/70 pb-2.5 last:border-0 last:pb-0">
                    <dt className="text-[12px] text-muted-foreground">{k}</dt>
                    <dd className="text-[13px] font-medium text-foreground text-right max-w-[60%] truncate">{v}</dd>
                  </div>
                ))}
              </dl>
            </div>

            <div className="rounded-lg border border-border bg-card p-5 lg:col-span-2">
              <h3 className="text-[14px] font-semibold text-foreground">Document Analysis</h3>
              {documents.length === 0 ? (
                <div className="mt-4 text-[13px] text-muted-foreground">No documents uploaded yet. Use the Documents tab to add PDFs.</div>
              ) : (
                <div className="mt-4 overflow-x-auto thin-scroll">
                  <table className="w-full min-w-[500px] text-left">
                    <thead>
                      <tr className="border-b border-border">
                        {["Document", "Type", "Status", "Uploaded", "Analysis"].map((h) => (
                          <th key={h} className="label-eyebrow px-2 py-2 font-semibold">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {documents.map((d) => (
                        <tr key={d.id} className="border-b border-border last:border-0">
                          <td className="px-2 py-2.5 text-[13px] text-foreground max-w-[180px] truncate">{d.filename}</td>
                          <td className="px-2 py-2.5 text-[13px] text-muted-foreground">{DOC_TYPE_LABEL[d.doc_type]}</td>
                          <td className="px-2 py-2.5"><DocStatusBadge status={d.status} /></td>
                          <td className="px-2 py-2.5 text-[13px] text-muted-foreground">{formatDate(d.uploaded_at)}</td>
                          <td className="px-2 py-2.5"><span className="text-[12px] font-medium text-emerald-700">Ready</span></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </TabsContent>

        {/* Documents */}
        <TabsContent value="documents" className="mt-5">
          <div className="rounded-lg border border-border bg-card">
            <div className="flex items-center justify-between border-b border-border px-4 py-3">
              <h3 className="text-[14px] font-semibold text-foreground">Documents</h3>
              <Button size="sm" variant="outline" onClick={() => fileInput.current?.click()} disabled={uploading} data-testid="add-documents-btn">
                {uploading ? <><Loader2 className="mr-1.5 h-4 w-4 animate-spin" />Uploading…</> : <><Plus className="mr-1.5 h-4 w-4" strokeWidth={2} />Add documents</>}
              </Button>
              <input ref={fileInput} type="file" accept="application/pdf" multiple className="hidden" data-testid="detail-file-input" onChange={(e) => { handleUpload(e.target.files); e.target.value = ""; }} />
            </div>
            {documents.length === 0 ? (
              <div className="flex flex-col items-center py-14 text-center">
                <UploadCloud className="h-8 w-8 text-muted-foreground" strokeWidth={1.5} />
                <p className="mt-3 text-[13px] text-muted-foreground max-w-xs">No documents yet. Upload bank statements, ITR, GST or salary slips as PDF.</p>
              </div>
            ) : (
              <div className="overflow-x-auto thin-scroll">
                <table className="w-full min-w-[680px] text-left">
                  <thead>
                    <tr className="border-b border-border">
                      {["Type", "Filename", "Status", "Uploaded", "Size", ""].map((h) => (
                        <th key={h} className="label-eyebrow px-4 py-2.5 font-semibold">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {documents.map((d) => (
                      <tr key={d.id} className="border-b border-border last:border-0 hover:bg-secondary/40 transition-colors">
                        <td className="px-4 py-3 text-[13px] font-medium text-foreground">{DOC_TYPE_LABEL[d.doc_type]}</td>
                        <td className="px-4 py-3 text-[13px] text-muted-foreground max-w-[220px] truncate flex items-center gap-2">
                          <FileText className="h-4 w-4 text-muted-foreground/70 shrink-0" strokeWidth={1.8} />{d.filename}
                        </td>
                        <td className="px-4 py-3"><DocStatusBadge status={d.status} /></td>
                        <td className="px-4 py-3 text-[13px] text-muted-foreground">{formatDate(d.uploaded_at)}</td>
                        <td className="px-4 py-3 tnum text-[13px] text-muted-foreground">{formatFileSize(d.file_size)}</td>
                        <td className="px-4 py-3 text-right">
                          <div className="flex items-center justify-end gap-1">
                            <button onClick={() => openPreview(d)} className="grid h-7 w-7 place-items-center rounded text-muted-foreground hover:bg-secondary hover:text-foreground transition-colors" title="View" data-testid={`view-doc-${d.id}`}>
                              <Eye className="h-4 w-4" strokeWidth={1.8} />
                            </button>
                            <a href={documentDownloadUrl(d.id)} target="_blank" rel="noreferrer" className="grid h-7 w-7 place-items-center rounded text-muted-foreground hover:bg-secondary hover:text-foreground transition-colors" title="Download" data-testid={`download-doc-${d.id}`}>
                              <Download className="h-4 w-4" strokeWidth={1.8} />
                            </a>
                            <button onClick={() => handleDelete(d.id)} className="grid h-7 w-7 place-items-center rounded text-muted-foreground hover:bg-secondary hover:text-red-600 transition-colors" title="Remove" data-testid={`delete-doc-${d.id}`}>
                              <Trash2 className="h-4 w-4" strokeWidth={1.8} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </TabsContent>

        {/* Decision */}
        <TabsContent value="brain" className="mt-5">
          <CreditBrainTab applicationId={id} />
        </TabsContent>

        <TabsContent value="policy" className="mt-5">
          <PolicyTab decision={decision} />
        </TabsContent>

        <TabsContent value="decision" className="mt-5">
          <DecisionTab
            decision={decision}
            running={running}
            stepIdx={stepIdx}
            onRun={runDecisionFlow}
            hasDocuments={documents.length > 0}
            onOverrideClick={openOverride}
          />
        </TabsContent>

        {/* Decision Trace */}
        <TabsContent value="trace" className="mt-5">
          <DecisionTraceTab application={application} documents={documents} decision={decision} onRun={runDecisionFlow} />
        </TabsContent>

        {/* Credit Memo */}
        <TabsContent value="memo" className="mt-5">
          <MemoTab application={application} decision={decision} onRun={runDecisionFlow} />
        </TabsContent>

        {/* Ask Brain */}
        <TabsContent value="ask" className="mt-5">
          <AskBrainTab applicationId={id} />
        </TabsContent>

        {/* Audit */}
        <TabsContent value="audit" className="mt-5">
          <AuditTab events={audit} />
        </TabsContent>
      </Tabs>

      {/* Override dialog */}
      <Dialog open={ovOpen} onOpenChange={setOvOpen}>
        <DialogContent className="sm:max-w-md" data-testid="override-dialog">
          <DialogHeader>
            <DialogTitle>Override credit decision</DialogTitle>
            <DialogDescription>
              The model recommended <span className="font-medium uppercase">{decision?.model_decision || decision?.decision}</span>.
              An override is recorded in the audit trail with your reason.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-1">
            <div className="space-y-1.5">
              <Label className="text-[13px]">Final decision</Label>
              <Select value={ovDecision} onValueChange={setOvDecision}>
                <SelectTrigger data-testid="override-decision-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="approve">Approve</SelectItem>
                  <SelectItem value="review">Review</SelectItem>
                  <SelectItem value="reject">Reject</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-[13px]">Reason</Label>
              <Textarea
                data-testid="override-reason-input"
                value={ovReason}
                onChange={(e) => setOvReason(e.target.value)}
                placeholder="Document the rationale for overriding the model decision…"
                rows={4}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOvOpen(false)}>Cancel</Button>
            <Button onClick={submitOverride} disabled={ovSaving} data-testid="override-submit-btn">
              {ovSaving ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Saving…</> : "Apply override"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* PDF preview dialog */}
      <Dialog open={preview.open} onOpenChange={(o) => !o && closePreview()}>
        <DialogContent className="max-w-3xl" data-testid="pdf-preview-dialog">
          <DialogHeader>
            <DialogTitle className="truncate">{preview.name}</DialogTitle>
            <DialogDescription>Read-only preview of the uploaded document.</DialogDescription>
          </DialogHeader>
          <div className="h-[70vh] w-full rounded-md border border-border bg-secondary/40 overflow-hidden">
            {preview.loading ? (
              <div className="flex h-full items-center justify-center text-[13px] text-muted-foreground">
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />Loading document…
              </div>
            ) : preview.url ? (
              <iframe title={preview.name} src={preview.url} className="h-full w-full" />
            ) : null}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
