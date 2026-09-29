import { Link } from "react-router";

export function GarminBanner({ connected }: { connected: boolean }) {
  if (connected) return null;
  return (
    <Link to="/settings" className="block rounded-lg border border-yellow-200 bg-yellow-50 px-4 py-3 text-sm text-yellow-800">
      Garmin non connecté — Cliquez ici pour synchroniser vos séances vers votre montre.
    </Link>
  );
}
