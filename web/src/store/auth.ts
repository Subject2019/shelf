/** 登录态：access token 只在内存，refresh token 持久化到 localStorage。 */

import { create } from "zustand";

import {
  getRefreshToken,
  onSessionExpired,
  refreshSession,
  setAccessToken,
  setRefreshToken,
} from "../api/client";
import { api } from "../api/endpoints";
import type { User } from "../api/types";

export type AuthStatus = "loading" | "authenticated" | "anonymous";

interface AuthState {
  user: User | null;
  status: AuthStatus;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  bootstrap: () => Promise<void>;
}

export const useAuth = create<AuthState>((set) => ({
  user: null,
  status: "loading",

  async bootstrap() {
    if (!getRefreshToken()) {
      set({ status: "anonymous", user: null });
      return;
    }
    const token = await refreshSession();
    if (!token) {
      set({ status: "anonymous", user: null });
      return;
    }
    try {
      const user = await api.me();
      set({ user, status: "authenticated" });
    } catch {
      set({ status: "anonymous", user: null });
    }
  },

  async login(username: string, password: string) {
    const data = await api.login(username, password);
    setAccessToken(data.access_token);
    setRefreshToken(data.refresh_token);
    set({ user: data.user, status: "authenticated" });
  },

  async logout() {
    const refreshToken = getRefreshToken();
    if (refreshToken) {
      try {
        await api.logout(refreshToken);
      } catch {
        // 网络异常也要允许本地退出
      }
    }
    setAccessToken(null);
    setRefreshToken(null);
    set({ user: null, status: "anonymous" });
  },
}));

// refresh token 被服务端判定失效时同步登录态，路由守卫据此跳转登录页
onSessionExpired(() => {
  useAuth.setState({ user: null, status: "anonymous" });
});
