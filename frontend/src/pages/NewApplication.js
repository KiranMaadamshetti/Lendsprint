import { useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { createApplication, uploadDocuments, apiErrorMessage } from "@/lib/api";
import { DOC_TYPE_LABEL, formatFileSize } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ArrowLeft, UploadCloud, FileText, X, Loader2, ShieldCheck } from "lucide-react";

const DOC_TYPES = ["bank_statement", "itr", "gst", "salary_slip"];

export default function NewApplication() {
  const navigate = useNavigate();
  const fileInput = useRef(null);
  const [borrowerName, setBorrowerName] = useState("");
  const [loanType, setLoanType] = useState("MSME");
  const [amount, setAmount] = useState("");
  const [files, setFiles] = useState([]); // {file, docType, id}
  const [dragOver, setDragOver] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const addFiles = (fileList) => {
    const arr = Array.from(fileList);
    const valid = [];
    for (const f of arr) {
      if (f.type !== "application/pdf" && !f.name.toLowerCase().endsWith(".pdf")) {
        toast.error(`${f.name} is not a PDF`);
        continue;
      }
      valid.push({ file: f, docType: "bank_statement", id: `${f.name}-${f.size}-${Math.random()}` });
    }
    if (valid.length) setFiles((p) => [...p, ...valid]);
  };

  const onDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files?.length) addFiles(e.dataTransfer.files);
  };

  const removeFile = (id) => setFiles((p) => p.filter((f) => f.id !== id));
  const setDocType = (id, docType) => setFiles((p) => p.map((f) => (f.id === id ? { ...f, docType } : f)));

  const formatAmountDisplay = (v) => {
    const num = Number(String(v).replace(/[^0-9]/g, ""));
    if (!num) return "";
    return num.toLocaleString("en-IN");
  };

  const submit = async () => {
    if (!borrowerName.trim()) return toast.error("Borrower name is required");
    const amt = Number(String(amount).replace(/[^0-9]/g, ""));
    if (!amt || amt <= 0) return toast.error("Enter a valid loan amount");

    setSubmitting(true);
    try {
      const application = await createApplication({
        borrower_name: borrowerName.trim(),
        loan_type: loanType,
        loan_amount: amt,
      });
      toast.success("Application created");
      if (files.length) {
        try {
          await uploadDocuments(application.id, files.map((f) => ({ file: f.file, docType: f.docType })));
          toast.success(`${files.length} document${files.length > 1 ? "s" : ""} uploaded`);
        } catch (err) {
          toast.error(apiErrorMessage(err, "Document upload failed"));
        }
      }
      navigate(`/applications/${application.id}`);
    } catch (err) {
      toast.error(apiErrorMessage(err, "Unable to create application"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="animate-fade-up">
      <button
        onClick={() => navigate("/dashboard")}
        className="inline-flex items-center gap-1.5 text-[13px] text-muted-foreground hover:text-foreground transition-colors"
        data-testid="back-to-dashboard"
      >
        <ArrowLeft className="h-4 w-4" strokeWidth={1.8} /> Dashboard
      </button>

      <div className="mt-3">
        <h1 className="text-[24px] font-semibold tracking-tight text-foreground">New Application</h1>
        <p className="mt-0.5 text-[13px] text-muted-foreground">
          Create a borrower application and upload supporting financial documents.
        </p>
      </div>

      <div className="mt-6 grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Left: application details */}
        <div className="rounded-lg border border-border bg-card p-5">
          <h2 className="text-[15px] font-semibold text-foreground">Application Details</h2>
          <p className="mt-0.5 text-[12px] text-muted-foreground">A reference is generated automatically.</p>

          <div className="mt-5 space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="borrower" className="text-[13px]">Borrower Name</Label>
              <Input
                id="borrower"
                data-testid="borrower-name-input"
                value={borrowerName}
                onChange={(e) => setBorrowerName(e.target.value)}
                placeholder="e.g. Arvind Engineering Pvt Ltd"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-[13px]">Loan Type</Label>
              <Select value={loanType} onValueChange={setLoanType}>
                <SelectTrigger data-testid="loan-type-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="business">Business</SelectItem>
                  <SelectItem value="personal">Personal</SelectItem>
                  <SelectItem value="MSME">MSME</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="amount" className="text-[13px]">Loan Amount</Label>
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-[14px] text-muted-foreground">₹</span>
                <Input
                  id="amount"
                  data-testid="loan-amount-input"
                  value={formatAmountDisplay(amount)}
                  onChange={(e) => setAmount(e.target.value)}
                  placeholder="35,00,000"
                  className="pl-7 tnum"
                  inputMode="numeric"
                />
              </div>
              <p className="text-[11px] text-muted-foreground">Enter the requested principal in rupees.</p>
            </div>
          </div>
        </div>

        {/* Right: document upload */}
        <div className="rounded-lg border border-border bg-card p-5">
          <h2 className="text-[15px] font-semibold text-foreground">Document Upload</h2>
          <p className="mt-0.5 text-[12px] text-muted-foreground">Upload financial documents</p>

          <div
            onClick={() => fileInput.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={onDrop}
            data-testid="dropzone"
            className={`mt-4 flex flex-col items-center justify-center rounded-lg border border-dashed px-4 py-8 text-center cursor-pointer transition-colors ${
              dragOver ? "border-accent-foreground bg-accent" : "border-border hover:bg-secondary/50"
            }`}
          >
            <div className="grid h-11 w-11 place-items-center rounded-lg bg-secondary">
              <UploadCloud className="h-5 w-5 text-accent-foreground" strokeWidth={1.8} />
            </div>
            <div className="mt-3 text-[13px] font-medium text-foreground">Drag and drop PDFs here or browse files</div>
            <div className="mt-1 text-[12px] text-muted-foreground">PDF only · Bank Statement, ITR, GST, Salary Slip</div>
            <input
              ref={fileInput}
              type="file"
              accept="application/pdf"
              multiple
              className="hidden"
              data-testid="file-input"
              onChange={(e) => { addFiles(e.target.files); e.target.value = ""; }}
            />
          </div>

          {files.length > 0 && (
            <div className="mt-4 space-y-2" data-testid="uploaded-files-list">
              {files.map((f) => (
                <div key={f.id} className="flex items-center gap-3 rounded-md border border-border bg-secondary/40 px-3 py-2">
                  <FileText className="h-4 w-4 shrink-0 text-accent-foreground" strokeWidth={1.8} />
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-[13px] font-medium text-foreground">{f.file.name}</div>
                    <div className="text-[11px] text-muted-foreground">{formatFileSize(f.file.size)} · Ready</div>
                  </div>
                  <Select value={f.docType} onValueChange={(v) => setDocType(f.id, v)}>
                    <SelectTrigger className="h-8 w-[150px] text-[12px]"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {DOC_TYPES.map((d) => <SelectItem key={d} value={d}>{DOC_TYPE_LABEL[d]}</SelectItem>)}
                    </SelectContent>
                  </Select>
                  <button onClick={() => removeFile(f.id)} className="grid h-7 w-7 place-items-center rounded text-muted-foreground hover:bg-secondary hover:text-red-600 transition-colors" data-testid={`remove-file-${f.id}`}>
                    <X className="h-4 w-4" strokeWidth={2} />
                  </button>
                </div>
              ))}
            </div>
          )}

          <div className="mt-4 flex items-center gap-1.5 text-[11px] text-muted-foreground">
            <ShieldCheck className="h-3.5 w-3.5" strokeWidth={1.8} />
            Documents are securely associated with this application.
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="mt-5 flex items-center justify-end gap-2 border-t border-border pt-5">
        <Button variant="outline" onClick={() => navigate("/dashboard")} data-testid="cancel-btn">Cancel</Button>
        <Button onClick={submit} disabled={submitting} data-testid="create-application-btn">
          {submitting ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Creating…</> : "Create Application"}
        </Button>
      </div>
    </div>
  );
}
