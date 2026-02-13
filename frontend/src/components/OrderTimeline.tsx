import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { format } from 'date-fns';

interface TimelineStep {
  key: string;
  label: string;
  icon: string;
  completed: boolean;
  current: boolean;
  timestamp?: string;
}

interface OrderTimelineProps {
  steps: TimelineStep[];
  status: string;
}

const STATUS_CONFIG: Record<string, { color: string; bgColor: string; icon: string }> = {
  placed: { color: '#3B82F6', bgColor: '#EFF6FF', icon: 'receipt' },
  pending: { color: '#F59E0B', bgColor: '#FFFBEB', icon: 'time' },
  confirmed: { color: '#22C55E', bgColor: '#F0FDF4', icon: 'checkmark-circle' },
  preparing: { color: '#8B5CF6', bgColor: '#F5F3FF', icon: 'flame' },
  ready: { color: '#22C55E', bgColor: '#F0FDF4', icon: 'cube' },
  awaiting_pickup: { color: '#06B6D4', bgColor: '#ECFEFF', icon: 'hourglass' },
  picked_up: { color: '#6366F1', bgColor: '#EEF2FF', icon: 'bicycle' },
  out_for_delivery: { color: '#EC4899', bgColor: '#FDF2F8', icon: 'navigate' },
  delivered: { color: '#22C55E', bgColor: '#F0FDF4', icon: 'checkmark-done-circle' },
  cancelled: { color: '#EF4444', bgColor: '#FEF2F2', icon: 'close-circle' },
  rejected: { color: '#EF4444', bgColor: '#FEF2F2', icon: 'close-circle' },
};

export const OrderTimeline: React.FC<OrderTimelineProps> = ({ steps, status }) => {
  const completedSteps = steps.filter(s => s.completed).length;
  const totalSteps = steps.length;
  const progressPercent = Math.round((completedSteps / totalSteps) * 100);
  
  const currentConfig = STATUS_CONFIG[status] || STATUS_CONFIG.pending;

  return (
    <View style={styles.container}>
      {/* Progress Header */}
      <View style={styles.progressHeader}>
        <View style={styles.progressInfo}>
          <Text style={styles.progressTitle}>Order Progress</Text>
          <Text style={[styles.progressPercent, { color: currentConfig.color }]}>
            {progressPercent}%
          </Text>
        </View>
        <View style={styles.progressBarContainer}>
          <View style={styles.progressBarBg}>
            <View 
              style={[
                styles.progressBarFill, 
                { 
                  width: `${progressPercent}%`,
                  backgroundColor: currentConfig.color 
                }
              ]} 
            />
          </View>
        </View>
      </View>

      {/* Timeline Steps */}
      <View style={styles.timeline}>
        {steps.map((step, index) => {
          const isLast = index === steps.length - 1;
          const stepConfig = STATUS_CONFIG[step.key] || STATUS_CONFIG.pending;
          
          return (
            <View key={step.key} style={styles.stepContainer}>
              {/* Connector Line */}
              {!isLast && (
                <View style={styles.connectorContainer}>
                  <View 
                    style={[
                      styles.connectorLine,
                      step.completed && styles.connectorLineCompleted
                    ]} 
                  />
                </View>
              )}
              
              {/* Step Circle */}
              <View 
                style={[
                  styles.stepCircle,
                  step.completed && { backgroundColor: '#22C55E', borderColor: '#22C55E' },
                  step.current && { backgroundColor: currentConfig.bgColor, borderColor: currentConfig.color, borderWidth: 3 },
                  !step.completed && !step.current && styles.stepCirclePending
                ]}
              >
                {step.completed ? (
                  <Ionicons name="checkmark" size={16} color="#FFFFFF" />
                ) : (
                  <Ionicons 
                    name={step.icon as any} 
                    size={14} 
                    color={step.current ? currentConfig.color : '#9CA3AF'} 
                  />
                )}
              </View>

              {/* Step Content */}
              <View style={styles.stepContent}>
                <Text 
                  style={[
                    styles.stepLabel,
                    step.completed && styles.stepLabelCompleted,
                    step.current && { color: currentConfig.color, fontWeight: '700' }
                  ]}
                >
                  {step.label}
                </Text>
                {step.timestamp && (
                  <Text style={styles.stepTime}>
                    {format(new Date(step.timestamp), 'h:mm a')}
                  </Text>
                )}
                {step.current && (
                  <View style={[styles.currentBadge, { backgroundColor: currentConfig.bgColor }]}>
                    <View style={[styles.currentDot, { backgroundColor: currentConfig.color }]} />
                    <Text style={[styles.currentText, { color: currentConfig.color }]}>Current</Text>
                  </View>
                )}
              </View>
            </View>
          );
        })}
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    backgroundColor: '#FFFFFF',
    marginHorizontal: 16,
    marginTop: 12,
    padding: 16,
    borderRadius: 16,
  },
  progressHeader: {
    marginBottom: 16,
  },
  progressInfo: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  progressTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#111827',
  },
  progressPercent: {
    fontSize: 16,
    fontWeight: '700',
  },
  progressBarContainer: {
    height: 8,
    borderRadius: 4,
    overflow: 'hidden',
  },
  progressBarBg: {
    flex: 1,
    backgroundColor: '#E5E7EB',
    borderRadius: 4,
  },
  progressBarFill: {
    height: '100%',
    borderRadius: 4,
  },
  timeline: {
    paddingTop: 8,
  },
  stepContainer: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    minHeight: 48,
    position: 'relative',
  },
  connectorContainer: {
    position: 'absolute',
    left: 14,
    top: 32,
    bottom: -8,
    width: 2,
  },
  connectorLine: {
    flex: 1,
    backgroundColor: '#E5E7EB',
    borderRadius: 1,
  },
  connectorLineCompleted: {
    backgroundColor: '#22C55E',
  },
  stepCircle: {
    width: 30,
    height: 30,
    borderRadius: 15,
    backgroundColor: '#F3F4F6',
    borderWidth: 2,
    borderColor: '#E5E7EB',
    justifyContent: 'center',
    alignItems: 'center',
    zIndex: 1,
  },
  stepCirclePending: {
    backgroundColor: '#F9FAFB',
    borderColor: '#D1D5DB',
  },
  stepContent: {
    flex: 1,
    marginLeft: 12,
    paddingBottom: 16,
  },
  stepLabel: {
    fontSize: 14,
    fontWeight: '500',
    color: '#9CA3AF',
  },
  stepLabelCompleted: {
    color: '#374151',
    fontWeight: '600',
  },
  stepTime: {
    fontSize: 12,
    color: '#9CA3AF',
    marginTop: 2,
  },
  currentBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 10,
    marginTop: 6,
    gap: 4,
  },
  currentDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  currentText: {
    fontSize: 11,
    fontWeight: '700',
  },
});

export default OrderTimeline;
