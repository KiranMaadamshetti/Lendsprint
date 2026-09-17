import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { getMe, login as apiLogin, setToken, clearToken, getToken } from "@/lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null); // null = checking, false = unauth, object = authed
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const boot = async () => {
      if (!getToken()) {
        setUser(false);
        setLoading(false);
        return;
      }
      try {
        const me = await getMe();
        setUser(me);
      } catch {
        clearToken();
        setUser(false);
      } finally {
        setLoading(false);
      }
    };
    boot();
  }, []);

  const signIn = useCallback(async (email, password) => {
    const data = await apiLogin(email, password);
    setToken(data.token);
    setUser(data.user);
    return data.user;
  }, []);

  const signOut = useCallback(() => {
    clearToken();
    setUser(false);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, signIn, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
