import { useState, useEffect, useRef, useCallback } from 'react';
import { Bell, X, Check } from '@phosphor-icons/react';
import { toast } from 'sonner';
import { notificationApi, orderApi } from '../api';
import { formatDistanceToNow } from 'date-fns';

function playOrderSound() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.type = 'sine';
    osc.frequency.setValueAtTime(880, ctx.currentTime);
    osc.frequency.setValueAtTime(1100, ctx.currentTime + 0.15);
    gain.gain.setValueAtTime(0.3, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.5);
    osc.start();
    osc.stop(ctx.currentTime + 0.5);
  } catch {
    // audio not available
  }
}

function showBrowserNotification(title, body) {
  if ('Notification' in window && Notification.permission === 'granted') {
    try {
      new Notification(title, { body, icon: '/icon-192.png', tag: 'new-order' });
    } catch {
      // notification blocked
    }
  }
}

// Polls pending orders and alerts (sound + toast + browser notification) on new ones
export function useNewOrderAlert() {
  const seenIds = useRef(null);

  useEffect(() => {
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission();
    }

    const check = async () => {
      try {
        const res = await orderApi.getPendingOrders();
        const orders = Array.isArray(res.data) ? res.data : [];
        const ids = new Set(orders.map((o) => o.order_id));
        if (seenIds.current !== null) {
          const newOrders = orders.filter((o) => !seenIds.current.has(o.order_id));
          if (newOrders.length > 0) {
            playOrderSound();
            const first = newOrders[0];
            const msg = newOrders.length === 1
              ? `New order #${first.order_id?.slice(-6)} — ₹${(first.total_amount || 0).toFixed(0)}`
              : `${newOrders.length} new orders received`;
            toast.info(msg, { duration: 10000 });
            showBrowserNotification('New Order! 🛒', msg);
          }
        }
        seenIds.current = ids;
      } catch {
        // polling failure, retry next tick
      }
    };

    check();
    const interval = setInterval(check, 20000);
    return () => clearInterval(interval);
  }, []);
}

export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const [unread, setUnread] = useState(0);
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(false);

  const fetchUnread = useCallback(async () => {
    try {
      const res = await notificationApi.getUnreadCount();
      setUnread(res.data.unread_count || 0);
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    fetchUnread();
    const interval = setInterval(fetchUnread, 30000);
    return () => clearInterval(interval);
  }, [fetchUnread]);

  const openPanel = async () => {
    setOpen(true);
    setLoading(true);
    try {
      const res = await notificationApi.getNotifications({ limit: 30 });
      setNotifications(res.data.notifications || []);
      setUnread(res.data.unread_count || 0);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await notificationApi.markAllRead();
      setNotifications((n) => n.map((x) => ({ ...x, is_read: true })));
      setUnread(0);
    } catch {
      toast.error('Failed to mark as read');
    }
  };

  const handleMarkRead = async (notif) => {
    if (notif.is_read) return;
    try {
      await notificationApi.markRead(notif.notification_id);
      setNotifications((n) =>
        n.map((x) => (x.notification_id === notif.notification_id ? { ...x, is_read: true } : x))
      );
      setUnread((u) => Math.max(0, u - 1));
    } catch {
      // ignore
    }
  };

  return (
    <>
      <button
        onClick={openPanel}
        className="fixed top-2 right-3 lg:top-4 lg:right-6 z-30 p-2.5 bg-white border border-[#E4E4E7] rounded-full hover:bg-[#F4F4F5] transition-colors shadow-sm"
        data-testid="notification-bell-button"
      >
        <Bell size={20} weight="bold" />
        {unread > 0 && (
          <span
            className="absolute -top-1 -right-1 min-w-[18px] h-[18px] px-1 bg-[#DC2626] text-white text-[10px] font-bold rounded-full flex items-center justify-center"
            data-testid="notification-unread-badge"
          >
            {unread > 99 ? '99+' : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="fixed inset-0 z-50" data-testid="notifications-panel">
          <div className="absolute inset-0 bg-black/30" onClick={() => setOpen(false)} />
          <div className="absolute right-0 top-0 bottom-0 w-full max-w-sm bg-white border-l border-[#E4E4E7] flex flex-col shadow-xl">
            <div className="p-4 border-b border-[#E4E4E7] flex items-center justify-between">
              <h2 className="font-bold text-lg" style={{ fontFamily: 'Cabinet Grotesk, system-ui' }}>
                Notifications
              </h2>
              <div className="flex items-center gap-2">
                {unread > 0 && (
                  <button
                    onClick={handleMarkAllRead}
                    className="text-xs font-medium text-[#002FA7] hover:underline flex items-center gap-1"
                    data-testid="mark-all-read-button"
                  >
                    <Check size={14} /> Mark all read
                  </button>
                )}
                <button onClick={() => setOpen(false)} className="p-2 hover:bg-[#F4F4F5] rounded" data-testid="close-notifications-button">
                  <X size={20} />
                </button>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto">
              {loading ? (
                <div className="flex justify-center p-8"><div className="spinner" /></div>
              ) : notifications.length === 0 ? (
                <div className="p-8 text-center text-[#52525B]">
                  <Bell size={40} className="mx-auto mb-3 text-[#E4E4E7]" />
                  <p className="text-sm">No notifications yet</p>
                </div>
              ) : (
                notifications.map((notif) => (
                  <button
                    key={notif.notification_id}
                    onClick={() => handleMarkRead(notif)}
                    className={`w-full text-left p-4 border-b border-[#E4E4E7] hover:bg-[#F4F4F5] transition-colors ${!notif.is_read ? 'bg-blue-50/60' : ''}`}
                    data-testid={`notification-item-${notif.notification_id}`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <p className="font-medium text-sm">{notif.title}</p>
                      {!notif.is_read && <span className="w-2 h-2 bg-[#002FA7] rounded-full flex-shrink-0 mt-1.5" />}
                    </div>
                    <p className="text-sm text-[#52525B] mt-0.5">{notif.message}</p>
                    {notif.created_at && (
                      <p className="text-xs text-[#52525B] mt-1">
                        {formatDistanceToNow(new Date(notif.created_at), { addSuffix: true })}
                      </p>
                    )}
                  </button>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
