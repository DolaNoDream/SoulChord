/**
 * Electron 预加载脚本
 * 通过 contextBridge 安全地暴露 IPC API 给渲染进程
 */
import { contextBridge, ipcRenderer } from 'electron'

// 暴露到渲染进程的 API
contextBridge.exposeInMainWorld('electronAPI', {
  // ===== 窗口控制 =====
  minimizeWindow: () => ipcRenderer.invoke('window:minimize'),
  maximizeWindow: () => ipcRenderer.invoke('window:maximize'),
  closeWindow: () => ipcRenderer.invoke('window:close'),
  toggleMiniMode: () => ipcRenderer.invoke('window:toggleMini'),
  setAlwaysOnTop: (flag: boolean) => ipcRenderer.invoke('window:alwaysOnTop', flag),

  // ===== 设置持久化 =====
  getSettings: () => ipcRenderer.invoke('settings:get'),
  setSettings: (settings: Record<string, unknown>) =>
    ipcRenderer.invoke('settings:set', settings),

  // ===== 媒体元数据 =====
  setMediaMetadata: (metadata: Record<string, unknown>) =>
    ipcRenderer.invoke('media:setMetadata', metadata),

  // ===== 事件监听（主进程 → 渲染进程）=====
  onTrayAction: (callback: (action: string) => void) => {
    ipcRenderer.on('tray:action', (_event, action) => callback(action))
  },

  onWindowBlur: (callback: () => void) => {
    window.addEventListener('blur', callback)
  },

  onWindowFocus: (callback: () => void) => {
    window.addEventListener('focus', callback)
  },
})
