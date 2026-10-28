import { Route, Routes } from "react-router-dom";

import RequireAuth from "./components/auth/RequireAuth";
import AppShell from "./components/layout/AppShell";
import BookDetail from "./pages/BookDetail";
import Home from "./pages/Home";
import Authors from "./pages/Authors";
import Library from "./pages/Library";
import Login from "./pages/Login";
import Placeholder from "./pages/Placeholder";
import PlayerPage from "./pages/PlayerPage";
import Search from "./pages/Search";
import Settings from "./pages/Settings";

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Home />} />
        <Route path="login" element={<Login />} />

        {/* 需要登录的页面 */}
        <Route element={<RequireAuth />}>
          <Route path="library" element={<Library />} />
          <Route path="authors" element={<Authors />} />
          <Route path="player" element={<PlayerPage />} />
          <Route path="search" element={<Search />} />
          <Route path="books/:bookId" element={<BookDetail />} />
          <Route
            path="collections"
            element={
              <Placeholder title="书单" description="自定义书单将在书籍与播放链路完成后排期。" />
            }
          />
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
