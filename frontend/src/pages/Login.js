import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ShieldCheck, Loader2 } from "lucide-react";

export default function Login() {
  const { signIn, user } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("kiranmaadamshetti@gmail.com");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  if (user) navigate("/dashboard", { replace: true });

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await signIn(email, password);
      navigate("/dashboard", { replace: true });
    } catch (err) {
      setError(apiErrorMessage(err, "Unable to sign in"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-2 bg-background">
      {/* Brand panel */}
      <div className="hidden lg:flex flex-col justify-between bg-primary text-primary-foreground p-12">
        <div className="flex items-center gap-2.5">
          <div className="grid h-9 w-9 place-items-center rounded-md bg-white/10 text-[16px] font-bold">L</div>
          <span className="text-[16px] font-semibold tracking-tight">LendSprint AI</span>
        </div>
        <div className="max-w-md">
          <h1 className="text-3xl font-semibold leading-tight tracking-tight">
            Explainable credit decisioning for mid-market NBFCs.
          </h1>
          <p className="mt-4 text-[14px] text-primary-foreground/70 leading-relaxed">
            Move from borrower application to an auditable, explainable credit decision — with reason codes,
            cash-flow evidence and an AI-drafted credit memo, all recorded in a traceable audit trail.
          </p>
          <div className="mt-8 flex items-center gap-2 text-[12px] text-primary-foreground/60">
            <ShieldCheck className="h-4 w-4" strokeWidth={1.8} />
            Designed for traceable, defensible credit decisions.
          </div>
        </div>
        <div className="text-[12px] text-primary-foreground/50">© 2026 LendSprint AI · Demonstration environment</div>
      </div>

      {/* Form */}
      <div className="flex items-center justify-center p-6 sm:p-12">
        <div className="w-full max-w-sm">
          <div className="lg:hidden flex items-center gap-2.5 mb-8">
            <div className="grid h-8 w-8 place-items-center rounded-md bg-primary text-primary-foreground text-[14px] font-bold">L</div>
            <span className="text-[15px] font-semibold">LendSprint AI</span>
          </div>
          <h2 className="text-[22px] font-semibold tracking-tight text-foreground">Sign in</h2>
          <p className="mt-1 text-[13px] text-muted-foreground">Access the credit operations workspace.</p>

          <form onSubmit={submit} className="mt-7 space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="email" className="text-[13px]">Email</Label>
              <Input
                id="email"
                data-testid="login-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="username"
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password" className="text-[13px]">Password</Label>
              <Input
                id="password"
                data-testid="login-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                placeholder="Enter your password"
                required
              />
            </div>
            {error && (
              <div data-testid="login-error" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-700">
                {error}
              </div>
            )}
            <Button data-testid="login-submit" type="submit" disabled={loading} className="w-full">
              {loading ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Signing in…</> : "Sign in"}
            </Button>
          </form>
          <p className="mt-5 text-[12px] text-muted-foreground">
            Demo access uses the account provisioned for this environment.
          </p>
        </div>
      </div>
    </div>
  );
}
