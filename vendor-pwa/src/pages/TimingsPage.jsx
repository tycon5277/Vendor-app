import { useEffect, useState, useCallback } from 'react';
import { Clock, Plus, Trash, Calendar, Check, X, Warning } from '@phosphor-icons/react';
import { toast } from 'sonner';
import { timingsApi } from '../api';

const DAYS = [
  { key: 'monday', label: 'Monday' },
  { key: 'tuesday', label: 'Tuesday' },
  { key: 'wednesday', label: 'Wednesday' },
  { key: 'thursday', label: 'Thursday' },
  { key: 'friday', label: 'Friday' },
  { key: 'saturday', label: 'Saturday' },
  { key: 'sunday', label: 'Sunday' },
];

function findDay(schedule, key) {
  return schedule.find((s) => s.day === key) || {
    day: key,
    is_open: true,
    open_time: '09:00',
    close_time: '21:00',
    has_break: false,
    break_start: '',
    break_end: '',
  };
}

export default function TimingsPage() {
  const [loading, setLoading] = useState(true);
  const [schedule, setSchedule] = useState([]);
  const [cutoff, setCutoff] = useState(30);
  const [holidays, setHolidays] = useState([]);
  const [savingDay, setSavingDay] = useState('');

  const [showHolidayForm, setShowHolidayForm] = useState(false);
  const [holidayForm, setHolidayForm] = useState({ name: '', date: '', end_date: '', reason: '' });

  const [showCloseEarly, setShowCloseEarly] = useState(false);
  const [closeEarly, setCloseEarly] = useState({ close_time: '18:00', reason: '' });

  const fetchTimings = useCallback(async () => {
    try {
      const res = await timingsApi.get();
      setSchedule(res.data?.timings?.weekly_schedule || []);
      setCutoff(res.data?.timings?.delivery_cutoff_minutes ?? 30);
      setHolidays(res.data?.holidays || []);
    } catch {
      toast.error('Failed to load timings');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchTimings(); }, [fetchTimings]);

  const saveDay = async (dayKey, applyToAllWeekdays = false) => {
    const day = findDay(schedule, dayKey);
    setSavingDay(dayKey);
    try {
      await timingsApi.updateDay({
        day: dayKey,
        is_open: !!day.is_open,
        open_time: day.open_time || '09:00',
        close_time: day.close_time || '21:00',
        has_break: !!day.has_break,
        break_start: day.has_break ? day.break_start || '13:00' : null,
        break_end: day.has_break ? day.break_end || '14:00' : null,
        apply_to_all_weekdays: applyToAllWeekdays,
      });
      toast.success(applyToAllWeekdays ? 'Applied to all weekdays' : 'Day saved');
      fetchTimings();
    } catch {
      toast.error('Failed to save');
    } finally {
      setSavingDay('');
    }
  };

  const updateLocalDay = (dayKey, patch) => {
    setSchedule((prev) => {
      const idx = prev.findIndex((s) => s.day === dayKey);
      if (idx === -1) {
        return [...prev, { ...findDay(prev, dayKey), ...patch }];
      }
      const next = [...prev];
      next[idx] = { ...next[idx], ...patch };
      return next;
    });
  };

  const addHoliday = async (e) => {
    e.preventDefault();
    if (!holidayForm.name || !holidayForm.date) {
      toast.error('Name and date are required');
      return;
    }
    try {
      await timingsApi.addHoliday({
        name: holidayForm.name,
        date: holidayForm.date,
        end_date: holidayForm.end_date || null,
        reason: holidayForm.reason || null,
      });
      toast.success('Holiday added');
      setHolidayForm({ name: '', date: '', end_date: '', reason: '' });
      setShowHolidayForm(false);
      fetchTimings();
    } catch {
      toast.error('Failed to add holiday');
    }
  };

  const deleteHoliday = async (id) => {
    if (!window.confirm('Delete this holiday?')) return;
    try {
      await timingsApi.deleteHoliday(id);
      toast.success('Holiday removed');
      fetchTimings();
    } catch {
      toast.error('Failed to delete');
    }
  };

  const submitCloseEarly = async (e) => {
    e.preventDefault();
    if (!closeEarly.close_time) return;
    try {
      await timingsApi.closeEarly(closeEarly);
      toast.success('Shop will close early today');
      setShowCloseEarly(false);
      fetchTimings();
    } catch {
      toast.error('Failed to schedule early close');
    }
  };

  const saveCutoff = async () => {
    try {
      await timingsApi.update({ weekly_schedule: schedule, delivery_cutoff_minutes: parseInt(cutoff, 10) || 30 });
      toast.success('Cutoff saved');
    } catch {
      toast.error('Failed to save');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="spinner" />
      </div>
    );
  }

  return (
    <div className="p-6 lg:p-8 max-w-4xl mx-auto" data-testid="timings-page">
      <div className="mb-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl lg:text-3xl font-bold mb-1" style={{ fontFamily: 'Cabinet Grotesk, system-ui' }}>
            Shop Timings
          </h1>
          <p className="text-[#52525B]">Weekly hours, breaks, holidays and closing early.</p>
        </div>
        <button
          onClick={() => setShowCloseEarly(true)}
          className="btn btn-outline text-[#DC2626] border-red-200 hover:bg-red-50"
          data-testid="open-close-early-button"
        >
          <Warning size={16} weight="bold" />
          Close Early Today
        </button>
      </div>

      <section className="mb-8">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-[#52525B] mb-3">Weekly Schedule</h2>
        <div className="space-y-3">
          {DAYS.map((d) => {
            const day = findDay(schedule, d.key);
            return (
              <div key={d.key} className="card p-4" data-testid={`day-row-${d.key}`}>
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <span className="font-semibold min-w-24">{d.label}</span>
                    <button
                      type="button"
                      onClick={() => updateLocalDay(d.key, { is_open: !day.is_open })}
                      className={`btn h-8 text-xs ${day.is_open ? 'btn-success' : 'btn-outline text-[#DC2626]'}`}
                      data-testid={`toggle-open-${d.key}`}
                    >
                      {day.is_open ? 'Open' : 'Closed'}
                    </button>
                  </div>
                  <div className="flex gap-2">
                    {d.key !== 'saturday' && d.key !== 'sunday' && (
                      <button
                        onClick={() => saveDay(d.key, true)}
                        className="btn btn-outline text-xs h-8"
                        disabled={savingDay === d.key}
                        data-testid={`apply-weekdays-${d.key}`}
                      >
                        Apply to weekdays
                      </button>
                    )}
                    <button
                      onClick={() => saveDay(d.key)}
                      className="btn btn-primary text-xs h-8"
                      disabled={savingDay === d.key}
                      data-testid={`save-day-${d.key}`}
                    >
                      {savingDay === d.key ? <span className="spinner" /> : 'Save'}
                    </button>
                  </div>
                </div>
                {day.is_open && (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <div>
                      <label className="label">Open</label>
                      <input
                        type="time"
                        className="input h-10"
                        value={day.open_time || '09:00'}
                        onChange={(e) => updateLocalDay(d.key, { open_time: e.target.value })}
                        data-testid={`open-time-${d.key}`}
                      />
                    </div>
                    <div>
                      <label className="label">Close</label>
                      <input
                        type="time"
                        className="input h-10"
                        value={day.close_time || '21:00'}
                        onChange={(e) => updateLocalDay(d.key, { close_time: e.target.value })}
                        data-testid={`close-time-${d.key}`}
                      />
                    </div>
                    <div className="flex items-end">
                      <button
                        type="button"
                        onClick={() => updateLocalDay(d.key, { has_break: !day.has_break })}
                        className={`btn h-10 w-full text-xs ${day.has_break ? 'btn-primary' : 'btn-outline'}`}
                        data-testid={`toggle-break-${d.key}`}
                      >
                        {day.has_break ? <><Check size={14}/> Break</> : 'Add Break'}
                      </button>
                    </div>
                    {day.has_break && (
                      <>
                        <div>
                          <label className="label">Break Start</label>
                          <input
                            type="time"
                            className="input h-10"
                            value={day.break_start || '13:00'}
                            onChange={(e) => updateLocalDay(d.key, { break_start: e.target.value })}
                            data-testid={`break-start-${d.key}`}
                          />
                        </div>
                        <div>
                          <label className="label">Break End</label>
                          <input
                            type="time"
                            className="input h-10"
                            value={day.break_end || '14:00'}
                            onChange={(e) => updateLocalDay(d.key, { break_end: e.target.value })}
                            data-testid={`break-end-${d.key}`}
                          />
                        </div>
                      </>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </section>

      <section className="mb-8">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-[#52525B] mb-3">Delivery Cutoff</h2>
        <div className="card p-4 flex items-end gap-3 max-w-md">
          <div className="flex-1">
            <label className="label">Stop accepting orders (min before close)</label>
            <input
              type="number"
              min="0"
              className="input h-10"
              value={cutoff}
              onChange={(e) => setCutoff(e.target.value)}
              data-testid="cutoff-input"
            />
          </div>
          <button onClick={saveCutoff} className="btn btn-primary h-10" data-testid="save-cutoff-button">
            Save
          </button>
        </div>
      </section>

      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-[#52525B]">Holidays & Closures</h2>
          <button
            onClick={() => setShowHolidayForm((v) => !v)}
            className="btn btn-primary text-xs h-8"
            data-testid="add-holiday-toggle"
          >
            <Plus size={14} weight="bold" />
            Add Holiday
          </button>
        </div>

        {showHolidayForm && (
          <form onSubmit={addHoliday} className="card p-4 mb-4 space-y-3" data-testid="add-holiday-form">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label className="label">Name *</label>
                <input
                  className="input h-10"
                  placeholder="e.g., Diwali"
                  value={holidayForm.name}
                  onChange={(e) => setHolidayForm((f) => ({ ...f, name: e.target.value }))}
                  data-testid="holiday-name-input"
                />
              </div>
              <div>
                <label className="label">Date *</label>
                <input
                  type="date"
                  className="input h-10"
                  value={holidayForm.date}
                  onChange={(e) => setHolidayForm((f) => ({ ...f, date: e.target.value }))}
                  data-testid="holiday-date-input"
                />
              </div>
              <div>
                <label className="label">End Date</label>
                <input
                  type="date"
                  className="input h-10"
                  value={holidayForm.end_date}
                  onChange={(e) => setHolidayForm((f) => ({ ...f, end_date: e.target.value }))}
                  data-testid="holiday-enddate-input"
                />
              </div>
              <div>
                <label className="label">Reason</label>
                <input
                  className="input h-10"
                  placeholder="Optional"
                  value={holidayForm.reason}
                  onChange={(e) => setHolidayForm((f) => ({ ...f, reason: e.target.value }))}
                  data-testid="holiday-reason-input"
                />
              </div>
            </div>
            <div className="flex gap-2 justify-end">
              <button
                type="button"
                onClick={() => setShowHolidayForm(false)}
                className="btn btn-outline"
              >
                Cancel
              </button>
              <button type="submit" className="btn btn-primary" data-testid="save-holiday-button">
                Save Holiday
              </button>
            </div>
          </form>
        )}

        {holidays.length === 0 ? (
          <div className="card p-8 text-center text-[#52525B]" data-testid="holidays-empty">
            <Calendar size={40} className="mx-auto mb-2 text-[#E4E4E7]" />
            <p className="text-sm">No holidays scheduled yet.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {holidays.map((h) => (
              <div key={h.holiday_id} className="card p-3 flex items-center gap-3" data-testid={`holiday-row-${h.holiday_id}`}>
                <div className="w-10 h-10 rounded bg-[#F4F4F5] flex items-center justify-center flex-shrink-0">
                  <Calendar size={18} weight="bold" className="text-[#002FA7]" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-sm">{h.name}</p>
                  <p className="text-xs text-[#52525B]">
                    {h.date}{h.end_date ? ` → ${h.end_date}` : ''}{h.reason ? ` • ${h.reason}` : ''}
                    {h.early_close_time ? ` • Closes ${h.early_close_time}` : ''}
                  </p>
                </div>
                <button
                  onClick={() => deleteHoliday(h.holiday_id)}
                  className="p-2 hover:bg-red-50 rounded text-[#DC2626]"
                  data-testid={`delete-holiday-${h.holiday_id}`}
                >
                  <Trash size={16} />
                </button>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Close early modal */}
      {showCloseEarly && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" data-testid="close-early-modal">
          <div className="bg-white rounded-lg w-full max-w-md">
            <div className="p-4 border-b border-[#E4E4E7] flex items-center justify-between">
              <h3 className="font-bold text-lg" style={{ fontFamily: 'Cabinet Grotesk, system-ui' }}>Close Early Today</h3>
              <button onClick={() => setShowCloseEarly(false)} className="p-2 hover:bg-[#F4F4F5] rounded">
                <X size={20} />
              </button>
            </div>
            <form onSubmit={submitCloseEarly} className="p-4 space-y-3">
              <div>
                <label className="label">Close Time *</label>
                <input
                  type="time"
                  className="input h-10"
                  value={closeEarly.close_time}
                  onChange={(e) => setCloseEarly((f) => ({ ...f, close_time: e.target.value }))}
                  data-testid="close-early-time"
                />
              </div>
              <div>
                <label className="label">Reason</label>
                <input
                  className="input h-10"
                  placeholder="e.g., Personal event"
                  value={closeEarly.reason}
                  onChange={(e) => setCloseEarly((f) => ({ ...f, reason: e.target.value }))}
                  data-testid="close-early-reason"
                />
              </div>
              <div className="flex gap-2 justify-end pt-2">
                <button type="button" onClick={() => setShowCloseEarly(false)} className="btn btn-outline">Cancel</button>
                <button type="submit" className="btn btn-primary" data-testid="submit-close-early">
                  <Clock size={16} weight="bold" />
                  Close Early
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
