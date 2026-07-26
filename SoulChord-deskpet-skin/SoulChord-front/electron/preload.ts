/**
 * Electron 预加载脚本
 * 通过 contextBridge 安全地暴露 IPC API 给渲染进程
 */
import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('electronAPI', {
  // ===== 窗口控制 =====
  minimizeWindow: () => ipcRenderer.invoke('window:minimize'),
  maximizeWindow: () => ipcRenderer.invoke('window:maximize'),
  closeWindow: () => ipcRenderer.invoke('window:close'),
  toggleMiniMode: () => ipcRenderer.invoke('window:toggleMini'),
  setAlwaysOnTop: (flag: boolean) => ipcRenderer.invoke('window:alwaysOnTop', flag),

  // ===== 设置 =====
  getSettings: () => ipcRenderer.invoke('settings:get'),
  setSettings: (settings: Record<string, unknown>) =>
    ipcRenderer.invoke('settings:set', settings),

  // ===== 媒体 =====
  setMediaMetadata: (metadata: Record<string, unknown>) =>
    ipcRenderer.invoke('media:setMetadata', metadata),

  // ===== 系统 =====
  openExternal: (url: string) => ipcRenderer.invoke('shell:openExternal', url),

  // ===== 事件监听 =====
  onTrayAction: (callback: (action: string) => void) => {
    ipcRenderer.on('tray:action', (_event, action) => callback(action))
  },
  onWindowBlur: (callback: () => void) => {
    window.addEventListener('blur', callback)
  },
  onWindowFocus: (callback: () => void) => {
    window.addEventListener('focus', callback)
  },

  // ===== 桌宠专用 =====
  movePetWindow: (x: number, y: number) => ipcRenderer.send('pet:move', x, y),
  showMainWindow: () => ipcRenderer.send('pet:showMain'),
  hideMainWindow: () => ipcRenderer.send('pet:hideMain'),

  // ===== 后端状态（Loading 窗口）=====
  getBackendStatuses: () => ipcRenderer.invoke('backend:getStatuses'),
  onBackendStatus: (callback: (statuses: unknown[]) => void) => {
    const handler = (_event: Electron.IpcRendererEvent, statuses: unknown[]) => callback(statuses)
    ipcRenderer.on('backend:status', handler)
    return () => ipcRenderer.removeListener('backend:status', handler)
  },
  onBackendUpdate: (callback: (update: { name: string; status: string }) => void) => {
    const handler = (_event: Electron.IpcRendererEvent, update: { name: string; status: string }) => callback(update)
    ipcRenderer.on('backend:update', handler)
    return () => ipcRenderer.removeListener('backend:update', handler)
  },
})
