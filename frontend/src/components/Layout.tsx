import { NavLink, Outlet } from "react-router";

import { useMe } from "../api/auth";
import { useQueueEvents } from "../api/useQueueEvents";
import { useAuth } from "../auth/AuthContext";

const NAV = [
  { to: "/queue", label: "Review queue" },
  { to: "/posts", label: "Posts" },
  { to: "/sources", label: "Sources" },
  { to: "/templates", label: "Templates" },
  { to: "/activity", label: "Activity" },
  { to: "/settings", label: "Settings" },
];

export function Layout() {
  const { signOut } = useAuth();
  const { data: user } = useMe(true);
  useQueueEvents();

  return (
    <div className="flex min-h-screen bg-slate-50 text-slate-900">
      <aside className="flex w-56 shrink-0 flex-col border-r border-slate-200 bg-white">
        <div className="px-5 py-4 text-sm font-semibold tracking-tight">News Comment Assistant</div>
        <nav className="flex flex-1 flex-col gap-0.5 px-2">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `rounded-md px-3 py-2 text-sm ${
                  isActive
                    ? "bg-indigo-50 font-medium text-indigo-700"
                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-slate-200 px-5 py-4 text-sm">
          <div className="truncate font-medium" title={user?.email}>
            {user?.email}
          </div>
          <div className="text-xs text-slate-500 capitalize">{user?.role}</div>
          <button onClick={signOut} className="mt-2 text-xs text-slate-500 hover:text-slate-900">
            Sign out
          </button>
        </div>
      </aside>
      <main className="min-w-0 flex-1 p-8">
        <Outlet />
      </main>
    </div>
  );
}
