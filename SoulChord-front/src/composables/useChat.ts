import { ref } from 'vue'
import { useChatStore } from '@/stores/chat'

/** 对话交互逻辑（v0.3 — WS 模式下由 useWebSocket 处理发送，此文件处理本地 UI 状态） */
export function useChat() {
  const chatStore = useChatStore()
  const isSending = ref(false)
  const error = ref<string | null>(null)

  /** 用户发送消息：添加到本地 store，实际 WS 发送由 useWebSocket 处理 */
  function sendMessage(text?: string): string {
    const messageText = text ?? chatStore.inputText.trim()
    if (!messageText) return ''
    chatStore.addUserMessage(messageText)
    chatStore.setInputText('')
    isSending.value = true
    error.value = null
    return messageText
  }

  /** 标记发送完成 */
  function done() { isSending.value = false }
  function setError(msg: string) { error.value = msg; isSending.value = false }

  return { isSending, error, sendMessage, done, setError }
}
