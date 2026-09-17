import { NavLink, useLocation } from "react-router-dom";
import {
  LayoutDashboard,
  FileText,
  Gauge,
  BarChart3,
  ShieldCheck,
  Settings,
  Lock,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

const mainItems = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard, active: true },
  { to: "/applications", label: "Applications", icon: FileText, active: true },
  { label: "Decisioning", icon: Gauge, active: false },
  { to: "/reports", label: "Reports", icon: BarChart3, active: true },
  { label: "Audit", icon: ShieldCheck, active: false },
];

function LockedItem({ item }) {
  const Icon = item.icon;
  return (
    <button
      data-testid={`nav-${item.label.toLowerCase()}`}
      onClick={() => toast.info(`${item.label} module is available in the full release.`)}
      className="group flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-[13px] font-medium text-muted-foreground/80 hover:bg-secondary transition-colors"
    >
      <Icon className="h-[17px] w-[17px] shrink-0" strokeWidth={1.8} />
      <span className="flex-1 text-left">{item.label}</span>
      <Lock className="h-3 w-3 opacity-50" strokeWidth={1.8} />
    </button>
  );
}

export function Sidebar() {
  const location = useLocation();
  return (
    <aside className="hidden lg:flex fixed left-0 top-14 bottom-0 w-[232px] flex-col border-r border-border bg-card/60 backdrop-blur-sm">
      <div className="flex-1 overflow-y-auto thin-scroll px-3 py-4">
        <div className="label-eyebrow px-2.5 mb-2">Workspace</div>
        <nav className="space-y-0.5">
          {mainItems.map((item) => {
            const Icon = item.icon;
            if (!item.active) return <LockedItem key={item.label} item={item} />;
            const selected =
              location.pathname === item.to ||
              (item.to === "/dashboard" && location.pathname === "/") ||
              (item.to === "/applications" && location.pathname.startsWith("/applications"));
            return (
              <NavLink
                key={item.label}
                to={item.to}
                data-testid={`nav-${item.label.toLowerCase()}`}
                className={cn(
                  "group flex items-center gap-2.5 rounded-md px-2.5 py-2 text-[13px] font-medium transition-colors",
                  selected
                    ? "bg-primary text-primary-foreground"
                    : "text-foreground/70 hover:bg-secondary hover:text-foreground"
                )}
              >
                <Icon className="h-[17px] w-[17px] shrink-0" strokeWidth={1.8} />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </nav>
      </div>
      <div className="border-t border-border px-3 py-3">
        <button
          data-testid="nav-settings"
          onClick={() => toast.info("Settings will be available in the full release.")}
          className="flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-[13px] font-medium text-muted-foreground/80 hover:bg-secondary transition-colors"
        >
          <Settings className="h-[17px] w-[17px]" strokeWidth={1.8} />
          <span>Settings</span>
        </button>
      </div>
    </aside>
  );
}
