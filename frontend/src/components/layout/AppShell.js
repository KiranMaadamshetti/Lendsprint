import { Sidebar } from "@/components/layout/Sidebar";
import { Header } from "@/components/layout/Header";

export function AppShell({ children }) {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <Header />
      <div className="flex">
        <Sidebar />
        <main className="flex-1 min-w-0 lg:ml-[232px] pt-14">
          <div className="mx-auto max-w-[1320px] px-5 sm:px-7 py-6">{children}</div>
        </main>
      </div>
    </div>
  );
}
