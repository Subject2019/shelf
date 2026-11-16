import { Route, Routes } from "react-router-dom";

import RequireAuth from "./components/auth/RequireAuth";
import AppShell from "./components/layout/AppShell";
import { isOfflineMode } from "./lib/download";
import BookDetail from "./pages/BookDetail";
import Home from "./pages/Home";
import Authors from "./pages/Authors";
import CollectionDetail from "./pages/CollectionDetail";
import Collections from "./pages/Collections";
import Library from "./pages/Library";
import Login from "./pages/Login";
import Placeholder from "./pages/Placeholder";
import PlayerPage from "./pages/PlayerPage";
import Search from "./pages/Search";
import Settings from "./pages/Settings";

export default function App() {
  // Android 断网时，本机 127.0.0.1 服务同时提供静态 WebUI 和离线 /api/v1；
  // 因此这里仍走和在线完全相同的路由，只把无法离线支持的功能置灰。
  return (
    <Routes>
      <Route element={<AppShell offline={isOfflineMode()} />}>
        <Route index element={<Home />} />
        <Route path="login" element={<Login />} />

        {/* 需要登录的页面 */}
        <Route element={<RequireAuth />}>
          <Route path="library" element={<Library />} />
          <Route path="authors" element={<Authors />} />
          <Route path="player" element={<PlayerPage />} />
          <Route path="search" element={<Search />} />
          <Route path="books/:bookId" element={<BookDetail />} />
          <Route path="collections" element={<Collections />} />
          <Route path="collections/:collectionId" element={<CollectionDetail />} />
        </Route>

        <Route path="settings" element={<Settings />} />
        <Route
          path="*"
          element={<Placeholder title="页面不存在" description="检查地址是否正确，或返回首页。" />}
        />
      </Route>
    </Routes>
  );
}
