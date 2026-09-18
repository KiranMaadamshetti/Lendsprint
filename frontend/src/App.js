import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { AppShell } from "@/components/layout/AppShell";
import Login from "@/pages/Login";
import Dashboard from "@/pages/Dashboard";
import NewApplication from "@/pages/NewApplication";
import ApplicationDetail from "@/pages/ApplicationDetail";
import Reports from "@/pages/Reports";
import CreditPolicy from "@/pages/CreditPolicy";
import PolicyWizard from "@/pages/PolicyWizard";

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading || user === null) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="text-sm text-muted-foreground">Loading LendSprint AI…</div>
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  return <AppShell>{children}</AppShell>;
}

function App() {
  return (
    <div className="App">
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
            <Route path="/applications" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
            <Route path="/applications/new" element={<ProtectedRoute><NewApplication /></ProtectedRoute>} />
            <Route path="/applications/:id" element={<ProtectedRoute><ApplicationDetail /></ProtectedRoute>} />
            <Route path="/reports" element={<ProtectedRoute><Reports /></ProtectedRoute>} />
            <Route path="/credit-policy" element={<ProtectedRoute><CreditPolicy /></ProtectedRoute>} />
            <Route path="/credit-policy/wizard" element={<ProtectedRoute><PolicyWizard /></ProtectedRoute>} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </BrowserRouter>
        <Toaster position="top-right" richColors />
      </AuthProvider>
    </div>
  );
}

export default App;
