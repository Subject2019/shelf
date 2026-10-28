/** 按 docs/API.md 组织的接口函数。 */

import { describeDevice } from "../lib/device";
import { request } from "./client";
import type {
  Book,
  BookDetail,
  BookList,
  BookUpdatePayload,
  Bookmark,
  BookmarkCreate,
  ChapterList,
  Device,
  DeviceList,
  Health,
  Library,
  LibraryList,
  PlayToken,
  ScanStatus,
  ScanTrigger,
  AuthorList,
  ListeningStats,
  SeriesList,
  ProgressHistoryList,
  ProgressPut,
  ProgressPutResult,
  RecentProgressList,
  TokenResponse,
  User,
  UserAdmin,
  UserAdminList,
  UserCreatePayload,
  UserUpdatePayload,
} from "./types";

const DEVICE_KEY = "echoshelf.device_id";

export function deviceId(): string {
  let id = localStorage.getItem(DEVICE_KEY);
  if (!id) {
    id = `web-${Math.random().toString(36).slice(2, 10)}`;
    localStorage.setItem(DEVICE_KEY, id);
  }
  return id;
}

export interface BookQuery {
  library_id?: number;
  q?: string;
  author?: string;
  series?: string;
  sort?:
    | "added_desc"
    | "title_asc"
    | "author_asc"
    | "duration_desc"
    | "progress_desc"
    | "series_asc";
  filter?: "all" | "in_progress" | "finished" | "unplayed" | "downloaded";
  page?: number;
  page_size?: number;
  /** 仅管理员：包含已隐藏的书 */
  include_hidden?: boolean;
}

export type BookSort = NonNullable<BookQuery["sort"]>;
export type BookFilter = NonNullable<BookQuery["filter"]>;

function toQuery(params: BookQuery): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === "") continue;
    search.set(key, String(value));
  }
  const query = search.toString();
  return query ? `?${query}` : "";
}

export const api = {
  health: () => request<Health>("/health", { anonymous: true }),

  login: (username: string, password: string) =>
    request<TokenResponse>("/auth/login", {
      method: "POST",
      anonymous: true,
      body: JSON.stringify({
        username,
        password,
        device: { id: deviceId(), ...describeDevice() },
      }),
    }),

  logout: (refreshToken: string) =>
    request<void>("/auth/logout", {
      method: "POST",
      anonymous: true,
      body: JSON.stringify({ refresh_token: refreshToken }),
    }),

  me: () => request<User>("/me"),

  changePassword: (payload: { old_password: string; new_password: string }) =>
    request<void>("/me/password", { method: "PATCH", body: JSON.stringify(payload) }),

  libraries: () => request<LibraryList>("/libraries"),

  createLibrary: (payload: { name: string; root_path: string }) =>
    request<Library>("/libraries", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  updateLibrary: (libraryId: number, payload: { name?: string; enabled?: boolean }) =>
    request<Library>(`/libraries/${libraryId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  deleteLibrary: (libraryId: number) =>
    request<void>(`/libraries/${libraryId}`, { method: "DELETE" }),

  scanLibrary: (libraryId: number) =>
    request<ScanTrigger>(`/libraries/${libraryId}/scan`, { method: "POST" }),

  scanStatus: (libraryId: number) =>
    request<ScanStatus>(`/libraries/${libraryId}/scan/status`),

  books: (query: BookQuery = {}) => request<BookList>(`/books${toQuery(query)}`),

  series: () => request<SeriesList>("/series"),

  authors: () => request<AuthorList>("/authors"),

  /** 收听统计（按天累计，来自 PUT /progress 的自然播放推进）。 */
  stats: (days = 7) => request<ListeningStats>(`/stats?days=${days}`),

  bookDetail: (bookId: number) => request<BookDetail>(`/books/${bookId}`),

  /** 详情接口对 >500 章的书会省略 chapters，这里兜底拉取。 */
  chapters: (bookId: number, page = 1, pageSize = 500) =>
    request<ChapterList>(
      `/books/${bookId}/chapters?page=${page}&page_size=${pageSize}`,
    ),

  /** <audio> 无法自定义请求头，用它换一个绑定本书的短时流令牌。 */
  playToken: (bookId: number) =>
    request<PlayToken>(`/books/${bookId}/play-token`, { method: "POST" }),

  putProgress: (bookId: number, payload: ProgressPut) =>
    request<ProgressPutResult>(`/progress/${bookId}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),

  /** 该账号在这本书上的进度回溯点（最多 5 条，新→旧）。 */
  progressHistory: (bookId: number) =>
    request<ProgressHistoryList>(`/progress/${bookId}/history`),

  /** 该账号最近的收听记录（一个账号一本书一条），用于跨设备接续。 */
  recentProgress: (limit = 5) =>
    request<RecentProgressList>(`/progress/recent?limit=${limit}`),

  updateBook: (bookId: number, payload: BookUpdatePayload) =>
    request<Book>(`/books/${bookId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  resetBookMetadata: (bookId: number) =>
    request<Book>(`/books/${bookId}/metadata/reset`, { method: "POST" }),

  uploadCover: (bookId: number, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<Book>(`/books/${bookId}/cover`, { method: "PUT", body: form });
  },

  deleteCover: (bookId: number) =>
    request<Book>(`/books/${bookId}/cover`, { method: "DELETE" }),

  bookmarks: (bookId: number) =>
    request<Bookmark[]>(`/books/${bookId}/bookmarks`),

  createBookmark: (bookId: number, payload: BookmarkCreate) =>
    request<Bookmark>(`/books/${bookId}/bookmarks`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  updateBookmark: (bookmarkId: number, note: string | null) =>
    request<Bookmark>(`/bookmarks/${bookmarkId}`, {
      method: "PATCH",
      body: JSON.stringify({ note }),
    }),

  deleteBookmark: (bookmarkId: number) =>
    request<void>(`/bookmarks/${bookmarkId}`, { method: "DELETE" }),

  // ---- 用户管理（管理员） ----

  users: () => request<UserAdminList>("/users"),

  createUser: (payload: UserCreatePayload) =>
    request<UserAdmin>("/users", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  updateUser: (userId: number, payload: UserUpdatePayload) =>
    request<UserAdmin>(`/users/${userId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  deleteUser: (userId: number) =>
    request<void>(`/users/${userId}`, { method: "DELETE" }),

  // ---- 设备 ----

  devices: (all = false) =>
    request<DeviceList>(`/devices${all ? "?all=true" : ""}`),

  renameDevice: (deviceId: string, name: string) =>
    request<Device>(`/devices/${deviceId}`, {
      method: "PATCH",
      body: JSON.stringify({ name }),
    }),

  kickDevice: (deviceId: string) =>
    request<void>(`/devices/${deviceId}`, { method: "DELETE" }),

  /** 在线心跳 / 主动下线；keepalive 保证页面关闭时请求仍能发出 */
  setPresence: (deviceId: string, online: boolean) =>
    request<Device>(`/devices/${deviceId}/presence`, {
      method: "POST",
      body: JSON.stringify({ online }),
      keepalive: true,
    }),
};
