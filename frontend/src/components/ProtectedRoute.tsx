import { Navigate, Outlet, useLocation } from "react-router";

import { useMe } from "../api/auth";
import { useAuth } from "../auth/AuthContext";

export function ProtectedRoute() {
  const { token, signOut } = useAuth();
  const location = useLocation();
  const me = useMe(token !== null);

  if (!token) return <Navigate to="/login" replace state={{ from: location.pathname }} />;

  if (me.isPending) {
    return (
      <div className="grid min-h-screen place-items-center text-sm text-slate-500">Loading…</div>
    );
  }

  if (me.isError) {
    return (
      <div className="grid min-h-screen place-items-center">
        <div className="space-y-3 text-center text-sm">
          <p className="text-slate-700">Couldn't load your account: {me.error.message}</p>
          <button onClick={signOut} className="text-indigo-600 hover:underline">
            Back to sign in
          </button>
        </div>
      </div>
    );
  }

  return <Outlet />;
}
