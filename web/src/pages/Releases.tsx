import { useReleases, useUnreadReleases, useMarkReleaseRead, useMarkAllReleasesRead } from "../hooks/useReleases";
import { AppShell } from "../components/layout/AppShell";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Alert } from "../components/ui/Alert";

export function Releases() {
  const { data: releases, isLoading, error } = useReleases();
  const { data: unread } = useUnreadReleases();
  const markRead = useMarkReleaseRead();
  const markAll = useMarkAllReleasesRead();
  const unreadVersions = new Set(unread?.map((r) => r.version));

  return (
    <AppShell>
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-bold">Les nouveautés</h1>
          {unreadVersions.size > 0 && (
            <Button variant="secondary" onClick={() => markAll.mutate()} loading={markAll.isPending}>
              Tout marquer comme lu
            </Button>
          )}
        </div>
        {error && <Alert>L'historique est momentanément indisponible.</Alert>}
        {!isLoading && !error && !releases?.length && <p className="text-sm text-gray-500">Les prochaines nouveautés seront publiées ici.</p>}
        {releases?.map((r) => (
          <Card key={r.version}>
            <div className="mb-2 flex items-center justify-between">
              <div>
                <h2 className="font-semibold">
                  v{r.version} — {r.title}
                  {unreadVersions.has(r.version) && <span className="ml-2 rounded bg-brand-600 px-2 py-0.5 text-xs text-white">Nouveau</span>}
                </h2>
                <p className="text-xs text-gray-500">{r.date}</p>
              </div>
              {unreadVersions.has(r.version) && (
                <Button variant="secondary" onClick={() => markRead.mutate(r.version)} disabled={markRead.isPending}>
                  Marquer comme lu
                </Button>
              )}
            </div>
            <ul className="list-disc space-y-1 pl-5 text-sm text-gray-700">
              {r.items.map((item, i) => <li key={i}>{item}</li>)}
            </ul>
          </Card>
        ))}
      </div>
    </AppShell>
  );
}
