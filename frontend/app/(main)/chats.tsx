import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  RefreshControl,
  TextInput,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { chatAPI } from '../../src/utils/api';
import { ChatRoom, Message } from '../../src/types';
import { useAuthStore } from '../../src/store/authStore';
import { format } from 'date-fns';

export default function ChatsScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ room?: string }>();
  const insets = useSafeAreaInsets();
  const { user } = useAuthStore();
  const [rooms, setRooms] = useState<ChatRoom[]>([]);
  const [selectedRoom, setSelectedRoom] = useState<ChatRoom | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [messageText, setMessageText] = useState('');
  const [sending, setSending] = useState(false);
  const flatListRef = useRef<FlatList>(null);

  const loadRooms = async () => {
    try {
      const response = await chatAPI.getRooms();
      setRooms(response.data);
      
      // If room param is provided, open that room
      if (params.room) {
        const room = response.data.find((r: ChatRoom) => r.room_id === params.room);
        if (room) {
          setSelectedRoom(room);
          loadMessages(room.room_id);
        }
      }
    } catch (error) {
      console.error('Load rooms error:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadMessages = async (roomId: string) => {
    try {
      const response = await chatAPI.getMessages(roomId);
      setMessages(response.data);
    } catch (error) {
      console.error('Load messages error:', error);
    }
  };

  useEffect(() => {
    loadRooms();
  }, []);

  useEffect(() => {
    if (selectedRoom) {
      loadMessages(selectedRoom.room_id);
      // Poll for new messages every 3 seconds
      const interval = setInterval(() => loadMessages(selectedRoom.room_id), 3000);
      return () => clearInterval(interval);
    }
  }, [selectedRoom]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    if (selectedRoom) {
      await loadMessages(selectedRoom.room_id);
    } else {
      await loadRooms();
    }
    setRefreshing(false);
  }, [selectedRoom]);

  const handleSendMessage = async () => {
    if (!messageText.trim() || !selectedRoom) return;

    setSending(true);
    try {
      await chatAPI.sendMessage(selectedRoom.room_id, messageText.trim());
      setMessageText('');
      await loadMessages(selectedRoom.room_id);
      flatListRef.current?.scrollToEnd();
    } catch (error) {
      console.error('Send message error:', error);
    } finally {
      setSending(false);
    }
  };

  const renderRoom = ({ item }: { item: ChatRoom }) => (
    <TouchableOpacity
      style={styles.roomCard}
      onPress={() => {
        setSelectedRoom(item);
        loadMessages(item.room_id);
      }}
    >
      <View style={styles.roomAvatar}>
        <Ionicons name="person" size={24} color="#6366F1" />
      </View>
      <View style={styles.roomInfo}>
        <Text style={styles.roomTitle} numberOfLines={1}>
          {item.customer?.name || 'Customer'}
        </Text>
        <Text style={styles.roomSubtitle} numberOfLines={1}>
          {item.wish_title || 'Chat'}
        </Text>
        {item.last_message && (
          <Text style={styles.lastMessage} numberOfLines={1}>
            {item.last_message.content}
          </Text>
        )}
      </View>
      <View style={styles.roomMeta}>
        <Text style={styles.roomTime}>
          {format(new Date(item.created_at), 'MMM d')}
        </Text>
      </View>
    </TouchableOpacity>
  );

  const renderMessage = ({ item }: { item: Message }) => {
    const isMe = item.sender_id === user?.user_id;
    return (
      <View style={[styles.messageRow, isMe && styles.messageRowMe]}>
        <View style={[styles.messageBubble, isMe ? styles.messageBubbleMe : styles.messageBubbleOther]}>
          <Text style={[styles.messageText, isMe && styles.messageTextMe]}>
            {item.content}
          </Text>
          <Text style={[styles.messageTime, isMe && styles.messageTimeMe]}>
            {format(new Date(item.created_at), 'h:mm a')}
          </Text>
        </View>
      </View>
    );
  };

  // Chat Detail View
  if (selectedRoom) {
    return (
      <View style={[styles.container, { paddingTop: insets.top }]}>
        <View style={styles.chatHeader}>
          <TouchableOpacity
            style={styles.backBtn}
            onPress={() => setSelectedRoom(null)}
          >
            <Ionicons name="arrow-back" size={24} color="#374151" />
          </TouchableOpacity>
          <View style={styles.chatHeaderInfo}>
            <Text style={styles.chatHeaderTitle}>
              {selectedRoom.customer?.name || 'Customer'}
            </Text>
            <Text style={styles.chatHeaderSubtitle}>
              {selectedRoom.wish_title}
            </Text>
          </View>
          <TouchableOpacity style={styles.callBtn}>
            <Ionicons name="call" size={22} color="#22C55E" />
          </TouchableOpacity>
        </View>

        <KeyboardAvoidingView
          style={styles.chatContainer}
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          keyboardVerticalOffset={Platform.OS === 'ios' ? 0 : 20}
        >
          <FlatList
            ref={flatListRef}
            data={messages}
            renderItem={renderMessage}
            keyExtractor={(item) => item.message_id}
            contentContainerStyle={styles.messagesList}
            refreshControl={
              <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
            }
            onContentSizeChange={() => flatListRef.current?.scrollToEnd()}
            ListEmptyComponent={
              <View style={styles.emptyMessages}>
                <Ionicons name="chatbubbles-outline" size={48} color="#D1D5DB" />
                <Text style={styles.emptyMessagesText}>No messages yet</Text>
              </View>
            }
          />

          <View style={styles.inputContainer}>
            <TextInput
              style={styles.messageInput}
              placeholder="Type a message..."
              placeholderTextColor="#9CA3AF"
              value={messageText}
              onChangeText={setMessageText}
              multiline
              maxLength={500}
            />
            <TouchableOpacity
              style={[styles.sendBtn, !messageText.trim() && styles.sendBtnDisabled]}
              onPress={handleSendMessage}
              disabled={!messageText.trim() || sending}
            >
              <Ionicons
                name="send"
                size={20}
                color={messageText.trim() ? '#FFFFFF' : '#9CA3AF'}
              />
            </TouchableOpacity>
          </View>
        </KeyboardAvoidingView>
      </View>
    );
  }

  // Room List View
  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      <View style={styles.header}>
        <Text style={styles.title}>Chats</Text>
      </View>

      <FlatList
        data={rooms}
        renderItem={renderRoom}
        keyExtractor={(item) => item.room_id}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
        ListEmptyComponent={
          <View style={styles.emptyState}>
            <Ionicons name="chatbubbles-outline" size={64} color="#D1D5DB" />
            <Text style={styles.emptyTitle}>No conversations</Text>
            <Text style={styles.emptySubtitle}>
              Customer chats will appear here
            </Text>
          </View>
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F9FAFB',
  },
  header: {
    paddingHorizontal: 20,
    paddingVertical: 16,
  },
  title: {
    fontSize: 28,
    fontWeight: '700',
    color: '#111827',
  },
  listContent: {
    paddingHorizontal: 16,
    paddingBottom: 100,
  },
  roomCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 16,
    marginBottom: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
    elevation: 2,
  },
  roomAvatar: {
    width: 48,
    height: 48,
    backgroundColor: '#EEF2FF',
    borderRadius: 24,
    justifyContent: 'center',
    alignItems: 'center',
  },
  roomInfo: {
    flex: 1,
    marginLeft: 12,
  },
  roomTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#111827',
  },
  roomSubtitle: {
    fontSize: 13,
    color: '#6366F1',
    marginTop: 2,
  },
  lastMessage: {
    fontSize: 13,
    color: '#6B7280',
    marginTop: 4,
  },
  roomMeta: {
    alignItems: 'flex-end',
  },
  roomTime: {
    fontSize: 12,
    color: '#9CA3AF',
  },
  emptyState: {
    alignItems: 'center',
    paddingVertical: 60,
  },
  emptyTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#374151',
    marginTop: 16,
  },
  emptySubtitle: {
    fontSize: 14,
    color: '#9CA3AF',
    marginTop: 4,
  },
  // Chat Detail Styles
  chatHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: '#FFFFFF',
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
  },
  backBtn: {
    width: 44,
    height: 44,
    justifyContent: 'center',
    alignItems: 'center',
  },
  chatHeaderInfo: {
    flex: 1,
    marginLeft: 8,
  },
  chatHeaderTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: '#111827',
  },
  chatHeaderSubtitle: {
    fontSize: 13,
    color: '#6B7280',
  },
  callBtn: {
    width: 44,
    height: 44,
    backgroundColor: '#DCFCE7',
    borderRadius: 22,
    justifyContent: 'center',
    alignItems: 'center',
  },
  chatContainer: {
    flex: 1,
  },
  messagesList: {
    padding: 16,
    paddingBottom: 8,
  },
  messageRow: {
    marginBottom: 12,
    alignItems: 'flex-start',
  },
  messageRowMe: {
    alignItems: 'flex-end',
  },
  messageBubble: {
    maxWidth: '80%',
    borderRadius: 16,
    padding: 12,
  },
  messageBubbleOther: {
    backgroundColor: '#FFFFFF',
    borderBottomLeftRadius: 4,
  },
  messageBubbleMe: {
    backgroundColor: '#6366F1',
    borderBottomRightRadius: 4,
  },
  messageText: {
    fontSize: 15,
    color: '#111827',
    lineHeight: 20,
  },
  messageTextMe: {
    color: '#FFFFFF',
  },
  messageTime: {
    fontSize: 11,
    color: '#9CA3AF',
    marginTop: 4,
    alignSelf: 'flex-end',
  },
  messageTimeMe: {
    color: 'rgba(255,255,255,0.7)',
  },
  emptyMessages: {
    alignItems: 'center',
    paddingVertical: 60,
  },
  emptyMessagesText: {
    fontSize: 14,
    color: '#9CA3AF',
    marginTop: 12,
  },
  inputContainer: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    padding: 12,
    backgroundColor: '#FFFFFF',
    borderTopWidth: 1,
    borderTopColor: '#E5E7EB',
    gap: 12,
  },
  messageInput: {
    flex: 1,
    backgroundColor: '#F3F4F6',
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingVertical: 10,
    fontSize: 15,
    color: '#111827',
    maxHeight: 100,
  },
  sendBtn: {
    width: 44,
    height: 44,
    backgroundColor: '#6366F1',
    borderRadius: 22,
    justifyContent: 'center',
    alignItems: 'center',
  },
  sendBtnDisabled: {
    backgroundColor: '#E5E7EB',
  },
});
