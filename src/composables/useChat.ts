/**
 * 对话交互逻辑
 * 封装消息发送、流式接收、场景触发等功能
 */
import { ref } from 'vue'
import { useChatStore } from '@/stores/chat'
import { sendStreamMessage, triggerScene } from '@/api/agent'

export function useChat() {
  const chatStore = useChatStore()
  const isSending = ref(false)
  const error = ref<string | null>(null)

  /** 发送用户消息 */
  async function sendMessage(text?: string): Promise<void> {
    const messageText = text ?? chatStore.inputText.trim()
    if (!messageText || isSending.value) return

    // 添加用户消息
    chatStore.addUserMessage(messageText)
    chatStore.setInputText('')
    isSending.value = true
    error.value = null

    // 开始流式接收
    chatStore.startStreaming()

    try {
      await sendStreamMessage(
        messageText,
        chatStore.conversationId,
        // onChunk
        (chunk) => {
          chatStore.appendStreamChunk(chunk)
        },
        // onDone
        (fullMessage) => {
          chatStore.finalizeStream()
          chatStore.conversationId = fullMessage.id
        },
        // onError
        (err) => {
          error.value = err.message
          chatStore.finalizeStream()
          // 添加错误提示消息
          chatStore.addMessage({
            id: `err_${Date.now()}`,
            role: 'assistant',
            content: '抱歉，我现在连接不上服务器。请确认后端服务已启动，或者稍后再试。',
            timestamp: new Date().toISOString(),
          })
        }
      )
    } finally {
      isSending.value = false
    }
  }

  /** 触发快捷场景 */
  async function sendScene(sceneId: string): Promise<void> {
    const scene = chatStore.quickScenes.find(s => s.id === sceneId)
    if (!scene || isSending.value) return

    chatStore.addUserMessage(scene.promptTemplate)
    isSending.value = true
    error.value = null
    chatStore.startStreaming()

    try {
      await sendStreamMessage(
        scene.promptTemplate,
        chatStore.conversationId,
        (chunk) => { chatStore.appendStreamChunk(chunk) },
        () => { chatStore.finalizeStream() },
        (err) => {
          error.value = err.message
          chatStore.finalizeStream()
        }
      )
    } finally {
      isSending.value = false
    }
  }

  return {
    isSending,
    error,
    sendMessage,
    sendScene,
  }
}
