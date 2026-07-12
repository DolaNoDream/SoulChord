/**
 * SoulChord Electron 主进程
 * 负责窗口管理、系统托盘、IPC 通信，并集成桌宠窗口
 */
import { app, BrowserWindow, Tray, Menu, ipcMain, nativeImage, screen, shell } from 'electron'
import { join } from 'path'

// ========== 常量 ==========
const MINI_WIDTH = 320
const MINI_HEIGHT = 100
const FULL_WIDTH = 440
const FULL_HEIGHT = 720

// ========== 全局状态 ==========
let mainWindow: BrowserWindow | null = null
let petWindow: BrowserWindow | null = null
let tray: Tray | null = null
let isMiniMode = false
let isAlwaysOnTop = true
let isQuitting = false
let isMaximized = false
let normalBounds: { x: number; y: number; width: number; height: number } | null = null

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
    show: false,   // 默认不显示
  })

  if (process.env.VITE_DEV_SERVER_URL) {
    mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL)
  } else {
    mainWindow.loadFile(join(__dirname, '../dist/index.html'))
  }

  mainWindow.on('maximize', () => { isMaximized = true })
  mainWindow.on('unmaximize', () => { isMaximized = false })

  mainWindow.once('ready-to-show', () => {
    // 不自动 show，由桌宠控制显示
  })

  mainWindow.on('closed', () => {
    mainWindow = null
  })
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

  if (process.env.VITE_DEV_SERVER_URL) {
    petWindow.loadURL(process.env.VITE_DEV_SERVER_URL + '/pet.html')
  } else {
    petWindow.loadFile(join(__dirname, '../dist/pet.html'))
  }

  petWindow.once('ready-to-show', () => {
    petWindow?.show()
  })

  petWindow.on('closed', () => {
    petWindow = null
  })
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
            if (mainWindow.isVisible()) {
              mainWindow.hide()
            } else {
              mainWindow.show()
              mainWindow.focus()
            }
          }
        },
      },
      { type: 'separator' },
      {
        label: '退出 SoulChord',
        click: () => {
          isQuitting = true
          app.quit()
        },
      },
    ])
  )

  tray.on('double-click', () => {
    if (mainWindow) {
      mainWindow.show()
      mainWindow.focus()
    }
  })
}

// ========== IPC 处理器 ==========
function setupIPC() {
  // 窗口控制
  ipcMain.handle('window:minimize', () => { mainWindow?.minimize() })
  ipcMain.handle('window:maximize', () => {
    if (!mainWindow) return false
    if (isMaximized) {
      if (normalBounds) mainWindow.setBounds(normalBounds)
      isMaximized = false
      return false
    } else {
      normalBounds = mainWindow.getBounds()
      const { x, y, width, height } = screen.getPrimaryDisplay().workArea
      mainWindow.setBounds({ x, y, width, height })
      isMaximized = true
      return true
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
    isAlwaysOnTop = flag
    mainWindow?.setAlwaysOnTop(flag)
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

  // ---------- 桌宠专用 IPC ----------
  // 移动桌宠窗口
  ipcMain.on('pet:move', (_event, x: number, y: number) => {
    if (petWindow) petWindow.setPosition(x, y)
  })

  // 显示主窗口
  ipcMain.on('pet:showMain', () => {
    if (mainWindow) {
      if (!mainWindow.isVisible()) mainWindow.show()
      mainWindow.focus()
    }
  })

  // 隐藏主窗口
  ipcMain.on('pet:hideMain', () => {
    if (mainWindow) mainWindow.hide()
  })
}

// ========== 应用生命周期 ==========
app.whenReady().then(() => {
  setupIPC()
  createWindow()      // 主窗口（默认隐藏）
  createPetWindow()   // 桌宠窗口（立即显示）
  createTray()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
      createPetWindow()
    } else {
      mainWindow?.show()
    }
  })
})

app.on('window-all-closed', () => {
  // macOS 不退出
})

app.on('before-quit', () => {
  isQuitting = true
})