// Formatting helpers for LendSprint AI

export function formatINR(amount) {
  if (amount == null) return "—";
  // Indian lakh/crore-aware short form
  if (amount >= 10000000) return `₹${(amount / 10000000).toFixed(2)} Cr`;
  if (amount >= 100000) return `₹${(amount / 100000).toFixed(2)} L`;
  return `₹${Number(amount).toLocaleString("en-IN")}`;
}

export function formatLakh(amount) {
  if (amount == null) return "—";
  return `₹${(amount / 100000).toFixed(2)} L`;
}

export function formatDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
}

export function formatDateTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  const date = d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
  const time = d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
  return `${date} ${time} IST`;
}

export function formatFileSize(bytes) {
  if (bytes == null) return "—";
  if (bytes >= 1048576) return `${(bytes / 1048576).toFixed(1)} MB`;
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${bytes} B`;
}

export const LOAN_TYPE_LABEL = { business: "Business", personal: "Personal", MSME: "MSME" };
export const DOC_TYPE_LABEL = {
  bank_statement: "Bank Statement",
  itr: "ITR",
  gst: "GST",
  salary_slip: "Salary Slip",
  kyc: "KYC",
  cibil: "CIBIL Report",
  purchase_bills: "Purchase Bills",
  sales_bills: "Sales Bills",
};

export function pct(v, digits = 1) {
  if (v == null) return "—";
  return `${(v * 100).toFixed(digits)}%`;
}
