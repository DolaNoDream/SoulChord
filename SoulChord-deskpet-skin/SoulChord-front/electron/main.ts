/**
 * SoulChord Electron 主进程
 * 负责窗口管理、系统托盘、IPC 通信、后端进程生命周期
 */
import { app, BrowserWindow, Tray, Menu, ipcMain, nativeImage, screen, shell, dialog } from 'electron'
import { join } from 'path'
import { BackendManager } from './backend-manager'

// ========== 常量 ==========
const MINI_WIDTH = 320
const MINI_HEIGHT = 100
const FULL_WIDTH = 440
const FULL_HEIGHT = 720

// ========== 全局状态 ==========
let mainWindow: BrowserWindow | null = null
let petWindow: BrowserWindow | null = null
let loadingWindow: BrowserWindow | null = null
let tray: Tray | null = null
let isMiniMode = false
let isAlwaysOnTop = true
let isQuitting = false
let isMaximized = false
let normalBounds: { x: number; y: number; width: number; height: number } | null = null
let backendManager: BackendManager | null = null

const isDev = !!process.env.VITE_DEV_SERVER_URL

// ========== Loading 窗口 ==========
function createLoadingWindow(): BrowserWindow {
  loadingWindow = new BrowserWindow({
    width: 400,
    height: 260,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    resizable: false,
    skipTaskbar: true,
    backgroundColor: '#00000000',
    webPreferences: {
      preload: join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
    show: false,
  })

  if (isDev) {
    loadingWindow.loadURL(process.env.VITE_DEV_SERVER_URL! + '/loading.html')
  } else {
    loadingWindow.loadFile(join(__dirname, '../dist/loading.html'))
  }

  loadingWindow.once('ready-to-show', () => {
    loadingWindow?.show()
  })

  loadingWindow.on('closed', () => { loadingWindow = null })
  return loadingWindow
}

// ========== 主窗口创建 ==========
function createWindow() {
  mainWindow = new BrowserWindow({
    width: FULL_WIDTH,
    height: FULL_HEIGHT,
    minWidth: 280,
    minHeight: 80,
    frame: false,
    transparent: true,
    alwaysOnTop: isAlwaysOnTop,
    skipTaskbar: false,
    resizable: true,
    backgroundColor: '#00000000',
    webPreferences: {
      preload: join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
      webSecurity: true,
      autoplayPolicy: 'no-user-gesture-required',
    },
    show: false,
  })

  if (isDev) {
    mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL!)
  } else {
    mainWindow.loadFile(join(__dirname, '../dist/index.html'))
  }

  mainWindow.on('maximize', () => { isMaximized = true })
  mainWindow.on('unmaximize', () => { isMaximized = false })

  mainWindow.on('closed', () => { mainWindow = null })
}

// ========== 桌宠窗口创建 ==========
function createPetWindow() {
  petWindow = new BrowserWindow({
    width: 200,
    height: 200,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    hasShadow: false,
    resizable: false,
    skipTaskbar: true,
    backgroundColor: '#00000000',
    webPreferences: {
      preload: join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
    show: false,
  })

  if (isDev) {
    petWindow.loadURL(process.env.VITE_DEV_SERVER_URL! + '/pet.html')
  } else {
    petWindow.loadFile(join(__dirname, '../dist/pet.html'))
  }

  petWindow.once('ready-to-show', () => { petWindow?.show() })
  petWindow.on('closed', () => { petWindow = null })
}

// ========== 系统托盘 ==========
function createTray() {
  const trayIcon = nativeImage.createEmpty()
  tray = new Tray(trayIcon)
  tray.setToolTip('SoulChord - AI音乐电台')

  tray.setContextMenu(
    Menu.buildFromTemplate([
      {
        label: '显示/隐藏窗口',
        click: () => {
          if (mainWindow) {
            if (mainWindow.isVisible()) mainWindow.hide()
            else { mainWindow.show(); mainWindow.focus() }
          }
        },
      },
      { type: 'separator' },
      {
        label: '退出 SoulChord',
        click: () => { isQuitting = true; app.quit() },
      },
    ])
  )

  tray.on('double-click', () => {
    if (mainWindow) { mainWindow.show(); mainWindow.focus() }
  })
}

// ========== 启动所有窗口 ==========
function showAppWindows() {
  createWindow()
  createPetWindow()
  createTray()
}

// ========== IPC 处理器 ==========
function setupIPC() {
  // 窗口控制
  ipcMain.handle('window:minimize', () => { mainWindow?.minimize() })
  ipcMain.handle('window:maximize', () => {
    if (!mainWindow) return false
    if (isMaximized) {
      if (normalBounds) mainWindow.setBounds(normalBounds)
      isMaximized = false; return false
    } else {
      normalBounds = mainWindow.getBounds()
      const { x, y, width, height } = screen.getPrimaryDisplay().workArea
      mainWindow.setBounds({ x, y, width, height })
      isMaximized = true; return true
    }
  })
  ipcMain.handle('window:close', () => { mainWindow?.hide() })
  ipcMain.handle('window:toggleMini', () => {
    if (!mainWindow) return
    isMiniMode = !isMiniMode
    if (isMiniMode) {
      mainWindow.setMinimumSize(MINI_WIDTH, MINI_HEIGHT)
      mainWindow.setSize(MINI_WIDTH, MINI_HEIGHT, true)
      mainWindow.setResizable(false)
      mainWindow.setSkipTaskbar(true)
    } else {
      mainWindow.setMinimumSize(280, 80)
      mainWindow.setSize(FULL_WIDTH, FULL_HEIGHT, true)
      mainWindow.setResizable(true)
      mainWindow.setSkipTaskbar(false)
      mainWindow.center()
    }
  })
  ipcMain.handle('window:alwaysOnTop', (_event, flag: boolean) => {
    isAlwaysOnTop = flag; mainWindow?.setAlwaysOnTop(flag)
  })

  // 设置
  ipcMain.handle('settings:get', () => ({}))
  ipcMain.handle('settings:set', (_event, settings: Record<string, unknown>) => {
    console.log('Settings saved:', settings)
  })

  // 媒体控制
  ipcMain.handle('media:setMetadata', (_event, metadata: Record<string, unknown>) => {
    console.log('Media metadata:', metadata)
  })

  // 外部链接
  ipcMain.handle('shell:openExternal', (_event, url: string) => shell.openExternal(url))

  // 桌宠专用
  ipcMain.on('pet:move', (_event, x: number, y: number) => { if (petWindow) petWindow.setPosition(x, y) })
  ipcMain.on('pet:showMain', () => {
    if (mainWindow) { if (!mainWindow.isVisible()) mainWindow.show(); mainWindow.focus() }
  })
  ipcMain.on('pet:hideMain', () => { if (mainWindow) mainWindow.hide() })

  // Loading 窗口 — 后端状态查询
  ipcMain.handle('backend:getStatuses', () => backendManager?.getStatuses() ?? [])
}

// ========== 应用生命周期 ==========
app.whenReady().then(async () => {
  setupIPC()

  if (isDev) {
    // Dev 模式：用户自行管理后端，直接显示窗口
    showAppWindows()
  } else {
    // 生产模式：BackendManager 自动启动后端
    const loading = createLoadingWindow()

    backendManager = new BackendManager()
    backendManager.onStatus((statuses) => {
      loading.webContents.send('backend:status', statuses)
    })

    const allHealthy = await backendManager.startAll((name, status) => {
      loading.webContents.send('backend:update', { name, status })
    })

    if (!allHealthy) {
      const unhealthy = backendManager.getStatuses().filter(s => !s.healthy)
      dialog.showMessageBox({
        type: 'warning',
        title: 'SoulChord — 部分后端启动失败',
        message: `以下服务未正常启动:\n${unhealthy.map(s => `  • ${s.name} (port ${s.port})`).join('\n')}`,
        detail: '部分功能可能不可用。是否继续？',
        buttons: ['继续', '退出'],
        defaultId: 0,
        cancelId: 1,
      }).then(({ response }) => {
        if (response === 1) { app.quit(); return }
        loading.close()
        showAppWindows()
      })
    } else {
      loading.close()
      showAppWindows()
    }
  }

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      if (isDev) showAppWindows()
    } else {
      mainWindow?.show()
    }
  })
})

app.on('window-all-closed', () => {
  // macOS 不退出
})

app.on('before-quit', async () => {
  isQuitting = true
  if (backendManager) {
    await backendManager.stopAll()
  }
})
