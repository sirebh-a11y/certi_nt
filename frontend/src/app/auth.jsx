import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

import { apiRequest, onAuthExpired } from "./api";

const AuthContext = createContext(null);

const STORAGE_KEYS = {
  token: "certi_nt.token",
  user: "certi_nt.user",
  setupToken: "certi_nt.setupToken",
  acquisitionAiFlowActive: "certi_nt.acquisitionAiFlowActive",
};

const SESSION_RENEW_INTERVAL_MS = 15 * 60 * 1000;
const SESSION_RENEW_CHECK_MS = 60 * 1000;
const USER_ACTIVITY_WINDOW_MS = 20 * 60 * 1000;

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem(STORAGE_KEYS.token));
  const [user, setUser] = useState(() => {
    const raw = localStorage.getItem(STORAGE_KEYS.user);
    return raw ? JSON.parse(raw) : null;
  });
  const [setupToken, setSetupToken] = useState(() => localStorage.getItem(STORAGE_KEYS.setupToken));
  const [loading, setLoading] = useState(Boolean(token));
  const [acquisitionAiFlowActive, setAcquisitionAiFlowActiveState] = useState(
    () => localStorage.getItem(STORAGE_KEYS.acquisitionAiFlowActive) === "1",
  );
  const lastUserActivityRef = useRef(Date.now());
  const lastRenewAttemptRef = useRef(Date.now());
  const lastAcquisitionAiFlowSignalRef = useRef(0);
  const renewInProgressRef = useRef(false);

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

  const persistAuth = useCallback((accessToken, currentUser) => {
    setToken(accessToken);
    setUser(currentUser);
    localStorage.setItem(STORAGE_KEYS.token, accessToken);
    localStorage.setItem(STORAGE_KEYS.user, JSON.stringify(currentUser));
  }, []);

  const clearAuth = useCallback(() => {
    setToken(null);
    setUser(null);
    setSetupToken(null);
    setAcquisitionAiFlowActiveState(false);
    localStorage.removeItem(STORAGE_KEYS.token);
    localStorage.removeItem(STORAGE_KEYS.user);
    localStorage.removeItem(STORAGE_KEYS.setupToken);
    localStorage.removeItem(STORAGE_KEYS.acquisitionAiFlowActive);
  }, []);

  useEffect(() => onAuthExpired(clearAuth), [clearAuth]);

  const setAcquisitionAiFlowActive = useCallback((active) => {
    setAcquisitionAiFlowActiveState(Boolean(active));
    if (active) {
      lastAcquisitionAiFlowSignalRef.current = Date.now();
      localStorage.setItem(STORAGE_KEYS.acquisitionAiFlowActive, "1");
    } else {
      lastAcquisitionAiFlowSignalRef.current = 0;
      localStorage.removeItem(STORAGE_KEYS.acquisitionAiFlowActive);
    }
  }, []);

  const renewSession = useCallback(async () => {
    if (!token || renewInProgressRef.current) {
      return null;
    }
    renewInProgressRef.current = true;
    try {
      const data = await apiRequest("/auth/renew-session", { method: "POST" }, token);
      if (data?.access_token && data?.user) {
        persistAuth(data.access_token, data.user);
      }
      return data;
    } finally {
      renewInProgressRef.current = false;
    }
  }, [persistAuth, token]);

  useEffect(() => {
    const markActivity = () => {
      lastUserActivityRef.current = Date.now();
    };
    const activityEvents = ["pointerdown", "keydown", "input", "scroll", "focus"];
    activityEvents.forEach((eventName) => window.addEventListener(eventName, markActivity, { passive: true }));
    document.addEventListener("visibilitychange", markActivity);
    return () => {
      activityEvents.forEach((eventName) => window.removeEventListener(eventName, markActivity));
      document.removeEventListener("visibilitychange", markActivity);
    };
  }, []);

  useEffect(() => {
    if (!token || !user) {
      return undefined;
    }

    const intervalId = window.setInterval(async () => {
      const now = Date.now();
      const recentUserActivity = now - lastUserActivityRef.current <= USER_ACTIVITY_WINDOW_MS;
      const shouldKeepAlive = recentUserActivity || acquisitionAiFlowActive;
      if (!shouldKeepAlive || now - lastRenewAttemptRef.current < SESSION_RENEW_INTERVAL_MS) {
        return;
      }
      lastRenewAttemptRef.current = now;
      await renewSession().catch(() => undefined);
    }, SESSION_RENEW_CHECK_MS);

    return () => window.clearInterval(intervalId);
  }, [acquisitionAiFlowActive, renewSession, token, user]);

  useEffect(() => {
    if (!token || !acquisitionAiFlowActive) {
      return undefined;
    }

    const intervalId = window.setInterval(async () => {
      try {
        const activeRun = await apiRequest("/acquisition/automation/runs/active", {}, token);
        const recentUploadPageSignal = Date.now() - lastAcquisitionAiFlowSignalRef.current <= 90 * 1000;
        if (!activeRun && !recentUploadPageSignal) {
          setAcquisitionAiFlowActive(false);
        }
      } catch {
        // apiRequest already handles auth expiration globally. Keep the flag if the check fails for a transient reason.
      }
    }, SESSION_RENEW_CHECK_MS);

    return () => window.clearInterval(intervalId);
  }, [acquisitionAiFlowActive, setAcquisitionAiFlowActive, token]);

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
      renewSession,
      acquisitionAiFlowActive,
      setAcquisitionAiFlowActive,
    }),
    [acquisitionAiFlowActive, changePassword, clearAuth, loading, login, logout, renewSession, setAcquisitionAiFlowActive, setPassword, setupToken, token, user],
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
