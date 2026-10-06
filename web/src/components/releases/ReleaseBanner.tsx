import { useState } from "react";
import { Link } from "react-router";
import { useUnreadReleases, useMarkReleaseRead } from "../../hooks/useReleases";

export function ReleaseBanner() {
  const { data: unread } = useUnreadReleases();
  const markRead = useMarkReleaseRead();
  const [open, setOpen] = useState(true);

  if (!unread?.length || !open) return null;

  const latest = unread[0];
  const remaining = unread.length - 1;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setOpen(false)}>
      <div className="mx-4 max-w-md rounded-xl bg-white p-6 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <h2 className="mb-1 text-lg font-bold text-brand-700">Nouveautés — v{latest.version}</h2>
        <p className="mb-3 text-xs text-gray-500">{latest.date}</p>
        <h3 className="mb-2 font-semibold">{latest.title}</h3>
        <ul className="mb-4 list-disc space-y-1 pl-5 text-sm text-gray-700">
          {latest.items.map((item, i) => <li key={i}>{item}</li>)}
        </ul>
        {remaining > 0 && (
          <p className="mb-3 text-xs text-gray-400">
            +{remaining} autre(s) version(s) non lue(s).{" "}
            <Link to="/releases" className="text-brand-600 hover:underline" onClick={() => setOpen(false)}>Voir l'historique</Link>
          </p>
        )}
        <button
          className="w-full rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700"
          onClick={async () => { await markRead.mutateAsync(latest.version); setOpen(false); }}
        >
          J'ai lu
        </button>
      </div>
    </div>
  );
}
