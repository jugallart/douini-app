import { useState, useRef, useEffect } from "react";
import { useNotifications, useMarkNotificationRead, useMarkAllNotificationsRead } from "../../hooks/useNotifications";

export function NotificationBell() {
  const { data: notifications } = useNotifications();
  const markRead = useMarkNotificationRead();
  const markAllRead = useMarkAllNotificationsRead();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const unread = notifications?.filter((n) => !n.read_at) ?? [];
  const unreadCount = unread.length;

  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setOpen(!open)} className="relative rounded-lg p-1.5 hover:bg-gray-100">
        <span className="text-lg">🔔</span>
        {unreadCount > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white">
            {unreadCount}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 top-full z-50 mt-1 w-80 rounded-xl border border-gray-200 bg-white shadow-lg">
          <div className="flex items-center justify-between border-b border-gray-100 px-4 py-2">
            <span className="text-sm font-semibold">Notifications</span>
            {unreadCount > 0 && (
              <button onClick={() => markAllRead.mutate()} className="text-xs text-brand-600 hover:underline">
                Tout marquer lu
              </button>
            )}
          </div>
          <div className="max-h-80 overflow-y-auto">
            {notifications?.length === 0 ? (
              <p className="px-4 py-6 text-center text-sm text-gray-400">Aucune notification</p>
            ) : (
              notifications?.map((n) => (
                <div
                  key={n.id}
                  className={`border-b border-gray-50 px-4 py-3 text-sm ${!n.read_at ? "bg-brand-50/50" : ""}`}
                >
                  <p className="text-gray-700">{n.message}</p>
                  <div className="mt-1 flex items-center justify-between">
                    <span className="text-xs text-gray-400">{new Date(n.created_at).toLocaleDateString("fr-FR")}</span>
                    {!n.read_at && (
                      <button onClick={() => markRead.mutate(n.id)} className="text-xs text-brand-600 hover:underline">
                        Marquer lu
                      </button>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
