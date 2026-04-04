import { createContext, useContext, useEffect, useMemo, useState } from "react";

import { apiRequest } from "./api";

const AuthContext = createContext(null);

const STORAGE_KEYS = {
  token: "certi_nt.token",
  user: "certi_nt.user",
  setupToken: "certi_nt.setupToken",
};

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem(STORAGE_KEYS.token));
  const [user, setUser] = useState(() => {
    const raw = localStorage.getItem(STORAGE_KEYS.user);
    return raw ? JSON.parse(raw) : null;
  });
  const [setupToken, setSetupToken] = useState(() => localStorage.getItem(STORAGE_KEYS.setupToken));
  const [loading, setLoading] = useState(Boolean(token));

  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }

    let ignore = false;
    apiRequest("/auth/me", {}, token)
      .then((data) => {
        if (!ignore && data?.user) {
          setUser(data.user);
          localStorage.setItem(STORAGE_KEYS.user, JSON.stringify(data.user));
        }
      })
      .catch(() => {
        if (!ignore) {
          clearAuth();
        }
      })
      .finally(() => {
        if (!ignore) {
          setLoading(false);
        }
      });

    return () => {
      ignore = true;
    };
  }, [token]);

  function persistAuth(accessToken, currentUser) {
    setToken(accessToken);
    setUser(currentUser);
    localStorage.setItem(STORAGE_KEYS.token, accessToken);
    localStorage.setItem(STORAGE_KEYS.user, JSON.stringify(currentUser));
  }

  function clearAuth() {
    setToken(null);
    setUser(null);
    setSetupToken(null);
    localStorage.removeItem(STORAGE_KEYS.token);
    localStorage.removeItem(STORAGE_KEYS.user);
    localStorage.removeItem(STORAGE_KEYS.setupToken);
  }

  async function login(email, password) {
    const data = await apiRequest("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });

    if (data.requires_set_password) {
      setSetupToken(data.setup_token);
      localStorage.setItem(STORAGE_KEYS.setupToken, data.setup_token);
      return data;
    }

    if (data.access_token && data.user) {
      persistAuth(data.access_token, data.user);
      localStorage.removeItem(STORAGE_KEYS.setupToken);
      setSetupToken(null);
    }

    return data;
  }

  async function setPassword(newPassword) {
    const data = await apiRequest("/auth/set-password", {
      method: "POST",
      body: JSON.stringify({ setup_token: setupToken, new_password: newPassword }),
    });

    if (data.access_token && data.user) {
      persistAuth(data.access_token, data.user);
      localStorage.removeItem(STORAGE_KEYS.setupToken);
      setSetupToken(null);
    }
    return data;
  }

  async function changePassword(currentPassword, newPassword) {
    await apiRequest(
      "/auth/change-password",
      {
        method: "POST",
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      },
      token,
    );

    const me = await apiRequest("/auth/me", {}, token);
    if (me?.user) {
      setUser(me.user);
      localStorage.setItem(STORAGE_KEYS.user, JSON.stringify(me.user));
    }
  }

  async function logout() {
    if (token) {
      await apiRequest("/auth/logout", { method: "POST" }, token).catch(() => undefined);
    }
    clearAuth();
  }

  const value = useMemo(
    () => ({
      token,
      user,
      setupToken,
      loading,
      isAuthenticated: Boolean(token && user),
      login,
      setPassword,
      changePassword,
      logout,
      clearAuth,
      setUser,
    }),
    [loading, setupToken, token, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return value;
}
