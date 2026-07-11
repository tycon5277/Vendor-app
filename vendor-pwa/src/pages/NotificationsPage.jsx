import { useEffect, useState, useCallback } from 'react';
import { Bell, Check } from '@phosphor-icons/react';
import { toast } from 'sonner';
import { formatDistanceToNow } from 'date-fns';
import { notificationApi } from '../api';

export default function NotificationsPage() {
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [unread, setUnread] = useState(0);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const res = await notificationApi.getNotifications({ limit: 100 });
      setNotifications(res.data.notifications || []);
      setUnread(res.data.unread_count || 0);
    } catch {
      toast.error('Failed to load notifications');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const markRead = async (notif) => {
    if (notif.is_read) return;
    try {
      await notificationApi.markRead(notif.notification_id);
      setNotifications((prev) =>
        prev.map((n) => (n.notification_id === notif.notification_id ? { ...n, is_read: true } : n))
      );
      setUnread((u) => Math.max(0, u - 1));
    } catch {
      // ignore
    }
  };

  const markAllRead = async () => {
    try {
      await notificationApi.markAllRead();
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setUnread(0);
      toast.success('All notifications marked as read');
    } catch {
      toast.error('Failed to mark all as read');
    }
  };

  return (
    <div className="p-6 lg:p-8 max-w-3xl mx-auto" data-testid="notifications-page">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl lg:text-3xl font-bold mb-1" style={{ fontFamily: 'Cabinet Grotesk, system-ui' }}>
            Notifications
          </h1>
          <p className="text-[#52525B]">{unread} unread</p>
        </div>
        {unread > 0 && (
          <button onClick={markAllRead} className="btn btn-outline" data-testid="mark-all-read-page-button">
            <Check size={16} weight="bold" />
            Mark all read
          </button>
        )}
      </div>

      {loading ? (
        <div className="flex justify-center py-16"><div className="spinner" /></div>
      ) : notifications.length === 0 ? (
        <div className="card p-12 text-center" data-testid="notifications-empty">
          <Bell size={64} className="text-[#E4E4E7] mx-auto mb-4" />
          <h3 className="font-bold text-lg mb-1">No notifications yet</h3>
          <p className="text-[#52525B]">You&apos;ll see order updates and Carpet Genie alerts here.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {notifications.map((n) => (
            <button
              key={n.notification_id}
              onClick={() => markRead(n)}
              className={`w-full text-left card p-4 flex items-start gap-3 transition-colors hover:bg-[#F4F4F5] ${
                !n.is_read ? 'border-[#002FA7]/40 bg-blue-50/40' : ''
              }`}
              data-testid={`notification-page-item-${n.notification_id}`}
            >
              <div className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 ${
                !n.is_read ? 'bg-[#002FA7] text-white' : 'bg-[#F4F4F5] text-[#52525B]'
              }`}>
                <Bell size={18} weight="bold" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 justify-between">
                  <p className="font-semibold text-sm">{n.title}</p>
                  {!n.is_read && <span className="w-2 h-2 bg-[#002FA7] rounded-full flex-shrink-0" />}
                </div>
                <p className="text-sm text-[#52525B] mt-0.5">{n.message}</p>
                {n.created_at && (
                  <p className="text-xs text-[#52525B] mt-1">
                    {formatDistanceToNow(new Date(n.created_at), { addSuffix: true })}
                  </p>
                )}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
