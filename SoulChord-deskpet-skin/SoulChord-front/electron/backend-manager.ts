/**
 * SoulChord Backend Manager
 * 负责 Electron 生命周期内启动/监控/关闭全部后端进程
 */
import { app } from 'electron'
import { spawn, ChildProcess, execSync } from 'child_process'
import { join, dirname } from 'path'
import { existsSync } from 'fs'
import http from 'http'
import net from 'net'

// ── Types ──
export interface BackendConfig {
  name: string
  port: number
  healthUrl: string
  healthCheckIncludes?: (body: string) => boolean
  /** Returns [exe, ...args] */
  getCmd: () => [string, string[]]
  cwd?: string
  env?: NodeJS.ProcessEnv
  startupDelayMs?: number
}

export interface BackendStatus {
  name: string; port: number
  pid: number | null; running: boolean; healthy: boolean
  startTime: number | null
}

type StatusCallback = (all: BackendStatus[]) => void

// ── Helpers ──
const isDev = !!process.env.VITE_DEV_SERVER_URL

/** Project root (parent of agent/, api/, SoulChord-*-skin/) */
function projectRoot(): string {
  // __dirname = SoulChord-deskpet-skin/SoulChord-front/dist-electron/
  if (isDev) return join(__dirname, '..', '..', '..')
  return dirname(process.resourcesPath)  // resources/ 的上一级 = app root
}

/** Where backend exes live (production only) */
function backendsDir(): string {
  return join(process.resourcesPath, 'backend')
}

function devPythonCmd(): [string, string[]] {
  // try python then python3
  try { execSync('python --version', { stdio: 'ignore' }); return ['python', []] }
  catch { return ['python3', []] }
}

// ── Backend definitions ──
function createBackends(): BackendConfig[] {
  const root = projectRoot()
  const bDir = backendsDir()
  const [py, _pyArgs] = devPythonCmd()

  return [
    // 1. NeteaseCloudMusicApi :3000
    {
      name: 'NeteaseCloudMusicApi',
      port: 3000,
      healthUrl: 'http://localhost:3000/',
      getCmd: () => {
        if (isDev) return ['npx', ['NeteaseCloudMusicApi']]
        const pkgExe = join(bDir, 'netease', 'netease_api.exe')
        if (existsSync(pkgExe)) return [pkgExe, []]
        return [join(bDir, 'node', 'node.exe'), [join(bDir, 'netease', 'launcher.js')]]
      },
      cwd: isDev ? undefined : join(bDir, 'netease'),
      env: { PORT: '3000' },
      startupDelayMs: 3000,
    },
    // 2. MusicAgentAPI :8081
    {
      name: 'MusicAgentAPI',
      port: 8081,
      healthUrl: 'http://localhost:8081/api/v1/health',
      getCmd: () => {
        if (isDev) return [py, ['-m', 'uvicorn', 'api.music_agent_api.main:app', '--port', '8081', '--host', '127.0.0.1']]
        return [join(bDir, 'music_api', 'music_api.exe'), []]
      },
      cwd: isDev ? root : undefined,
    },
    // 3. QQMusicApi :8082
    {
      name: 'QQMusicApi',
      port: 8082,
      healthUrl: 'http://localhost:8082/',
      healthCheckIncludes: (body) => body.includes('"code":0'),
      getCmd: () => {
        if (isDev) return [py, ['-m', 'uvicorn', 'web.src.app:create_app', '--factory', '--port', '8082', '--host', '127.0.0.1']]
        return [join(bDir, 'qqmusic_api', 'qqmusic_api.exe'), []]
      },
      cwd: isDev ? join(root, 'api', 'QQMusicApi-main') : undefined,
    },
    // 4. AgentRuntime :8000
    {
      name: 'AgentRuntime',
      port: 8000,
      healthUrl: 'http://localhost:8000/api/health',
      getCmd: () => {
        if (isDev) return [py, ['-m', 'agent', '--port', '8000']]
        return [join(bDir, 'agent', 'agent.exe'), ['--port', '8000']]
      },
      cwd: isDev ? root : undefined,
    },
  ]
}

// ── BackendManager ──
export class BackendManager {
  private processes = new Map<string, ChildProcess>()
  private statuses = new Map<string, BackendStatus>()
  private healthTimers = new Map<string, NodeJS.Timeout>()
  private _callback: StatusCallback | null = null
  private _aborted = false

  constructor() {
    for (const b of createBackends()) {
      this.statuses.set(b.name, { name: b.name, port: b.port, pid: null, running: false, healthy: false, startTime: null })
    }
  }

  onStatus(cb: StatusCallback) { this._callback = cb }
  private emit() { this._callback?.(Array.from(this.statuses.values())) }

  private set(name: string, p: Partial<BackendStatus>) {
    const s = this.statuses.get(name)
    if (s) { Object.assign(s, p); this.emit() }
  }

  // ── Health check ──
  private async checkHealth(url: string, validate?: (body: string) => boolean, timeout = 5000): Promise<boolean> {
    return new Promise(resolve => {
      const req = http.get(url, { timeout }, res => {
        let data = ''
        res.on('data', c => data += c)
        res.on('end', () => {
          const ok = res.statusCode! >= 200 && res.statusCode! < 500
          resolve(ok && (!validate || validate(data)))
        })
      })
      req.on('error', () => resolve(false))
      req.on('timeout', () => { req.destroy(); resolve(false) })
    })
  }

  private async isPortFree(port: number): Promise<boolean> {
    return new Promise(resolve => {
      const s = net.createServer()
      s.once('error', () => resolve(false))
      s.once('listening', () => { s.close(); resolve(true) })
      s.listen(port, '127.0.0.1')
    })
  }

  // ── Start one backend ──
  async startOne(config: BackendConfig): Promise<boolean> {
    const free = await this.isPortFree(config.port)
    if (!free) {
      console.log(`[BackendManager] Port ${config.port} already in use — assuming ${config.name} is running`)
      this.set(config.name, { running: true, healthy: true, startTime: Date.now() })
      return true
    }

    return new Promise(resolve => {
      const [exe, args] = config.getCmd()
      console.log(`[BackendManager] Starting ${config.name}: ${exe} ${args.join(' ')}`)

      try {
        const proc = spawn(exe, args, {
          cwd: config.cwd,
          env: { ...process.env, ...config.env, PORT: String(config.port) },
          stdio: ['ignore', 'pipe', 'pipe'],
          windowsHide: false,
        })

        this.processes.set(config.name, proc)
        this.set(config.name, { pid: proc.pid!, running: true, startTime: Date.now() })

        proc.stdout?.on('data', (d: Buffer) => console.log(`[${config.name}] ${d.toString().trimEnd()}`))
        proc.stderr?.on('data', (d: Buffer) => console.error(`[${config.name}] ${d.toString().trimEnd()}`))

        proc.on('exit', (code, signal) => {
          console.log(`[BackendManager] ${config.name} exited (code=${code} signal=${signal})`)
          this.set(config.name, { running: false, healthy: false, pid: null })
          this.processes.delete(config.name)
          this.stopHealthPing(config.name)
        })
        proc.on('error', err => {
          console.error(`[BackendManager] ${config.name} spawn error:`, err.message)
          this.set(config.name, { running: false, healthy: false })
          this.processes.delete(config.name)
          resolve(false)
        })

        // 等 startupDelay 后开始健康检查
        setTimeout(() => this.startHealthPing(config), config.startupDelayMs ?? 0)
        setTimeout(() => resolve(true), 1000)
      } catch (err) {
        console.error(`[BackendManager] ${config.name} exception:`, err)
        resolve(false)
      }
    })
  }

  private startHealthPing(config: BackendConfig) {
    this.stopHealthPing(config.name)
    const interval = setInterval(async () => {
      if (this._aborted) return
      const healthy = await this.checkHealth(config.healthUrl, config.healthCheckIncludes)
      this.set(config.name, { healthy })
    }, 2000)
    this.healthTimers.set(config.name, interval)
  }

  private stopHealthPing(name: string) {
    const t = this.healthTimers.get(name)
    if (t) { clearInterval(t); this.healthTimers.delete(name) }
  }

  // ── Wait for health ──
  private async waitHealthy(config: BackendConfig, timeoutMs: number): Promise<boolean> {
    const deadline = Date.now() + timeoutMs
    while (Date.now() < deadline) {
      if (this._aborted) return false
      const ok = await this.checkHealth(config.healthUrl, config.healthCheckIncludes)
      if (ok) { this.set(config.name, { healthy: true }); return true }
      await new Promise(r => setTimeout(r, 1000))
    }
    return false
  }

  // ── Start all ──
  async startAll(onProgress?: (name: string, status: string) => void): Promise<boolean> {
    this._aborted = false
    const backends = createBackends()

    // 1. Netease 最先
    const netease = backends.find(b => b.name === 'NeteaseCloudMusicApi')!
    onProgress?.('NeteaseCloudMusicApi', 'starting')
    await this.startOne(netease)
    const neteaseOk = await this.waitHealthy(netease, 30000)
    onProgress?.('NeteaseCloudMusicApi', neteaseOk ? 'healthy' : 'skipped')
    if (!neteaseOk) console.warn('[BackendManager] Netease unavailable — music_agent_api will handle')

    // 2. MusicAgentAPI + QQMusicApi 并行
    const pair = backends.filter(b => b.name !== 'NeteaseCloudMusicApi' && b.name !== 'AgentRuntime')
    await Promise.all(pair.map(async b => {
      onProgress?.(b.name, 'starting')
      await this.startOne(b)
      const ok = await this.waitHealthy(b, 20000)
      onProgress?.(b.name, ok ? 'healthy' : 'failed')
    }))

    // 3. AgentRuntime 最后
    const agent = backends.find(b => b.name === 'AgentRuntime')!
    onProgress?.('AgentRuntime', 'starting')
    await this.startOne(agent)
    const agentOk = await this.waitHealthy(agent, 60000)
    onProgress?.('AgentRuntime', agentOk ? 'healthy' : 'failed')

    return [neteaseOk, ...pair.map(_ => true), agentOk].every(Boolean)
  }

  // ── Stop all ──
  async stopAll(): Promise<void> {
    this._aborted = true
    for (const [name] of this.healthTimers) this.stopHealthPing(name)

    const backends = createBackends()
    for (const b of backends.reverse()) {
      const proc = this.processes.get(b.name)
      if (!proc || !proc.pid) continue
      console.log(`[BackendManager] Stopping ${b.name} (pid=${proc.pid})`)
      try { execSync(`taskkill /pid ${proc.pid} /T /F`, { stdio: 'ignore' }) }
      catch { proc.kill('SIGTERM') }
    }
    this.processes.clear()
    for (const [name] of this.statuses) this.set(name, { running: false, healthy: false, pid: null })
  }

  getStatuses() { return Array.from(this.statuses.values()) }
  isAllHealthy() { return Array.from(this.statuses.values()).every(s => s.healthy) }
}
