/**
 * Electron 预加载脚本
 * 通过 contextBridge 安全地暴露 IPC API 给渲染进程
 */
import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('electronAPI', {
  // ===== 窗口控制（原有）=====
  minimizeWindow: () => ipcRenderer.invoke('window:minimize'),
  maximizeWindow: () => ipcRenderer.invoke('window:maximize'),
  closeWindow: () => ipcRenderer.invoke('window:close'),
  toggleMiniMode: () => ipcRenderer.invoke('window:toggleMini'),
  setAlwaysOnTop: (flag: boolean) => ipcRenderer.invoke('window:alwaysOnTop', flag),

  // ===== 设置（原有）=====
  getSettings: () => ipcRenderer.invoke('settings:get'),
  setSettings: (settings: Record<string, unknown>) =>
    ipcRenderer.invoke('settings:set', settings),

  // ===== 媒体（原有）=====
  setMediaMetadata: (metadata: Record<string, unknown>) =>
    ipcRenderer.invoke('media:setMetadata', metadata),

  // ===== 系统（原有）=====
  openExternal: (url: string) => ipcRenderer.invoke('shell:openExternal', url),

  // ===== 事件监听（原有）=====
  onTrayAction: (callback: (action: string) => void) => {
    ipcRenderer.on('tray:action', (_event, action) => callback(action))
  },
  onWindowBlur: (callback: () => void) => {
    window.addEventListener('blur', callback)
  },
  onWindowFocus: (callback: () => void) => {
    window.addEventListener('focus', callback)
  },

  // ===== 桌宠专用（新增）=====
  movePetWindow: (x: number, y: number) => ipcRenderer.send('pet:move', x, y),
  showMainWindow: () => ipcRenderer.send('pet:showMain'),
  hideMainWindow: () => ipcRenderer.send('pet:hideMain'),
})