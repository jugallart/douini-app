import { ReactNode } from "react";
import { Link, useLocation } from "react-router";
import { useAuth } from "../../hooks/useAuth";

const NAV = [
  { to: "/", label: "Dashboard" },
  { to: "/plan", label: "Plan" },
  { to: "/profile", label: "Profil" },
  { to: "/pantheon", label: "Palmarès" },
  { to: "/settings", label: "Réglages" },
];

export function AppShell({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const { pathname } = useLocation();

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
          <Link to="/" className="text-lg font-bold text-brand-600">Douini Run</Link>
          <nav className="flex gap-1">
            {NAV.map((item) => (
              <Link
                key={item.to}
                to={item.to}
                className={`rounded-lg px-3 py-1.5 text-sm font-medium ${
                  pathname === item.to ? "bg-brand-50 text-brand-700" : "text-gray-600 hover:bg-gray-100"
                }`}
              >
                {item.label}
              </Link>
            ))}
          </nav>
          <div className="flex items-center gap-3">
            {user && <span className="text-sm text-gray-500">{user.email}</span>}
            <button onClick={logout} className="text-sm text-gray-500 hover:text-red-600">Déconnexion</button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-6">{children}</main>
    </div>
  );
}
