import { Link } from "react-router";

export function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4">
      <h1 className="text-4xl font-bold text-gray-800">404</h1>
      <Link to="/" className="text-brand-600 hover:underline">Retour à l'accueil</Link>
    </div>
  );
}
