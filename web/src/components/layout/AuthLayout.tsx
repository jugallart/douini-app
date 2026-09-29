import { ReactNode } from "react";
import { Link } from "react-router";

export function AuthLayout({ children, title }: { children: ReactNode; title: string }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-md">
        <Link to="/" className="mb-8 block text-center">
          <span className="text-2xl font-bold text-brand-600">Douini Run</span>
        </Link>
        <div className="rounded-xl border border-gray-200 bg-white p-8 shadow-sm">
          <h1 className="mb-6 text-xl font-semibold text-gray-800">{title}</h1>
          {children}
        </div>
      </div>
    </div>
  );
}
