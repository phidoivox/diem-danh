"use client";

import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import {
  User,
  UserRole,
  getToken,
  getMe,
  login as loginApi,
  logout as logoutApi,
} from "./http";

interface AuthContextType {
  user: User | null;
  token: string | null;
  role: UserRole | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (credentials: { user_code_or_email: string; password: string }) => Promise<User>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const initAuth = useCallback(async () => {
    try {
      const storedToken = getToken();
      if (!storedToken) {
        setIsLoading(false);
        return;
      }
      setToken(storedToken);
      const currentUser = await getMe();
      setUser(currentUser);
    } catch {
      logoutApi();
      setUser(null);
      setToken(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    initAuth();
  }, [initAuth]);

  const login = async (credentials: { user_code_or_email: string; password: string }): Promise<User> => {
    setIsLoading(true);
    try {
      const res = await loginApi(credentials.user_code_or_email, credentials.password);
      setToken(res.access_token);
      setUser(res.user);
      return res.user;
    } finally {
      setIsLoading(false);
    }
  };

  const logout = () => {
    logoutApi();
    setUser(null);
    setToken(null);
  };

  const refreshUser = async () => {
    try {
      const updated = await getMe();
      setUser(updated);
    } catch {
      logout();
    }
  };

  const role = user?.role || null;
  const isAuthenticated = !!user && !!token;

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        role,
        isLoading,
        isAuthenticated,
        login,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
