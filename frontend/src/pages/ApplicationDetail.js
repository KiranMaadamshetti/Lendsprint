import { useEffect, useState, useCallback, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import {
  getApplication,
  getAuditTrail,
  runDecision,
  uploadDocuments,
  deleteDocument,
  documentDownloadUrl,
  apiErrorMessage,
} from "@/lib/api";
import { formatINR, formatDate, formatFileSize, LOAN_TYPE_LABEL, DOC_TYPE_LABEL } from "@/lib/format";
import { DecisionBadge, StatusBadge, DocStatusBadge } from "@/components/common/StatusBadge";
import { DecisionTab } from "@/components/application/DecisionTab";
import { MemoTab } from "@/components/application/MemoTab";
import { AuditTab } from "@/components/application/AuditTab";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import {
  ArrowLeft, Play, RotateCw, FileText, Download, Trash2, UploadCloud, Loader2, Plus,
} from "lucide-react";

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
      const [dec] = await Promise.all([runDecision(id), sleep(2500)]);
      clearInterval(timer);
      setStepIdx(6);
      setData((d) => ({ ...d, decision: dec, application: { ...d.application, status: "decided" } }));
      const a = await getAuditTrail(id);
      setAudit(a);
      toast.success("Decision generated");
    } catch (err) {
      clearInterval(timer);
      toast.error(apiErrorMessage(err, "Decision could not be generated"));
    } finally {
      setRunning(false);
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

      {/* Summary strip */}
      <div className="mt-5 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        {summary.map((s) => (
          <div key={s.label} className="rounded-lg border border-border bg-card px-4 py-3">
            <div className="label-eyebrow">{s.label}</div>
            <div className="metric-num mt-1.5 text-[20px] font-semibold text-foreground">{s.value}</div>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <Tabs value={tab} onValueChange={setTab} className="mt-6">
        <TabsList className="w-full justify-start rounded-none border-b border-border bg-transparent p-0 h-auto gap-1">
          {[
            ["overview", "Overview"],
            ["documents", "Documents"],
            ["decision", "Decision"],
            ["memo", "Credit Memo"],
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
                <table className="w-full min-w-[640px] text-left">
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
        <TabsContent value="decision" className="mt-5">
          <DecisionTab decision={decision} running={running} stepIdx={stepIdx} onRun={runDecisionFlow} hasDocuments={documents.length > 0} />
        </TabsContent>

        {/* Credit Memo */}
        <TabsContent value="memo" className="mt-5">
          <MemoTab application={application} decision={decision} onRun={runDecisionFlow} />
        </TabsContent>

        {/* Audit */}
        <TabsContent value="audit" className="mt-5">
          <AuditTab events={audit} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
