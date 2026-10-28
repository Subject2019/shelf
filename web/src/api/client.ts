/** fetch 封装：Bearer、401 自动 refresh 并重试一次、统一错误类型。 */

import type { ApiErrorBody, TokenResponse } from "./types";

const API_BASE = "/api/v1";
const REFRESH_KEY = "echoshelf.refresh_token";

let accessToken: string | null = null;
let refreshInFlight: Promise<string | null> | null = null;
let onRefreshed: ((access: string) => void) | null = null;
let onExpired: (() => void) | null = null;

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

export function getAccessToken(): string | null {
  return accessToken;
}

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_KEY);
}

export function setRefreshToken(token: string | null): void {
  if (token) {
    localStorage.setItem(REFRESH_KEY, token);
  } else {
    localStorage.removeItem(REFRESH_KEY);
  }
}

export function onSessionRefreshed(callback: ((access: string) => void) | null): void {
  onRefreshed = callback;
}

/** refresh token 明确失效（401）时通知上层退回未登录，网络异常不触发。 */
export function onSessionExpired(callback: (() => void) | null): void {
  onExpired = callback;
}

/** 用 refresh token 换新的 access；并发调用会合并成一次请求。 */
export function refreshSession(): Promise<string | null> {
  if (refreshInFlight) {
    return refreshInFlight;
  }
  const refreshToken = getRefreshToken();
  if (!refreshToken) {
    return Promise.resolve(null);
  }

  refreshInFlight = (async () => {
    try {
      const response = await fetch(`${API_BASE}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
      if (!response.ok) {
        setRefreshToken(null);
        setAccessToken(null);
        onExpired?.();
        return null;
      }
      const data = (await response.json()) as TokenResponse;
      setAccessToken(data.access_token);
      setRefreshToken(data.refresh_token);
      onRefreshed?.(data.access_token);
      return data.access_token;
    } catch {
      return null;
    }
  })().finally(() => {
    refreshInFlight = null;
  });

  return refreshInFlight;
}

export interface RequestOptions extends RequestInit {
  /** 匿名请求不带 token，也不触发 401 刷新 */
  anonymous?: boolean;
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { anonymous = false, headers, ...rest } = options;
  const requestHeaders = new Headers(headers);
  // FormData 必须让浏览器自己带 boundary，不能手写 Content-Type
  if (rest.body && !(rest.body instanceof FormData) && !requestHeaders.has("Content-Type")) {
    requestHeaders.set("Content-Type", "application/json");
  }
  if (!anonymous && accessToken) {
    requestHeaders.set("Authorization", `Bearer ${accessToken}`);
  }

  const response = await fetch(`${API_BASE}${path}`, { ...rest, headers: requestHeaders });

  if (response.status === 401 && !anonymous) {
    const refreshed = await refreshSession();
    if (refreshed) {
      const retryHeaders = new Headers(requestHeaders);
      retryHeaders.set("Authorization", `Bearer ${refreshed}`);
      return handleResponse<T>(
        await fetch(`${API_BASE}${path}`, { ...rest, headers: retryHeaders }),
      );
    }
  }

  return handleResponse<T>(response);
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (response.status === 204) {
    return undefined as T;
  }

  const isJson = (response.headers.get("content-type") ?? "").includes("application/json");

  if (!response.ok) {
    if (isJson) {
      const body = (await response.json()) as ApiErrorBody;
      throw new ApiError(
        response.status,
        body.error?.code ?? "error",
        body.error?.message ?? "请求失败",
      );
    }
    throw new ApiError(response.status, "error", `请求失败（${response.status}）`);
  }

  if (!isJson) {
    return (await response.text()) as unknown as T;
  }
  return (await response.json()) as T;
}
