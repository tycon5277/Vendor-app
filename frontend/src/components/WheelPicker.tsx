import React, { useRef, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Dimensions,
  NativeSyntheticEvent,
  NativeScrollEvent,
} from 'react-native';

const ITEM_HEIGHT = 44;
const VISIBLE_ITEMS = 5;
const PICKER_HEIGHT = ITEM_HEIGHT * VISIBLE_ITEMS;

interface WheelPickerProps {
  items: { value: string; label: string }[];
  selectedValue: string;
  onValueChange: (value: string) => void;
  width?: number;
}

export const WheelPicker: React.FC<WheelPickerProps> = ({
  items,
  selectedValue,
  onValueChange,
  width = 80,
}) => {
  const scrollRef = useRef<ScrollView>(null);
  const selectedIndex = items.findIndex(item => item.value === selectedValue);

  useEffect(() => {
    if (scrollRef.current && selectedIndex >= 0) {
      scrollRef.current.scrollTo({
        y: selectedIndex * ITEM_HEIGHT,
        animated: false,
      });
    }
  }, []);

  const handleScrollEnd = (event: NativeSyntheticEvent<NativeScrollEvent>) => {
    const y = event.nativeEvent.contentOffset.y;
    const index = Math.round(y / ITEM_HEIGHT);
    const clampedIndex = Math.max(0, Math.min(index, items.length - 1));
    
    if (items[clampedIndex] && items[clampedIndex].value !== selectedValue) {
      onValueChange(items[clampedIndex].value);
    }
    
    // Snap to nearest item
    scrollRef.current?.scrollTo({
      y: clampedIndex * ITEM_HEIGHT,
      animated: true,
    });
  };

  const handleItemPress = (index: number) => {
    scrollRef.current?.scrollTo({
      y: index * ITEM_HEIGHT,
      animated: true,
    });
    if (items[index]) {
      onValueChange(items[index].value);
    }
  };

  return (
    <View style={[styles.container, { width }]}>
      <View style={styles.highlightBar} />
      <ScrollView
        ref={scrollRef}
        showsVerticalScrollIndicator={false}
        snapToInterval={ITEM_HEIGHT}
        decelerationRate="fast"
        onMomentumScrollEnd={handleScrollEnd}
        onScrollEndDrag={handleScrollEnd}
        contentContainerStyle={{
          paddingVertical: ITEM_HEIGHT * 2,
        }}
      >
        {items.map((item, index) => {
          const isSelected = item.value === selectedValue;
          return (
            <TouchableOpacity
              key={item.value}
              style={styles.item}
              onPress={() => handleItemPress(index)}
              activeOpacity={0.7}
            >
              <Text
                style={[
                  styles.itemText,
                  isSelected && styles.itemTextSelected,
                ]}
              >
                {item.label}
              </Text>
            </TouchableOpacity>
          );
        })}
      </ScrollView>
    </View>
  );
};

// Date Picker using wheel style
interface DateWheelPickerProps {
  date: Date;
  onDateChange: (date: Date) => void;
  minYear?: number;
  maxYear?: number;
}

export const DateWheelPicker: React.FC<DateWheelPickerProps> = ({
  date,
  onDateChange,
  minYear = 2024,
  maxYear = 2030,
}) => {
  const days = Array.from({ length: 31 }, (_, i) => ({
    value: (i + 1).toString().padStart(2, '0'),
    label: (i + 1).toString(),
  }));

  const months = [
    { value: '01', label: 'Jan' },
    { value: '02', label: 'Feb' },
    { value: '03', label: 'Mar' },
    { value: '04', label: 'Apr' },
    { value: '05', label: 'May' },
    { value: '06', label: 'Jun' },
    { value: '07', label: 'Jul' },
    { value: '08', label: 'Aug' },
    { value: '09', label: 'Sep' },
    { value: '10', label: 'Oct' },
    { value: '11', label: 'Nov' },
    { value: '12', label: 'Dec' },
  ];

  const years = Array.from({ length: maxYear - minYear + 1 }, (_, i) => ({
    value: (minYear + i).toString(),
    label: (minYear + i).toString(),
  }));

  const currentDay = date.getDate().toString().padStart(2, '0');
  const currentMonth = (date.getMonth() + 1).toString().padStart(2, '0');
  const currentYear = date.getFullYear().toString();

  const handleChange = (type: 'day' | 'month' | 'year', value: string) => {
    const newDate = new Date(date);
    if (type === 'day') {
      newDate.setDate(parseInt(value));
    } else if (type === 'month') {
      newDate.setMonth(parseInt(value) - 1);
    } else {
      newDate.setFullYear(parseInt(value));
    }
    onDateChange(newDate);
  };

  return (
    <View style={styles.datePickerContainer}>
      <WheelPicker
        items={days}
        selectedValue={currentDay}
        onValueChange={(v) => handleChange('day', v)}
        width={60}
      />
      <WheelPicker
        items={months}
        selectedValue={currentMonth}
        onValueChange={(v) => handleChange('month', v)}
        width={70}
      />
      <WheelPicker
        items={years}
        selectedValue={currentYear}
        onValueChange={(v) => handleChange('year', v)}
        width={80}
      />
    </View>
  );
};

// Time Picker using wheel style
interface TimeWheelPickerProps {
  time: string; // HH:mm format
  onTimeChange: (time: string) => void;
  minuteInterval?: 1 | 5 | 15 | 30;
}

export const TimeWheelPicker: React.FC<TimeWheelPickerProps> = ({
  time,
  onTimeChange,
  minuteInterval = 15,
}) => {
  const hours = Array.from({ length: 24 }, (_, i) => ({
    value: i.toString().padStart(2, '0'),
    label: i.toString().padStart(2, '0'),
  }));

  const minuteCount = 60 / minuteInterval;
  const minutes = Array.from({ length: minuteCount }, (_, i) => ({
    value: (i * minuteInterval).toString().padStart(2, '0'),
    label: (i * minuteInterval).toString().padStart(2, '0'),
  }));

  const [currentHour, currentMinute] = time.split(':');

  const handleChange = (type: 'hour' | 'minute', value: string) => {
    if (type === 'hour') {
      onTimeChange(`${value}:${currentMinute}`);
    } else {
      onTimeChange(`${currentHour}:${value}`);
    }
  };

  // Format for display (12hr with AM/PM)
  const hour12 = parseInt(currentHour) % 12 || 12;
  const ampm = parseInt(currentHour) < 12 ? 'AM' : 'PM';

  return (
    <View style={styles.timePickerContainer}>
      <WheelPicker
        items={hours}
        selectedValue={currentHour}
        onValueChange={(v) => handleChange('hour', v)}
        width={60}
      />
      <Text style={styles.colonSeparator}>:</Text>
      <WheelPicker
        items={minutes}
        selectedValue={currentMinute}
        onValueChange={(v) => handleChange('minute', v)}
        width={60}
      />
      <View style={styles.timePreview}>
        <Text style={styles.timePreviewText}>{hour12}:{currentMinute}</Text>
        <Text style={styles.ampmText}>{ampm}</Text>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    height: PICKER_HEIGHT,
    overflow: 'hidden',
    backgroundColor: '#F9FAFB',
    borderRadius: 12,
  },
  highlightBar: {
    position: 'absolute',
    top: ITEM_HEIGHT * 2,
    left: 4,
    right: 4,
    height: ITEM_HEIGHT,
    backgroundColor: '#EEF2FF',
    borderRadius: 8,
    zIndex: -1,
  },
  item: {
    height: ITEM_HEIGHT,
    justifyContent: 'center',
    alignItems: 'center',
  },
  itemText: {
    fontSize: 16,
    color: '#9CA3AF',
    fontWeight: '500',
  },
  itemTextSelected: {
    fontSize: 18,
    color: '#6366F1',
    fontWeight: '700',
  },
  datePickerContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 12,
    borderWidth: 1,
    borderColor: '#E5E7EB',
  },
  timePickerContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 4,
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 12,
    borderWidth: 1,
    borderColor: '#E5E7EB',
  },
  colonSeparator: {
    fontSize: 24,
    fontWeight: '700',
    color: '#6366F1',
    marginHorizontal: 4,
  },
  timePreview: {
    marginLeft: 16,
    alignItems: 'center',
    backgroundColor: '#EEF2FF',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 8,
  },
  timePreviewText: {
    fontSize: 18,
    fontWeight: '700',
    color: '#6366F1',
  },
  ampmText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#818CF8',
  },
});

export default WheelPicker;
