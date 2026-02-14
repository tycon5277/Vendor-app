import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  Modal,
  TextInput,
  Switch,
  Alert,
  ActivityIndicator,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { timingsAPI } from '../../../src/utils/api';
import { useAlert } from '../../../src/context/AlertContext';
import { DateWheelPicker, TimeWheelPicker } from '../../../src/components/WheelPicker';

const DAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'];
const DAY_LABELS: Record<string, string> = {
  monday: 'Monday',
  tuesday: 'Tuesday',
  wednesday: 'Wednesday',
  thursday: 'Thursday',
  friday: 'Friday',
  saturday: 'Saturday',
  sunday: 'Sunday',
};

const HOURS = Array.from({ length: 24 }, (_, i) => i.toString().padStart(2, '0'));
const MINUTES = ['00', '15', '30', '45'];

interface DaySchedule {
  day: string;
  is_open: boolean;
  open_time: string;
  close_time: string;
  has_break: boolean;
  break_start?: string;
  break_end?: string;
}

interface Holiday {
  holiday_id: string;
  name: string;
  date: string;
  end_date?: string;
  reason?: string;
}

export default function TimingsScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { showAlert } = useAlert();
  
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [weeklySchedule, setWeeklySchedule] = useState<DaySchedule[]>([]);
  const [holidays, setHolidays] = useState<Holiday[]>([]);
  const [deliveryCutoff, setDeliveryCutoff] = useState(30);
  
  const [showDayModal, setShowDayModal] = useState(false);
  const [selectedDay, setSelectedDay] = useState<DaySchedule | null>(null);
  const [showHolidayModal, setShowHolidayModal] = useState(false);
  const [showCloseEarlyModal, setShowCloseEarlyModal] = useState(false);
  
  // Form state for day editing
  const [dayForm, setDayForm] = useState({
    is_open: true,
    open_time: '09:00',
    close_time: '21:00',
    has_break: false,
    break_start: '13:00',
    break_end: '14:00',
    apply_to_all_weekdays: false,
  });
  
  // Form state for holiday
  const [holidayForm, setHolidayForm] = useState({
    name: '',
    date: new Date(),
    end_date: new Date(Date.now() + 24 * 60 * 60 * 1000), // Tomorrow
    reason: '',
    isMultiDay: false,
  });
  
  // Form state for close early
  const [closeEarlyTime, setCloseEarlyTime] = useState('18:00');
  const [closeEarlyReason, setCloseEarlyReason] = useState('');

  const loadTimings = useCallback(async () => {
    try {
      const response = await timingsAPI.get();
      const { timings, holidays: loadedHolidays } = response.data;
      setWeeklySchedule(timings?.weekly_schedule || []);
      setDeliveryCutoff(timings?.delivery_cutoff_minutes || 30);
      setHolidays(loadedHolidays || []);
    } catch (error) {
      console.error('Load timings error:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadTimings();
  }, [loadTimings]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadTimings();
    setRefreshing(false);
  }, [loadTimings]);

  const formatTime = (time: string) => {
    if (!time) return '';
    const [hour, minute] = time.split(':');
    const h = parseInt(hour);
    const ampm = h >= 12 ? 'PM' : 'AM';
    const displayHour = h === 0 ? 12 : h > 12 ? h - 12 : h;
    return `${displayHour}:${minute} ${ampm}`;
  };

  const openDayModal = (day: DaySchedule) => {
    setSelectedDay(day);
    setDayForm({
      is_open: day.is_open,
      open_time: day.open_time,
      close_time: day.close_time,
      has_break: day.has_break,
      break_start: day.break_start || '13:00',
      break_end: day.break_end || '14:00',
      apply_to_all_weekdays: false,
    });
    setShowDayModal(true);
  };

  const saveDaySchedule = async () => {
    if (!selectedDay) return;
    
    setSaving(true);
    try {
      await timingsAPI.updateDay({
        day: selectedDay.day,
        is_open: dayForm.is_open,
        open_time: dayForm.open_time,
        close_time: dayForm.close_time,
        has_break: dayForm.has_break,
        break_start: dayForm.has_break ? dayForm.break_start : null,
        break_end: dayForm.has_break ? dayForm.break_end : null,
        apply_to_all_weekdays: dayForm.apply_to_all_weekdays,
      });
      
      showAlert({ type: 'success', title: 'Saved!', message: 'Schedule updated' });
      setShowDayModal(false);
      loadTimings();
    } catch (error: any) {
      showAlert({ type: 'error', title: 'Error', message: error.response?.data?.detail || 'Failed to update schedule' });
    } finally {
      setSaving(false);
    }
  };

  const addHoliday = async () => {
    if (!holidayForm.name) {
      showAlert({ type: 'warning', title: 'Required', message: 'Please enter holiday name' });
      return;
    }
    
    setSaving(true);
    try {
      const formatDateStr = (date: Date) => date.toISOString().split('T')[0];
      
      await timingsAPI.addHoliday({
        name: holidayForm.name,
        date: formatDateStr(holidayForm.date),
        end_date: holidayForm.isMultiDay ? formatDateStr(holidayForm.end_date) : null,
        reason: holidayForm.reason || null,
      });
      
      showAlert({ type: 'success', title: 'Added!', message: 'Holiday added' });
      setShowHolidayModal(false);
      setHolidayForm({ 
        name: '', 
        date: new Date(), 
        end_date: new Date(Date.now() + 24 * 60 * 60 * 1000), 
        reason: '',
        isMultiDay: false,
      });
      loadTimings();
    } catch (error: any) {
      showAlert({ type: 'error', title: 'Error', message: error.response?.data?.detail || 'Failed to add holiday' });
    } finally {
      setSaving(false);
    }
  };

  const deleteHoliday = async (holiday: Holiday) => {
    Alert.alert(
      'Delete Holiday',
      `Remove "${holiday.name}" from holidays?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            try {
              await timingsAPI.deleteHoliday(holiday.holiday_id);
              showAlert({ type: 'success', title: 'Deleted', message: 'Holiday removed' });
              loadTimings();
            } catch (error) {
              showAlert({ type: 'error', title: 'Error', message: 'Failed to delete holiday' });
            }
          },
        },
      ]
    );
  };

  const closeShopEarly = async () => {
    setSaving(true);
    try {
      await timingsAPI.closeEarly({
        close_time: closeEarlyTime,
        reason: closeEarlyReason || undefined,
      });
      
      showAlert({ type: 'success', title: 'Done!', message: `Shop will close at ${formatTime(closeEarlyTime)} today` });
      setShowCloseEarlyModal(false);
      setCloseEarlyTime('18:00');
      setCloseEarlyReason('');
      loadTimings();
    } catch (error: any) {
      showAlert({ type: 'error', title: 'Error', message: error.response?.data?.detail || 'Failed to set early closing' });
    } finally {
      setSaving(false);
    }
  };

  const getCurrentDayStatus = () => {
    const today = new Date().toLocaleDateString('en-US', { weekday: 'long' }).toLowerCase();
    const todaySchedule = weeklySchedule.find(s => s.day === today);
    
    if (!todaySchedule || !todaySchedule.is_open) {
      return { isOpen: false, text: 'Closed today' };
    }
    
    const now = new Date();
    const currentTime = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;
    
    if (currentTime < todaySchedule.open_time) {
      return { isOpen: false, text: `Opens at ${formatTime(todaySchedule.open_time)}` };
    }
    
    if (currentTime >= todaySchedule.close_time) {
      return { isOpen: false, text: 'Closed for today' };
    }
    
    return { isOpen: true, text: `Closes at ${formatTime(todaySchedule.close_time)}` };
  };

  const renderTimeSelector = (
    label: string,
    value: string,
    onChange: (time: string) => void
  ) => {
    return (
      <View style={styles.timeSelectorContainer}>
        <Text style={styles.timeSelectorLabel}>{label}</Text>
        <TimeWheelPicker
          time={value}
          onTimeChange={onChange}
          minuteInterval={15}
        />
      </View>
    );
  };

  if (loading) {
    return (
      <View style={[styles.container, styles.centered, { paddingTop: insets.top }]}>
        <ActivityIndicator size="large" color="#6366F1" />
      </View>
    );
  }

  const dayStatus = getCurrentDayStatus();

  return (
    <View style={[styles.container, { paddingTop: insets.top }]} data-testid="timings-screen">
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity style={styles.backBtn} onPress={() => router.back()}>
          <Ionicons name="arrow-back" size={24} color="#374151" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Operating Hours</Text>
        <View style={{ width: 40 }} />
      </View>

      <ScrollView
        style={styles.scrollView}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} colors={['#6366F1']} />}
        showsVerticalScrollIndicator={false}
      >
        {/* Current Status Card */}
        <View style={[styles.statusCard, dayStatus.isOpen ? styles.statusCardOpen : styles.statusCardClosed]}>
          <View style={styles.statusIconContainer}>
            <Ionicons name={dayStatus.isOpen ? 'storefront' : 'moon'} size={28} color={dayStatus.isOpen ? '#22C55E' : '#EF4444'} />
          </View>
          <View style={styles.statusContent}>
            <Text style={[styles.statusTitle, dayStatus.isOpen && styles.statusTitleOpen]}>
              Shop is {dayStatus.isOpen ? 'OPEN' : 'CLOSED'}
            </Text>
            <Text style={styles.statusSubtitle}>{dayStatus.text}</Text>
          </View>
        </View>

        {/* Weekly Schedule */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Weekly Schedule</Text>
          
          {weeklySchedule.map(day => (
            <TouchableOpacity
              key={day.day}
              style={styles.dayCard}
              onPress={() => openDayModal(day)}
              data-testid={`timings-day-${day.day}`}
            >
              <View style={styles.dayHeader}>
                <Text style={styles.dayName}>{DAY_LABELS[day.day]}</Text>
                <View style={[styles.dayStatus, day.is_open ? styles.dayStatusOpen : styles.dayStatusClosed]}>
                  <Text style={[styles.dayStatusText, day.is_open && styles.dayStatusTextOpen]}>
                    {day.is_open ? 'Open' : 'Closed'}
                  </Text>
                </View>
              </View>
              
              {day.is_open ? (
                <View style={styles.dayTimes}>
                  <Text style={styles.dayTimeText}>
                    {formatTime(day.open_time)} → {formatTime(day.close_time)}
                  </Text>
                  {day.has_break && (
                    <Text style={styles.dayBreakText}>
                      Break: {formatTime(day.break_start!)} - {formatTime(day.break_end!)}
                    </Text>
                  )}
                </View>
              ) : (
                <Text style={styles.dayClosedText}>All day</Text>
              )}
              
              <Ionicons name="chevron-forward" size={20} color="#9CA3AF" style={styles.dayArrow} />
            </TouchableOpacity>
          ))}
        </View>

        {/* Quick Actions */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Quick Actions</Text>
          
          <View style={styles.quickActionsRow}>
            <TouchableOpacity 
              style={styles.quickActionBtn}
              onPress={() => setShowCloseEarlyModal(true)}
              data-testid="timings-close-early-btn"
            >
              <View style={[styles.quickActionIcon, { backgroundColor: '#FEF3C7' }]}>
                <Ionicons name="moon" size={24} color="#F59E0B" />
              </View>
              <Text style={styles.quickActionText}>Close Early Today</Text>
            </TouchableOpacity>
            
            <TouchableOpacity 
              style={styles.quickActionBtn}
              onPress={() => setShowHolidayModal(true)}
              data-testid="timings-holidays-btn"
            >
              <View style={[styles.quickActionIcon, { backgroundColor: '#DCFCE7' }]}>
                <Ionicons name="calendar" size={24} color="#22C55E" />
              </View>
              <Text style={styles.quickActionText}>Add Holiday</Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* Holidays List */}
        {holidays.length > 0 && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Upcoming Closures</Text>
            
            {holidays.map(holiday => (
              <View key={holiday.holiday_id} style={styles.holidayCard}>
                <View style={styles.holidayIcon}>
                  <Ionicons name="calendar" size={20} color="#6366F1" />
                </View>
                <View style={styles.holidayContent}>
                  <Text style={styles.holidayName}>{holiday.name}</Text>
                  <Text style={styles.holidayDate}>
                    {holiday.date}{holiday.end_date ? ` - ${holiday.end_date}` : ''}
                  </Text>
                  {holiday.reason && (
                    <Text style={styles.holidayReason}>{holiday.reason}</Text>
                  )}
                </View>
                <TouchableOpacity onPress={() => deleteHoliday(holiday)}>
                  <Ionicons name="trash-outline" size={20} color="#EF4444" />
                </TouchableOpacity>
              </View>
            ))}
          </View>
        )}

        {/* Delivery Cutoff */}
        <View style={styles.section}>
          <View style={styles.deliveryCard}>
            <View style={styles.deliveryIcon}>
              <Ionicons name="bicycle" size={24} color="#6366F1" />
            </View>
            <View style={styles.deliveryContent}>
              <Text style={styles.deliveryTitle}>Delivery Cutoff</Text>
              <Text style={styles.deliverySubtitle}>
                Last order accepted: {deliveryCutoff} mins before closing
              </Text>
            </View>
          </View>
        </View>

        <View style={{ height: 100 }} />
      </ScrollView>

      {/* Edit Day Modal */}
      <Modal
        visible={showDayModal}
        animationType="slide"
        onRequestClose={() => setShowDayModal(false)}
      >
        <View style={[styles.modalContainer, { paddingTop: insets.top }]} data-testid="timings-edit-day-modal">
          <View style={styles.modalHeader}>
            <TouchableOpacity onPress={() => setShowDayModal(false)}>
              <Ionicons name="close" size={24} color="#374151" />
            </TouchableOpacity>
            <Text style={styles.modalTitle}>{selectedDay ? DAY_LABELS[selectedDay.day] : ''}</Text>
            <TouchableOpacity onPress={saveDaySchedule} disabled={saving}>
              <Text style={[styles.modalSaveText, saving && { opacity: 0.5 }]}>Save</Text>
            </TouchableOpacity>
          </View>

          <ScrollView style={styles.modalContent} showsVerticalScrollIndicator={false}>
            {/* Open/Closed Toggle */}
            <View style={styles.toggleSection}>
              <Text style={styles.toggleLabel}>Shop Status</Text>
              <View style={styles.toggleRow}>
                <TouchableOpacity
                  style={[styles.toggleOption, dayForm.is_open && styles.toggleOptionActive]}
                  onPress={() => setDayForm(prev => ({ ...prev, is_open: true }))}
                >
                  <Ionicons 
                    name={dayForm.is_open ? 'radio-button-on' : 'radio-button-off'} 
                    size={20} 
                    color={dayForm.is_open ? '#6366F1' : '#9CA3AF'} 
                  />
                  <Text style={[styles.toggleText, dayForm.is_open && styles.toggleTextActive]}>Open</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={[styles.toggleOption, !dayForm.is_open && styles.toggleOptionActive]}
                  onPress={() => setDayForm(prev => ({ ...prev, is_open: false }))}
                >
                  <Ionicons 
                    name={!dayForm.is_open ? 'radio-button-on' : 'radio-button-off'} 
                    size={20} 
                    color={!dayForm.is_open ? '#EF4444' : '#9CA3AF'} 
                  />
                  <Text style={[styles.toggleText, !dayForm.is_open && { color: '#EF4444' }]}>Closed</Text>
                </TouchableOpacity>
              </View>
            </View>

            {dayForm.is_open && (
              <>
                {/* Operating Hours */}
                <View style={styles.formSection}>
                  <Text style={styles.formSectionTitle}>Operating Hours</Text>
                  {renderTimeSelector('Opening Time', dayForm.open_time, (time) => setDayForm(prev => ({ ...prev, open_time: time })))}
                  {renderTimeSelector('Closing Time', dayForm.close_time, (time) => setDayForm(prev => ({ ...prev, close_time: time })))}
                </View>

                {/* Break Time */}
                <View style={styles.breakSection}>
                  <View style={styles.breakHeader}>
                    <Text style={styles.formSectionTitle}>Break Time</Text>
                    <Switch
                      value={dayForm.has_break}
                      onValueChange={(value) => setDayForm(prev => ({ ...prev, has_break: value }))}
                      trackColor={{ false: '#E5E7EB', true: '#A5B4FC' }}
                      thumbColor={dayForm.has_break ? '#6366F1' : '#9CA3AF'}
                    />
                  </View>
                  
                  {dayForm.has_break && (
                    <>
                      {renderTimeSelector('Break Start', dayForm.break_start, (time) => setDayForm(prev => ({ ...prev, break_start: time })))}
                      {renderTimeSelector('Break End', dayForm.break_end, (time) => setDayForm(prev => ({ ...prev, break_end: time })))}
                    </>
                  )}
                </View>

                {/* Apply to all weekdays */}
                <View style={styles.applyAllSection}>
                  <Switch
                    value={dayForm.apply_to_all_weekdays}
                    onValueChange={(value) => setDayForm(prev => ({ ...prev, apply_to_all_weekdays: value }))}
                    trackColor={{ false: '#E5E7EB', true: '#A5B4FC' }}
                    thumbColor={dayForm.apply_to_all_weekdays ? '#6366F1' : '#9CA3AF'}
                  />
                  <Text style={styles.applyAllText}>Apply to all weekdays (Mon-Fri)</Text>
                </View>
              </>
            )}
          </ScrollView>
        </View>
      </Modal>

      {/* Add Holiday Modal */}
      <Modal
        visible={showHolidayModal}
        animationType="slide"
        transparent
        onRequestClose={() => setShowHolidayModal(false)}
      >
        <View style={styles.bottomModalOverlay}>
          <View style={[styles.bottomModal, { paddingBottom: insets.bottom + 20 }]}>
            <View style={styles.bottomModalHandle} />
            <Text style={styles.bottomModalTitle}>Add Holiday</Text>
            
            <TextInput
              style={styles.input}
              placeholder="Holiday Name (e.g., Christmas)"
              placeholderTextColor="#9CA3AF"
              value={holidayForm.name}
              onChangeText={(text) => setHolidayForm(prev => ({ ...prev, name: text }))}
            />
            
            <TextInput
              style={styles.input}
              placeholder="Date (YYYY-MM-DD)"
              placeholderTextColor="#9CA3AF"
              value={holidayForm.date}
              onChangeText={(text) => setHolidayForm(prev => ({ ...prev, date: text }))}
            />
            
            <TextInput
              style={styles.input}
              placeholder="End Date (optional, for multi-day)"
              placeholderTextColor="#9CA3AF"
              value={holidayForm.end_date}
              onChangeText={(text) => setHolidayForm(prev => ({ ...prev, end_date: text }))}
            />
            
            <TextInput
              style={styles.input}
              placeholder="Reason (optional)"
              placeholderTextColor="#9CA3AF"
              value={holidayForm.reason}
              onChangeText={(text) => setHolidayForm(prev => ({ ...prev, reason: text }))}
            />
            
            <View style={styles.bottomModalButtons}>
              <TouchableOpacity 
                style={styles.bottomModalCancelBtn}
                onPress={() => setShowHolidayModal(false)}
              >
                <Text style={styles.bottomModalCancelText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity 
                style={[styles.bottomModalSaveBtn, saving && { opacity: 0.5 }]}
                onPress={addHoliday}
                disabled={saving}
              >
                {saving ? (
                  <ActivityIndicator color="#FFFFFF" size="small" />
                ) : (
                  <Text style={styles.bottomModalSaveText}>Add Holiday</Text>
                )}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* Close Early Modal */}
      <Modal
        visible={showCloseEarlyModal}
        animationType="slide"
        transparent
        onRequestClose={() => setShowCloseEarlyModal(false)}
      >
        <View style={styles.bottomModalOverlay}>
          <View style={[styles.bottomModal, { paddingBottom: insets.bottom + 20 }]}>
            <View style={styles.bottomModalHandle} />
            <Text style={styles.bottomModalTitle}>Close Shop Early Today</Text>
            
            <View style={styles.closeEarlyTimeSection}>
              <Text style={styles.closeEarlyLabel}>Closing Time</Text>
              {renderTimeSelector('', closeEarlyTime, setCloseEarlyTime)}
            </View>
            
            <TextInput
              style={styles.input}
              placeholder="Reason (optional)"
              placeholderTextColor="#9CA3AF"
              value={closeEarlyReason}
              onChangeText={setCloseEarlyReason}
            />
            
            <View style={styles.bottomModalButtons}>
              <TouchableOpacity 
                style={styles.bottomModalCancelBtn}
                onPress={() => setShowCloseEarlyModal(false)}
              >
                <Text style={styles.bottomModalCancelText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity 
                style={[styles.bottomModalSaveBtn, { backgroundColor: '#F59E0B' }, saving && { opacity: 0.5 }]}
                onPress={closeShopEarly}
                disabled={saving}
              >
                {saving ? (
                  <ActivityIndicator color="#FFFFFF" size="small" />
                ) : (
                  <Text style={styles.bottomModalSaveText}>Close Early</Text>
                )}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F8FAFC',
  },
  centered: {
    justifyContent: 'center',
    alignItems: 'center',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: '#FFFFFF',
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
  },
  backBtn: {
    width: 40,
    height: 40,
    justifyContent: 'center',
    alignItems: 'center',
  },
  headerTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: '#111827',
  },
  scrollView: {
    flex: 1,
  },
  statusCard: {
    flexDirection: 'row',
    alignItems: 'center',
    margin: 16,
    padding: 16,
    borderRadius: 16,
    backgroundColor: '#FFFFFF',
  },
  statusCardOpen: {
    borderWidth: 2,
    borderColor: '#22C55E',
    backgroundColor: '#F0FDF4',
  },
  statusCardClosed: {
    borderWidth: 2,
    borderColor: '#E5E7EB',
  },
  statusIconContainer: {
    width: 56,
    height: 56,
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 14,
  },
  statusContent: {
    flex: 1,
  },
  statusTitle: {
    fontSize: 18,
    fontWeight: '800',
    color: '#374151',
  },
  statusTitleOpen: {
    color: '#22C55E',
  },
  statusSubtitle: {
    fontSize: 14,
    color: '#6B7280',
    marginTop: 4,
  },
  section: {
    marginHorizontal: 16,
    marginBottom: 24,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#111827',
    marginBottom: 12,
  },
  dayCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    borderRadius: 14,
    padding: 14,
    marginBottom: 8,
  },
  dayHeader: {
    flex: 1,
  },
  dayName: {
    fontSize: 15,
    fontWeight: '600',
    color: '#111827',
    marginBottom: 4,
  },
  dayStatus: {
    alignSelf: 'flex-start',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 6,
  },
  dayStatusOpen: {
    backgroundColor: '#DCFCE7',
  },
  dayStatusClosed: {
    backgroundColor: '#FEE2E2',
  },
  dayStatusText: {
    fontSize: 11,
    fontWeight: '600',
    color: '#EF4444',
  },
  dayStatusTextOpen: {
    color: '#22C55E',
  },
  dayTimes: {
    alignItems: 'flex-end',
    marginRight: 8,
  },
  dayTimeText: {
    fontSize: 13,
    fontWeight: '500',
    color: '#374151',
  },
  dayBreakText: {
    fontSize: 11,
    color: '#9CA3AF',
    marginTop: 2,
  },
  dayClosedText: {
    fontSize: 13,
    color: '#9CA3AF',
    marginRight: 8,
  },
  dayArrow: {
    marginLeft: 4,
  },
  quickActionsRow: {
    flexDirection: 'row',
    gap: 12,
  },
  quickActionBtn: {
    flex: 1,
    backgroundColor: '#FFFFFF',
    borderRadius: 14,
    padding: 16,
    alignItems: 'center',
  },
  quickActionIcon: {
    width: 52,
    height: 52,
    borderRadius: 16,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 10,
  },
  quickActionText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#374151',
  },
  holidayCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    borderRadius: 14,
    padding: 14,
    marginBottom: 8,
  },
  holidayIcon: {
    width: 40,
    height: 40,
    backgroundColor: '#EEF2FF',
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  holidayContent: {
    flex: 1,
  },
  holidayName: {
    fontSize: 15,
    fontWeight: '600',
    color: '#111827',
  },
  holidayDate: {
    fontSize: 13,
    color: '#6B7280',
    marginTop: 2,
  },
  holidayReason: {
    fontSize: 12,
    color: '#9CA3AF',
    marginTop: 2,
  },
  deliveryCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    borderRadius: 14,
    padding: 16,
  },
  deliveryIcon: {
    width: 48,
    height: 48,
    backgroundColor: '#EEF2FF',
    borderRadius: 14,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 14,
  },
  deliveryContent: {
    flex: 1,
  },
  deliveryTitle: {
    fontSize: 15,
    fontWeight: '600',
    color: '#111827',
  },
  deliverySubtitle: {
    fontSize: 13,
    color: '#6B7280',
    marginTop: 2,
  },
  // Modal styles
  modalContainer: {
    flex: 1,
    backgroundColor: '#F8FAFC',
  },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 14,
    backgroundColor: '#FFFFFF',
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#111827',
  },
  modalSaveText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#6366F1',
  },
  modalContent: {
    flex: 1,
    padding: 16,
  },
  toggleSection: {
    marginBottom: 24,
  },
  toggleLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: '#374151',
    marginBottom: 10,
  },
  toggleRow: {
    flexDirection: 'row',
    gap: 12,
  },
  toggleOption: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    padding: 14,
    borderWidth: 1,
    borderColor: '#E5E7EB',
    gap: 8,
  },
  toggleOptionActive: {
    borderColor: '#6366F1',
    backgroundColor: '#EEF2FF',
  },
  toggleText: {
    fontSize: 15,
    fontWeight: '600',
    color: '#6B7280',
  },
  toggleTextActive: {
    color: '#6366F1',
  },
  formSection: {
    marginBottom: 24,
  },
  formSectionTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#374151',
    marginBottom: 12,
  },
  timeSelectorContainer: {
    marginBottom: 16,
  },
  timeSelectorLabel: {
    fontSize: 13,
    color: '#6B7280',
    marginBottom: 8,
  },
  timeSelector: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    padding: 10,
  },
  timePicker: {
    flexDirection: 'row',
    gap: 4,
  },
  timeOption: {
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 8,
  },
  timeOptionActive: {
    backgroundColor: '#6366F1',
  },
  timeOptionText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#6B7280',
  },
  timeOptionTextActive: {
    color: '#FFFFFF',
  },
  timeSeparator: {
    fontSize: 20,
    fontWeight: '700',
    color: '#374151',
    marginHorizontal: 8,
  },
  timeDisplay: {
    fontSize: 14,
    fontWeight: '600',
    color: '#6366F1',
    textAlign: 'center',
    marginTop: 8,
  },
  breakSection: {
    marginBottom: 24,
  },
  breakHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 12,
  },
  applyAllSection: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    padding: 14,
    gap: 12,
  },
  applyAllText: {
    fontSize: 14,
    fontWeight: '500',
    color: '#374151',
    flex: 1,
  },
  // Bottom modal styles
  bottomModalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'flex-end',
  },
  bottomModal: {
    backgroundColor: '#FFFFFF',
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    padding: 20,
  },
  bottomModalHandle: {
    width: 40,
    height: 4,
    backgroundColor: '#D1D5DB',
    borderRadius: 2,
    alignSelf: 'center',
    marginBottom: 16,
  },
  bottomModalTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#111827',
    textAlign: 'center',
    marginBottom: 20,
  },
  input: {
    backgroundColor: '#F9FAFB',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#E5E7EB',
    paddingHorizontal: 14,
    paddingVertical: 14,
    fontSize: 16,
    color: '#111827',
    marginBottom: 12,
  },
  bottomModalButtons: {
    flexDirection: 'row',
    gap: 12,
    marginTop: 8,
  },
  bottomModalCancelBtn: {
    flex: 1,
    backgroundColor: '#F3F4F6',
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: 'center',
  },
  bottomModalCancelText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#6B7280',
  },
  bottomModalSaveBtn: {
    flex: 1,
    backgroundColor: '#6366F1',
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: 'center',
  },
  bottomModalSaveText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFFFFF',
  },
  closeEarlyTimeSection: {
    marginBottom: 12,
  },
  closeEarlyLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: '#374151',
    marginBottom: 8,
  },
});
