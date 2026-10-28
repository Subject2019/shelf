/** 与 docs/API.md 对齐的 DTO。字段名保持下划线，避免手工映射出错。 */

export interface Health {
  status: string;
  version: string;
  db: string;
  ffmpeg: boolean;
  libraries: number;
  books: number;
  uptime_sec: number;
}

export interface ProgressBrief {
  position_sec: number;
  percent: number;
  is_finished: boolean;
}

/** 进度回溯点：每本书最多 5 个「位置差异明显」的快照。 */
export interface ProgressHistoryItem {
  id: number;
  position_sec: number;
  track_id: number | null;
  device_id: string | null;
  created_at: number;
}

export interface ProgressHistoryList {
  items: ProgressHistoryItem[];
}

/** GET /progress/recent 的一条：某本书的最近进度（一个账号一本书只有一条）。 */
export interface RecentProgress {
  book_id: number;
  title: string;
  author: string | null;
  cover_url: string | null;
  position_sec: number;
  total_duration_sec: number;
  percent: number;
  updated_at: number;
  device_id: string | null;
}

export interface RecentProgressList {
  items: RecentProgress[];
}

/** 三级角色：管理员 / 上传者 / 听众。 */
export type UserRole = "admin" | "editor" | "listener";

export interface User {
  id: number;
  username: string;
  display_name: string | null;
  role: UserRole;
  libraries: number[];
  created_at: number;
}

/** 管理员视角的用户（多出启用状态与最近登录）。 */
export interface UserAdmin extends User {
  is_active: boolean;
  last_login_at: number | null;
}

export interface UserAdminList {
  items: UserAdmin[];
  total: number;
  page: number;
  page_size: number;
}

export interface UserCreatePayload {
  username: string;
  password: string;
  display_name?: string | null;
  role?: Exclude<UserRole, "admin">;
  library_ids?: number[];
}

export interface UserUpdatePayload {
  display_name?: string | null;
  role?: Exclude<UserRole, "admin">;
  is_active?: boolean;
  password?: string;
  library_ids?: number[];
}

export interface Device {
  id: string;
  user_id: number;
  username: string | null;
  name: string | null;
  platform: string | null;
  app_version: string | null;
  os: string | null;
  form_factor: string | null;
  screen: string | null;
  user_agent: string | null;
  created_at: number | null;
  last_seen_at: number | null;
  revoked_at: number | null;
  offline_at: number | null;
  online: boolean;
}

export interface DeviceList {
  items: Device[];
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  user: User;
}

export interface ScanBrief {
  status: string;
  finished_at: number | null;
}

export interface Library {
  id: number;
  name: string;
  root_path: string;
  enabled: boolean;
  book_count: number;
  total_duration_sec: number;
  last_scan_at: number | null;
  scan: ScanBrief | null;
}

export interface ScanTrigger {
  task_id: number;
  status: string;
}

export interface ScanStatus {
  task_id: number;
  status: string;
  started_at: number | null;
  finished_at: number | null;
  files_seen: number;
  files_added: number;
  files_updated: number;
  files_removed: number;
  books_created: number;
  books_updated: number;
  error: string | null;
}

export interface LibraryList {
  items: Library[];
  total: number;
  page: number;
  page_size: number;
}

export interface Book {
  id: number;
  library_id: number;
  title: string;
  author: string | null;
  narrator: string | null;
  series_name: string | null;
  series_index: number | null;
  language: string | null;
  cover_url: string | null;
  /** 手工封面的上传者；扫描抽取的封面为 null */
  cover_uploaded_by: number | null;
  manual_override: boolean;
  /** 管理员在书架中隐藏（普通用户不可见） */
  hidden: boolean;
  total_duration_sec: number;
  /** 跳过片头/片尾（秒），0 表示不跳 */
  intro_sec: number;
  outro_sec: number;
  track_count: number;
  size_bytes: number;
  chapter_source: string | null;
  added_at: number;
  progress: ProgressBrief | null;
}

export interface BookList {
  items: Book[];
  total: number;
  page: number;
  page_size: number;
}

export interface SeriesSummary {
  name: string;
  book_count: number;
  total_duration_sec: number;
  cover_book_id: number | null;
  cover_url: string | null;
  latest_added_at: number;
}

export interface SeriesList {
  items: SeriesSummary[];
}

export interface AuthorSummary {
  name: string;
  book_count: number;
  total_duration_sec: number;
  cover_book_id: number | null;
  cover_url: string | null;
  latest_added_at: number;
}

export interface AuthorList {
  items: AuthorSummary[];
}

export interface Track {
  id: number;
  track_no: number;
  disc_no: number;
  title: string | null;
  duration_sec: number;
  format: string | null;
  bitrate: number | null;
  stream_url: string;
}

export interface Chapter {
  id: number;
  idx: number;
  title: string;
  start_sec: number;
  end_sec: number | null;
  track_id: number;
}

export interface BookDetail extends Book {
  subtitle: string | null;
  publisher: string | null;
  publish_year: number | null;
  description: string | null;
  rel_dir: string | null;
  is_missing: boolean;
  updated_at: number;
  tracks: Track[];
  chapters: Chapter[] | null;
}

export interface Bookmark {
  id: number;
  book_id: number;
  position_sec: number;
  track_id: number | null;
  note: string | null;
  created_at: number;
}

export interface BookmarkCreate {
  position_sec: number;
  track_id?: number | null;
  note?: string | null;
}

export interface ChapterList {
  items: Chapter[];
  total: number;
  page: number;
  page_size: number;
}

export interface BookUpdatePayload {
  title?: string;
  subtitle?: string | null;
  author?: string | null;
  narrator?: string | null;
  publisher?: string | null;
  publish_year?: number | null;
  language?: string | null;
  series_name?: string | null;
  series_index?: number | null;
  description?: string | null;
  intro_sec?: number;
  outro_sec?: number;
  hidden?: boolean;
}

export interface PlayToken {
  token: string;
  expires_in: number;
  expires_at: number;
}

export interface ProgressPut {
  track_id?: number | null;
  position_sec: number;
  playback_rate?: number;
  device_id?: string;
  client_updated_at: number;
  explicit_seek?: boolean;
  finished?: boolean;
}

export interface ProgressPutResult {
  book_id: number;
  position_sec: number;
  track_id: number | null;
  accepted: boolean;
  is_finished: boolean;
  updated_at: number;
}

export interface ApiErrorBody {
  error?: {
    code?: string;
    message?: string;
    details?: unknown;
  };
}

/** GET /stats：今日 / 累计 / 连续天数 + 最近 N 天明细。 */
export interface DayStat {
  day: string;
  seconds: number;
}

export interface ListeningStats {
  today_sec: number;
  total_sec: number;
  streak_days: number;
  days: DayStat[];
}
