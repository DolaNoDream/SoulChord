/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<object, object, unknown>
  export default component
}

interface Window {
  electronAPI?: {
    minimizeWindow: () => Promise<void>
    maximizeWindow: () => Promise<void>
    closeWindow: () => Promise<void>
    toggleMiniMode: () => Promise<void>
    setAlwaysOnTop: (flag: boolean) => Promise<void>
    openExternal: (url: string) => Promise<void>
    getSettings: () => Promise<Record<string, unknown>>
    setSettings: (settings: Record<string, unknown>) => Promise<void>
    setMediaMetadata: (metadata: {
      title?: string
      artist?: string
      album?: string
      artwork?: Array<{ src: string; sizes: string; type: string }>
    }) => Promise<void>
    onTrayAction: (callback: (action: string) => void) => void
    onWindowBlur: (callback: () => void) => void
    onWindowFocus: (callback: () => void) => void
  }
}
