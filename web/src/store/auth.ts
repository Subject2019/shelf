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
import type { DefaultListener, User } from "../api/types";

export type AuthStatus = "loading" | "authenticated" | "anonymous";

// 退出后当前标签页不再自动登录，方便切换管理员账号；新标签页仍按默认逻辑处理。
const SKIP_AUTO_LOGIN_KEY = "echoshelf.skip_auto_login";

interface AuthState {
  user: User | null;
  status: AuthStatus;
  passwordlessUsers: DefaultListener[];
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  bootstrap: () => Promise<void>;
}

export const useAuth = create<AuthState>((set, get) => ({
  user: null,
  status: "loading",
  passwordlessUsers: [],

  async bootstrap() {
    let passwordlessUsers: DefaultListener[] = [];
    try {
      passwordlessUsers = (await api.passwordlessListeners()).items;
    } catch {
      // 免密账号列表查询失败时仍允许普通账号登录
    }
    set({ passwordlessUsers });

    if (!getRefreshToken()) {
      if (
        passwordlessUsers.length === 1 &&
        sessionStorage.getItem(SKIP_AUTO_LOGIN_KEY) !== "1"
      ) {
        try {
          await get().login(passwordlessUsers[0].username, "");
          return;
        } catch {
          // 自动登录失败时退回登录页，让用户手动选择/输入
        }
      }
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
    sessionStorage.removeItem(SKIP_AUTO_LOGIN_KEY);
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
    sessionStorage.setItem(SKIP_AUTO_LOGIN_KEY, "1");
    setAccessToken(null);
    setRefreshToken(null);
    set({ user: null, status: "anonymous" });
    try {
      const { items } = await api.passwordlessListeners();
      set({ passwordlessUsers: items });
    } catch {
      // 列表刷新失败时保留上一次结果，登录页仍可手动输入账号
    }
  },
}));

// refresh token 被服务端判定失效时同步登录态，路由守卫据此跳转登录页
onSessionExpired(() => {
  useAuth.setState({ user: null, status: "anonymous" });
});
