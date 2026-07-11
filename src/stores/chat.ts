import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { ChatMessage, QuickScene } from '@/types/chat'

export const useChatStore = defineStore('chat', () => {
  // ========== 状态 ==========
  const messages = ref<ChatMessage[]>([])
  const isStreaming = ref(false)
  const inputText = ref('')
  const quickScenes = ref<QuickScene[]>([
    { id: 'tired', label: '有点累', icon: 'Moon', promptTemplate: '我今天感觉有点累，能推荐一些放松的音乐吗？', scenario: 'relax' },
    { id: 'focus', label: '需要专注', icon: 'Aim', promptTemplate: '我需要集中注意力工作，来点专注音乐', scenario: 'focus' },
    { id: 'happy', label: '心情不错', icon: 'Sunny', promptTemplate: '今天心情很好，来点欢快的歌吧', scenario: 'relax' },
    { id: 'sleep', label: '失眠中', icon: 'MoonNight', promptTemplate: '我睡不着，能陪我聊聊天放点安静的曲子吗？', scenario: 'sleep' },
    { id: 'commute', label: '在路上', icon: 'Van', promptTemplate: '我在通勤路上，推荐点路上听的歌', scenario: 'commute' },
    { id: 'workout', label: '运动一下', icon: 'Bicycle', promptTemplate: '我刚跑完步，来点有节奏的音乐', scenario: 'workout' },
  ])

  // ========== 计算属性 ==========
  const lastMessage = computed<ChatMessage | null>(() => messages.value.length > 0 ? messages.value[messages.value.length - 1] : null)
  const messageCount = computed(() => messages.value.length)

  // ========== 方法 ==========
  function addMessage(msg: ChatMessage) { messages.value.push(msg) }
  function addUserMessage(text: string): ChatMessage {
    const msg: ChatMessage = { id: `msg_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`, role: 'user', content: text, timestamp: new Date().toISOString() }
    messages.value.push(msg)
    return msg
  }
  function setInputText(text: string) { inputText.value = text }
  function clearHistory() { messages.value = [] }

  return {
    messages, isStreaming, inputText, quickScenes,
    lastMessage, messageCount,
    addMessage, addUserMessage, setInputText, clearHistory,
  }
})
