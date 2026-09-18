import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import {
  getApplications,
  getDashboardStats,
  seedDemoData,
  apiErrorMessage,
} from "@/lib/api";
import { formatINR, formatDate, LOAN_TYPE_LABEL } from "@/lib/format";
import { DecisionBadge, StatusBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Plus,
  Database,
  Search,
  ArrowUpRight,
  FileStack,
  Zap,
  Timer,
  AlertCircle,
  Calendar,
} from "lucide-react";

const STAT_META = [
  { key: "total_applications", label: "Total Applications", sub: "Applications processed", icon: FileStack, fmt: (v) => v },
  { key: "straight_through_rate", label: "Straight-Through Rate", sub: "Decisions without manual review", icon: Zap, fmt: (v) => `${v}%` },
  { key: "avg_tat", label: "Average TAT", sub: "Submission to decision", icon: Timer, fmt: (v) => `${v} min` },
  { key: "pending_review", label: "Pending Review", sub: "Applications requiring analyst attention", icon: AlertCircle, fmt: (v) => v },
];

function StatCard({ meta, value, loading }) {
  const Icon = meta.icon;
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="flex items-center justify-between">
        <span className="label-eyebrow">{meta.label}</span>
        <Icon className="h-4 w-4 text-muted-foreground/70" strokeWidth={1.8} />
      </div>
      {loading ? (
        <Skeleton className="h-9 w-24 mt-3" />
      ) : (
        <div className="metric-num mt-2 text-[30px] font-semibold text-foreground leading-none">
          {meta.fmt(value)}
        </div>
      )}
      <div className="mt-2 text-[12px] text-muted-foreground">{meta.sub}</div>
    </div>
  );
}

export default function Dashboard() {
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [apps, setApps] = useState([]);
  const [loading, setLoading] = useState(true);
  const [seeding, setSeeding] = useState(false);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");

  const load = useCallback(async () => {
    try {
      const [s, a] = await Promise.all([
        getDashboardStats(),
        getApplications({ search, status: statusFilter, loan_type: typeFilter }),
      ]);
      setStats(s);
      setApps(a);
    } catch (err) {
      toast.error(apiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [search, statusFilter, typeFilter]);

  useEffect(() => {
    const t = setTimeout(load, 250);
    return () => clearTimeout(t);
  }, [load]);

  const handleSeed = async () => {
    setSeeding(true);
    try {
      const res = await seedDemoData();
      toast.success(res.created ? "Sample portfolio loaded" : "Sample portfolio already present");
      await load();
    } catch (err) {
      toast.error(apiErrorMessage(err));
    } finally {
      setSeeding(false);
    }
  };

  const isEmpty = !loading && apps.length === 0 && !search && statusFilter === "all" && typeFilter === "all";

  return (
    <div className="animate-fade-up">
      {/* Page header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-[24px] font-semibold tracking-tight text-foreground">Dashboard</h1>
          <p className="mt-0.5 text-[13px] text-muted-foreground">Credit applications and decision activity</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="hidden sm:flex items-center gap-2 h-9 rounded-md border border-border bg-card px-3 text-[13px] text-muted-foreground">
            <Calendar className="h-4 w-4" strokeWidth={1.8} />
            Last 30 days
          </div>
          <Button variant="outline" size="sm" data-testid="load-sample-btn" onClick={handleSeed} disabled={seeding}>
            <Database className="mr-1.5 h-4 w-4" strokeWidth={1.8} />
            {seeding ? "Loading…" : "Load sample data"}
          </Button>
          <Button size="sm" data-testid="new-application-btn" onClick={() => navigate("/applications/new")}>
            <Plus className="mr-1.5 h-4 w-4" strokeWidth={2} />
            New application
          </Button>
        </div>
      </div>

      {/* Stat cards */}
      <div className="mt-5 grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3">
        {STAT_META.map((meta) => (
          <StatCard key={meta.key} meta={meta} value={stats?.[meta.key]} loading={loading && !stats} />
        ))}
      </div>

      {/* Applications table */}
      <div className="mt-6 rounded-lg border border-border bg-card">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-3">
          <h2 className="text-[15px] font-semibold text-foreground">Recent Applications</h2>
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-2 h-9 rounded-md border border-border bg-card px-3 w-[210px]">
              <Search className="h-4 w-4 text-muted-foreground" strokeWidth={1.8} />
              <input
                data-testid="app-search"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search borrower or ID"
                className="flex-1 bg-transparent text-[13px] focus:outline-none"
              />
            </div>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="h-9 w-[130px] text-[13px]" data-testid="status-filter">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All statuses</SelectItem>
                <SelectItem value="pending">Pending</SelectItem>
                <SelectItem value="decided">Decided</SelectItem>
              </SelectContent>
            </Select>
            <Select value={typeFilter} onValueChange={setTypeFilter}>
              <SelectTrigger className="h-9 w-[130px] text-[13px]" data-testid="type-filter">
                <SelectValue placeholder="Loan type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All types</SelectItem>
                <SelectItem value="business">Business</SelectItem>
                <SelectItem value="personal">Personal</SelectItem>
                <SelectItem value="MSME">MSME</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        <div className="overflow-x-auto thin-scroll">
          <table className="w-full min-w-[880px] text-left">
            <thead>
              <tr className="border-b border-border">
                {["Application", "Borrower", "Product", "Requested", "Recommended", "Status", "Decision", "EMI", ""].map((h, i) => (
                  <th key={i} className={`label-eyebrow px-4 py-2.5 font-semibold ${["Requested", "Recommended", "EMI"].includes(h) ? "text-right" : ""}`}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading && apps.length === 0 ? (
                Array.from({ length: 4 }).map((_, i) => (
                  <tr key={i} className="border-b border-border">
                    <td colSpan={9} className="px-4 py-3"><Skeleton className="h-5 w-full" /></td>
                  </tr>
                ))
              ) : apps.length === 0 ? (
                <tr>
                  <td colSpan={9} className="px-4 py-16">
                    <EmptyState isTrulyEmpty={isEmpty} onSeed={handleSeed} seeding={seeding} onNew={() => navigate("/applications/new")} />
                  </td>
                </tr>
              ) : (
                apps.map((a) => (
                  <tr
                    key={a.id}
                    data-testid={`app-row-${a.id}`}
                    onClick={() => navigate(`/applications/${a.id}`)}
                    className="group border-b border-border last:border-0 hover:bg-secondary/50 cursor-pointer transition-colors"
                  >
                    <td className="px-4 py-3 tnum text-[13px] font-medium text-foreground">{a.reference}</td>
                    <td className="px-4 py-3 text-[13px] text-foreground max-w-[220px] truncate">{a.borrower_name}</td>
                    <td className="px-4 py-3 text-[13px] text-muted-foreground">{LOAN_TYPE_LABEL[a.loan_type]}</td>
                    <td className="px-4 py-3 tnum text-[13px] text-right font-medium text-foreground">{formatINR(a.loan_amount)}</td>
                    <td className="px-4 py-3 tnum text-[13px] text-right text-foreground">{a.recommended_amount != null ? formatINR(a.recommended_amount) : "—"}</td>
                    <td className="px-4 py-3"><StatusBadge status={a.status} /></td>
                    <td className="px-4 py-3">{a.decision ? <DecisionBadge decision={a.decision} /> : <span className="text-[13px] text-muted-foreground">—</span>}</td>
                    <td className="px-4 py-3 tnum text-[13px] text-right text-muted-foreground">{a.emi ? `₹${a.emi.toLocaleString("en-IN")}` : "—"}</td>
                    <td className="px-4 py-3 text-right">
                      <span className="inline-flex items-center gap-1 text-[12px] font-medium text-accent-foreground opacity-0 group-hover:opacity-100 transition-opacity">
                        View <ArrowUpRight className="h-3.5 w-3.5" strokeWidth={2} />
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function EmptyState({ isTrulyEmpty, onSeed, seeding, onNew }) {
  return (
    <div className="flex flex-col items-center text-center" data-testid="dashboard-empty">
      <div className="grid h-12 w-12 place-items-center rounded-lg border border-border bg-secondary">
        <FileStack className="h-6 w-6 text-muted-foreground" strokeWidth={1.6} />
      </div>
      <h3 className="mt-4 text-[15px] font-semibold text-foreground">
        {isTrulyEmpty ? "No applications yet" : "No matching applications"}
      </h3>
      <p className="mt-1 max-w-sm text-[13px] text-muted-foreground">
        {isTrulyEmpty
          ? "Load sample data to explore the credit decisioning workflow, or create a new application."
          : "Try adjusting your search or filters."}
      </p>
      {isTrulyEmpty && (
        <div className="mt-5 flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={onSeed} disabled={seeding}>
            <Database className="mr-1.5 h-4 w-4" strokeWidth={1.8} /> Load sample data
          </Button>
          <Button size="sm" onClick={onNew}>
            <Plus className="mr-1.5 h-4 w-4" strokeWidth={2} /> New application
          </Button>
        </div>
      )}
    </div>
  );
}
