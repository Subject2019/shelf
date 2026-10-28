import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "../../store/auth";

/** 受保护路由：未登录跳 /login，并记住来源以便登录后回跳。 */
export default function RequireAuth() {
  const status = useAuth((state) => state.status);
  const location = useLocation();

  if (status === "loading") {
    return (
      <div className="py-24 text-center text-sm text-zinc-500">正在恢复登录状态…</div>
    );
  }

  if (status !== "authenticated") {
    return (
      <Navigate
        to="/login"
        replace
        state={{ from: `${location.pathname}${location.search}` }}
      />
    );
  }

  return <Outlet />;
}
