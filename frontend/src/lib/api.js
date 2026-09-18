import axios from "axios";

const BASE = `${process.env.REACT_APP_BACKEND_URL}/api`;
const TOKEN_KEY = "ls_token";

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (t) => localStorage.setItem(TOKEN_KEY, t);
export const clearToken = () => localStorage.removeItem(TOKEN_KEY);

const client = axios.create({ baseURL: BASE });

client.interceptors.request.use((config) => {
  const token = getToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export function apiErrorMessage(err, fallback = "Something went wrong. Please try again.") {
  const detail = err?.response?.data?.detail;
  if (detail == null) return err?.message || fallback;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail.map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e))).join(" ");
  if (detail && typeof detail.msg === "string") return detail.msg;
  return fallback;
}

// Auth
export const login = (email, password) =>
  client.post("/auth/login", { email, password }).then((r) => r.data);
export const getMe = () => client.get("/auth/me").then((r) => r.data);

// Applications
export const getApplications = (params = {}) =>
  client.get("/applications", { params }).then((r) => r.data);
export const getApplication = (id) => client.get(`/applications/${id}`).then((r) => r.data);
export const createApplication = (data) =>
  client.post("/applications", data).then((r) => r.data);
export const getDashboardStats = () => client.get("/dashboard/stats").then((r) => r.data);

// Documents
export const uploadDocuments = (id, items) => {
  const form = new FormData();
  items.forEach(({ file, docType }) => {
    form.append("files", file);
    form.append("doc_types", docType);
  });
  return client
    .post(`/applications/${id}/documents`, form, {
      headers: { "Content-Type": "multipart/form-data" },
    })
    .then((r) => r.data);
};
export const deleteDocument = (docId) => client.delete(`/documents/${docId}`).then((r) => r.data);
export const documentDownloadUrl = (docId) =>
  `${BASE}/documents/${docId}/download`;

// Decision & audit
export const runDecision = (id, useAi = false) =>
  client.post(`/applications/${id}/decision`, { use_ai: useAi }).then((r) => r.data);
export const overrideDecision = (id, payload) =>
  client.post(`/applications/${id}/decision/override`, payload).then((r) => r.data);
export const getAuditTrail = (id) => client.get(`/applications/${id}/audit`).then((r) => r.data);
export const getReportsSummary = () => client.get("/reports/summary").then((r) => r.data);
export const fetchDocumentBlob = (docId) =>
  client.get(`/documents/${docId}/download`, { responseType: "blob" }).then((r) => r.data);

// Demo
export const seedDemoData = () => client.post("/demo/seed").then((r) => r.data);

// Credit policy & brain
export const getCreditPolicy = () => client.get("/credit-policy").then((r) => r.data);
export const getPolicyVersions = () => client.get("/credit-policy/versions").then((r) => r.data);
export const updateCreditPolicy = (payload) => client.put("/credit-policy", payload).then((r) => r.data);
export const simulatePolicy = (payload) => client.post("/credit-policy/simulate", payload).then((r) => r.data);
export const getCreditBrain = (id) => client.get(`/credit-brain/${id}`).then((r) => r.data);
export const getPolicyEvaluation = (id) => client.get(`/applications/${id}/policy-evaluation`).then((r) => r.data);

export default client;
