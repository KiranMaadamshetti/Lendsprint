import { useNavigate } from "react-router-dom";
import { Search, Bell, HelpCircle, LogOut, ChevronDown } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

export function Header() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  const initials = (user?.name || "CA")
    .split(" ")
    .map((s) => s[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  return (
    <header className="fixed top-0 left-0 right-0 z-30 h-14 border-b border-border bg-card/90 backdrop-blur-md">
      <div className="flex h-full items-center gap-4 px-4 sm:px-5">
        {/* Wordmark */}
        <div
          className="flex items-center gap-2 cursor-pointer select-none"
          onClick={() => navigate("/dashboard")}
          data-testid="brand-logo"
        >
          <div className="grid h-7 w-7 place-items-center rounded-md bg-primary text-primary-foreground text-[13px] font-bold">
            L
          </div>
          <div className="leading-none">
            <div className="text-[14px] font-semibold tracking-tight text-foreground">
              LendSprint <span className="text-accent-foreground">AI</span>
            </div>
          </div>
        </div>

        <div className="mx-1 hidden md:block h-5 w-px bg-border" />
        <div className="hidden md:block text-[12px] text-muted-foreground truncate">
          Explainable AI credit decisioning for Indian NBFCs
        </div>

        <div className="flex-1" />

        {/* Global search */}
        <div className="hidden sm:flex items-center gap-2 h-9 rounded-md border border-border bg-secondary/60 px-3 text-muted-foreground w-[220px]">
          <Search className="h-4 w-4" strokeWidth={1.8} />
          <input
            data-testid="global-search"
            placeholder="Search"
            className="flex-1 bg-transparent text-[13px] text-foreground placeholder:text-muted-foreground focus:outline-none"
            readOnly
          />
          <span className="text-[11px] rounded border border-border bg-card px-1.5 py-0.5">⌘K</span>
        </div>

        <button className="grid h-9 w-9 place-items-center rounded-md text-muted-foreground hover:bg-secondary transition-colors" data-testid="notifications-btn">
          <Bell className="h-[18px] w-[18px]" strokeWidth={1.8} />
        </button>
        <button className="grid h-9 w-9 place-items-center rounded-md text-muted-foreground hover:bg-secondary transition-colors" data-testid="help-btn">
          <HelpCircle className="h-[18px] w-[18px]" strokeWidth={1.8} />
        </button>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button className="flex items-center gap-2 rounded-md pl-1 pr-2 py-1 hover:bg-secondary transition-colors" data-testid="user-menu">
              <span className="grid h-7 w-7 place-items-center rounded-full bg-primary text-primary-foreground text-[11px] font-semibold">
                {initials}
              </span>
              <ChevronDown className="h-4 w-4 text-muted-foreground" strokeWidth={1.8} />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuLabel>
              <div className="text-[13px] font-medium text-foreground">{user?.name}</div>
              <div className="text-[12px] text-muted-foreground font-normal truncate">{user?.email}</div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem data-testid="logout-btn" onClick={() => { signOut(); navigate("/login"); }}>
              <LogOut className="mr-2 h-4 w-4" /> Sign out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
