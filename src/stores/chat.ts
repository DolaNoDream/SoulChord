import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { ChatMessage, QuickScene } from '@/types/chat'

export const useChatStore = defineStore('chat', () => {
  // ========== 状态 ==========
  const messages = ref<ChatMessage[]>([])
  const isStreaming = ref(false)
  const currentStreamingMessage = ref('')
  const inputText = ref('')
  const conversationId = ref<string | null>(null)

  const quickScenes = ref<QuickScene[]>([
    { id: 'tired', label: '有点累', icon: 'Moon', promptTemplate: '我今天感觉有点累，能推荐一些放松的音乐吗？', scenario: 'relax' },
    { id: 'focus', label: '需要专注', icon: 'Aim', promptTemplate: '我需要集中注意力工作，来点专注音乐', scenario: 'focus' },
    { id: 'happy', label: '心情不错', icon: 'Sunny', promptTemplate: '今天心情很好，来点欢快的歌吧', scenario: 'relax' },
    { id: 'sleep', label: '失眠中', icon: 'MoonNight', promptTemplate: '我睡不着，能陪我聊聊天放点安静的曲子吗？', scenario: 'sleep' },
    { id: 'commute', label: '在路上', icon: 'Van', promptTemplate: '我在通勤路上，推荐点路上听的歌', scenario: 'commute' },
    { id: 'workout', label: '运动一下', icon: 'Bicycle', promptTemplate: '我刚跑完步，来点有节奏的音乐', scenario: 'workout' },
  ])

  // ========== 计算属性 ==========
  const lastMessage = computed<ChatMessage | null>(() => {
    return messages.value.length > 0 ? messages.value[messages.value.length - 1] : null
  })

  const messageCount = computed(() => messages.value.length)

  // ========== 方法 ==========

  /** 添加一条消息 */
  function addMessage(msg: ChatMessage) {
    messages.value.push(msg)
  }

  /** 添加用户消息 */
  function addUserMessage(text: string) {
    const msg: ChatMessage = {
      id: generateId(),
      role: 'user',
      content: text,
      timestamp: new Date().toISOString(),
    }
    messages.value.push(msg)
    return msg
  }

  /** 开始流式 AI 回复 */
  function startStreaming() {
    isStreaming.value = true
    currentStreamingMessage.value = ''
  }

  /** 追加流式内容 */
  function appendStreamChunk(chunk: string) {
    currentStreamingMessage.value += chunk
  }

  /** 完成流式回复 */
  function finalizeStream(attachments?: ChatMessage['attachments']) {
    const msg: ChatMessage = {
      id: generateId(),
      role: 'assistant',
      content: currentStreamingMessage.value,
      timestamp: new Date().toISOString(),
      attachments,
    }
    messages.value.push(msg)
    isStreaming.value = false
    currentStreamingMessage.value = ''
    return msg
  }

  /** 设置输入文本 */
  function setInputText(text: string) {
    inputText.value = text
  }

  /** 清空历史 */
  function clearHistory() {
    messages.value = []
    conversationId.value = null
  }

  /** 生成唯一 ID */
  function generateId(): string {
    return `msg_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
  }

  return {
    // state
    messages,
    isStreaming,
    currentStreamingMessage,
    inputText,
    conversationId,
    quickScenes,
    // computed
    lastMessage,
    messageCount,
    // actions
    addMessage,
    addUserMessage,
    startStreaming,
    appendStreamChunk,
    finalizeStream,
    setInputText,
    clearHistory,
  }
})
