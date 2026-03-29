// Timezone utilities for Indian Standard Time (IST = UTC+5:30)

const IST_OFFSET_MINUTES = 330; // 5 hours 30 minutes

/**
 * Convert a date to IST timezone
 */
export const toIST = (date: Date | string): Date => {
  const d = typeof date === 'string' ? new Date(date) : date;
  // Get UTC time and add IST offset
  const utc = d.getTime() + (d.getTimezoneOffset() * 60000);
  return new Date(utc + (IST_OFFSET_MINUTES * 60000));
};

/**
 * Format date in IST for display
 * @param date - Date string or Date object
 * @param options - Intl.DateTimeFormat options
 */
export const formatDateIST = (
  date: Date | string,
  options?: Intl.DateTimeFormatOptions
): string => {
  const d = typeof date === 'string' ? new Date(date) : date;
  
  const defaultOptions: Intl.DateTimeFormatOptions = {
    timeZone: 'Asia/Kolkata',
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    ...options,
  };
  
  return d.toLocaleDateString('en-IN', defaultOptions);
};

/**
 * Format time in IST for display
 * @param date - Date string or Date object
 * @param use24Hour - Use 24-hour format (default: false for 12-hour with AM/PM)
 */
export const formatTimeIST = (
  date: Date | string,
  use24Hour: boolean = false
): string => {
  const d = typeof date === 'string' ? new Date(date) : date;
  
  const options: Intl.DateTimeFormatOptions = {
    timeZone: 'Asia/Kolkata',
    hour: '2-digit',
    minute: '2-digit',
    hour12: !use24Hour,
  };
  
  return d.toLocaleTimeString('en-IN', options);
};

/**
 * Format datetime in IST for display
 * @param date - Date string or Date object
 */
export const formatDateTimeIST = (date: Date | string): string => {
  const d = typeof date === 'string' ? new Date(date) : date;
  
  const options: Intl.DateTimeFormatOptions = {
    timeZone: 'Asia/Kolkata',
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: true,
  };
  
  return d.toLocaleString('en-IN', options);
};

/**
 * Get relative time string (e.g., "2 hours ago", "Just now")
 * @param date - Date string or Date object
 */
export const getRelativeTimeIST = (date: Date | string): string => {
  const d = typeof date === 'string' ? new Date(date) : date;
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffSecs = Math.floor(diffMs / 1000);
  const diffMins = Math.floor(diffSecs / 60);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffSecs < 60) {
    return 'Just now';
  } else if (diffMins < 60) {
    return `${diffMins} min${diffMins > 1 ? 's' : ''} ago`;
  } else if (diffHours < 24) {
    return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
  } else if (diffDays < 7) {
    return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
  } else {
    return formatDateIST(d);
  }
};

/**
 * Get current date in IST
 */
export const getNowIST = (): Date => {
  return toIST(new Date());
};

/**
 * Get today's date string in YYYY-MM-DD format (IST)
 */
export const getTodayIST = (): string => {
  const now = getNowIST();
  return now.toISOString().split('T')[0];
};

/**
 * Get current day name in IST (e.g., "monday", "tuesday")
 */
export const getCurrentDayIST = (): string => {
  const now = new Date();
  return now.toLocaleDateString('en-US', { 
    weekday: 'long', 
    timeZone: 'Asia/Kolkata' 
  }).toLowerCase();
};

/**
 * Format order time for display
 */
export const formatOrderTime = (date: Date | string): string => {
  const d = typeof date === 'string' ? new Date(date) : date;
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  
  if (diffMins < 1) {
    return 'Just now';
  } else if (diffMins < 60) {
    return `${diffMins}m ago`;
  } else if (diffMins < 1440) { // Less than 24 hours
    const hours = Math.floor(diffMins / 60);
    return `${hours}h ago`;
  } else {
    return formatDateTimeIST(d);
  }
};

export default {
  toIST,
  formatDateIST,
  formatTimeIST,
  formatDateTimeIST,
  getRelativeTimeIST,
  getNowIST,
  getTodayIST,
  getCurrentDayIST,
  formatOrderTime,
};
