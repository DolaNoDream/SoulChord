/**
 * SoulChord Electron 主进程
 * 负责窗口管理、系统托盘和 IPC 通信
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
let tray: Tray | null = null
let isMiniMode = false
let isAlwaysOnTop = true
let isQuitting = false
let isMaximized = false
// 保存最大化前的位置和大小
let normalBounds: { x: number; y: number; width: number; height: number } | null = null

// ========== 窗口创建 ==========

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

  // 开发环境加载 Vite 开发服务器，生产环境加载打包后的文件
  if (process.env.VITE_DEV_SERVER_URL) {
    mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL)
  } else {
    mainWindow.loadFile(join(__dirname, '../dist/index.html'))
  }

  // 窗口准备好后再显示，避免白屏闪烁
  // 同步最大化状态（用户双击标题栏等操作）
  mainWindow.on('maximize', () => { isMaximized = true })
  mainWindow.on('unmaximize', () => { isMaximized = false })

  mainWindow.once('ready-to-show', () => {
    mainWindow?.show()
  })

  mainWindow.on('closed', () => {
    mainWindow = null
  })
}

// ========== 系统托盘 ==========

function createTray() {
  // 创建一个简单的 16x16 托盘图标
  const trayIcon = nativeImage.createEmpty()
  tray = new Tray(trayIcon)

  // 使用 emoji 作为托盘图标标题（Windows 兼容方案）
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

  // 双击托盘图标显示窗口
  tray.on('double-click', () => {
    if (mainWindow) {
      mainWindow.show()
      mainWindow.focus()
    }
  })
}

// ========== IPC 处理器 ==========

function setupIPC() {
  // 最小化窗口
  ipcMain.handle('window:minimize', () => {
    mainWindow?.minimize()
  })

  // 最大化/还原窗口（手动计算尺寸，绕过 frameless 窗口的限制）
  ipcMain.handle('window:maximize', () => {
    if (!mainWindow) return false

    if (isMaximized) {
      // 还原：回到之前保存的位置和大小
      if (normalBounds) {
        mainWindow.setBounds(normalBounds)
      }
      isMaximized = false
      return false
    } else {
      // 最大化：保存当前位置，铺满屏幕工作区
      normalBounds = mainWindow.getBounds()
      const { x, y, width, height } = screen.getPrimaryDisplay().workArea
      mainWindow.setBounds({ x, y, width, height })
      isMaximized = true
      return true
    }
  })

  // 关闭窗口（隐藏到托盘）
  ipcMain.handle('window:close', () => {
    mainWindow?.hide()
  })

  // 切换迷你模式
  ipcMain.handle('window:toggleMini', () => {
    if (!mainWindow) return

    isMiniMode = !isMiniMode

    if (isMiniMode) {
      // 切换到迷你模式
      mainWindow.setMinimumSize(MINI_WIDTH, MINI_HEIGHT)
      mainWindow.setSize(MINI_WIDTH, MINI_HEIGHT, true)
      mainWindow.setResizable(false)
      mainWindow.setSkipTaskbar(true)
    } else {
      // 恢复完整模式
      mainWindow.setMinimumSize(280, 80)
      mainWindow.setSize(FULL_WIDTH, FULL_HEIGHT, true)
      mainWindow.setResizable(true)
      mainWindow.setSkipTaskbar(false)
      mainWindow.center()
    }
  })

  // 始终置顶
  ipcMain.handle('window:alwaysOnTop', (_event, flag: boolean) => {
    isAlwaysOnTop = flag
    mainWindow?.setAlwaysOnTop(flag)
  })

  // 获取设置
  ipcMain.handle('settings:get', () => {
    // 简单实现：从文件读取（可后续增强）
    return {}
  })

  // 保存设置
  ipcMain.handle('settings:set', (_event, settings: Record<string, unknown>) => {
    // 简单实现：写入文件（可后续增强）
    console.log('Settings saved:', settings)
  })

  // 设置媒体元数据（OS 媒体控件）
  ipcMain.handle('media:setMetadata', (_event, metadata: Record<string, unknown>) => {
    // 可用于 Windows 系统媒体控制
    console.log('Media metadata:', metadata)
  })

  // 用系统默认浏览器打开链接
  ipcMain.handle('shell:openExternal', (_event, url: string) => {
    return shell.openExternal(url)
  })
}

// ========== 应用生命周期 ==========

app.whenReady().then(() => {
  setupIPC()
  createWindow()
  createTray()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    } else {
      mainWindow?.show()
    }
  })
})

// 防止窗口关闭时退出应用（隐藏到托盘）
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    // macOS 上不退出
  }
})

app.on('before-quit', () => {
  isQuitting = true
})
