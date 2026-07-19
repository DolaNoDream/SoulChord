import { ref, computed } from 'vue'
import { useChatStore } from '@/stores/chat'

/** 对话交互逻辑（v0.3 — WS 模式下由 useWebSocket 处理发送，此文件处理本地 UI 状态） */
export function useChat() {
  const chatStore = useChatStore()
  const error = ref<string | null>(null)

  /** 用户发送消息：添加到本地 store，实际 WS 发送由 useWebSocket 处理 */
  function sendMessage(text?: string): string {
    const messageText = text ?? chatStore.inputText.trim()
    if (!messageText) return ''
    chatStore.addUserMessage(messageText)
    chatStore.setInputText('')
    chatStore.isSending = true
    error.value = null
    return messageText
  }

  /** 标记发送完成 */
  function done() { chatStore.isSending = false }
  function setError(msg: string) { error.value = msg; chatStore.isSending = false }

  return { isSending: computed(() => chatStore.isSending), error, sendMessage, done, setError }
}
