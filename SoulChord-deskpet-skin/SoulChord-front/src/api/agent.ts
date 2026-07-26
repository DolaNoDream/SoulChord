/**
 * AI Agent 通信层（v1.1 — 对齐 frontend-agent-api.md）
 * 通道：WebSocket（主）+ HTTP（补充）
 */
import axios, { type AxiosInstance } from 'axios'
import type { Song, Playlist } from '@/types/music'
import type { UserProfits, RecentMood, AgentInfo } from '@/types/user'

/** Agent 基础地址 */
const AGENT_BASE_URL = 'http://localhost:8000'
const WS_URL = 'ws://localhost:8000/ws/client'

/** 通用错误码（对齐文档 0.3） */
export const ERROR_CODES: Record<number, string> = {
  0: '成功',
  1001: '参数错误',
  1002: 'APIKey未配置 / 网易云账号未登录',
  1003: '歌单/歌曲资源不存在',
  2001: 'LLM大模型调用失败',
  2002: '工具调用失败',
  2003: '请求超时',
  3001: '网易云音乐服务不可用',
  3002: '网易云接口请求异常',
  9999: '服务内部异常',
}

// ===== Axios 实例 =====
const http: AxiosInstance = axios.create({
  baseURL: `${AGENT_BASE_URL}/api`,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

// 响应拦截器：检查 {code, msg, data} 格式
http.interceptors.response.use(
  (res) => {
    const body = res.data
    if (body && typeof body === 'object' && 'code' in body) {
      if (body.code !== 0) {
        const errMsg = body.msg || ERROR_CODES[body.code] || `Error code ${body.code}`
        const error = new Error(errMsg) as Error & { code: number }
        error.code = body.code
        return Promise.reject(error)
      }
      return { ...res, data: body.data }
    }
    return res
  },
  (err) => Promise.reject(err)
)

// ===== HTTP 接口 =====

// ---- 1.1 初始化 ----

/** 启动初始化：拉取全量基础数据 */
export async function fetchInit(): Promise<{
  agent: AgentInfo
  user_profile: UserProfits
  recent_moods: RecentMood[]
  current_state: {
    is_playing: boolean
    current_song: Song | null
    scene: string
    active_expression: string
  }
  playlists: Playlist[]
  netease_status: { login_status: boolean; nickname: string }
  qq: { provider: string; login_status: boolean; nickname: string; avatar_url: string | null }
  settings: Record<string, unknown>
}> {
  const res = await http.get('/init')
  return res.data
}

// ---- 1.2 设置功能（APIKey 配置）----

/** 获取所有服务密钥配置 */
export async function getSettings(): Promise<{ llm_apikey: string }> {
  const res = await http.get('/settings')
  return res.data
}

/** 增量更新 APIKey 配置 */
export async function updateSettings(data: {
  llm_apikey?: string
}): Promise<void> {
  await http.put('/settings', data)
}

// ---- 1.3 网易云账号登录 ----

/** 手机号+密码登录网易云 */
export async function postNeteasePhoneLogin(data: {
  phone: string
  password: string
}): Promise<{ login_status: boolean; nickname: string }> {
  const res = await http.post('/netease/login', { type: 'phone', ...data })
  return res.data
}

/** 获取 QR 登录临时 key */
export async function getNeteaseQrKey(): Promise<{ key: string }> {
  const res = await http.get('/netease/qr-key')
  return res.data
}

/** 根据 key 获取 QR 码 base64 图片 */
export async function getNeteaseQrCreate(key: string): Promise<{ qr_img: string }> {
  const res = await http.get('/netease/qr-create', { params: { key } })
  return res.data
}

/** 轮询检查 QR 码扫描状态 */
export async function postNeteaseQrCheck(key: string): Promise<{
  status: 'waiting' | 'scanning' | 'confirmed' | 'expired'
  nickname?: string
}> {
  const res = await http.post('/netease/qr-check', { key })
  return res.data
}

/** 查询当前网易云登录状态 */
export async function getNeteaseStatus(): Promise<{ login_status: boolean; nickname: string }> {
  const res = await http.get('/netease/status')
  return res.data
}

// ---- 1.8 QQ 音乐账号登录 ----

/** 查询 QQ 音乐登录状态（Agent 层统一格式） */
export async function getQqStatus(): Promise<{
  provider: string
  login_status: boolean
  nickname: string
  avatar_url: string | null
}> {
  const res = await http.get('/qq/status')
  return res.data
}

/** 获取 QQ 扫码登录二维码 */
export async function getQqQrcode(): Promise<{
  qr_type: string
  identifier: string
  mimetype: string
  data: string
  img: string
}> {
  const res = await http.get('/qq/login/qrcode')
  return res.data
}

/** 轮询检查 QQ 扫码状态 */
export async function getQqQrcodeStatus(identifier: string): Promise<{
  event: number
  done: boolean
  identifier: string
  login_type: string
}> {
  const res = await http.get('/qq/login/qrcode/status', { params: { identifier } })
  return res.data
}

/** 获取当前登录用户的网易云歌单列表 */
export async function getNeteasePlaylists(): Promise<{
  playlists: Array<{
    netease_id: number
    name: string
    song_count: number
    cover_url: string
    description: string
    creator: string
  }>
}> {
  const res = await http.get('/netease/playlists')
  return res.data
}

/** 从网易云账号导入歌单到本地 */
export async function importNeteasePlaylist(neteaseId: number): Promise<Playlist> {
  const res = await http.post('/netease/playlist/import', { netease_id: neteaseId })
  return res.data
}

/** 从 QQ 音乐导入歌单到本地（按 qq_id） */
export async function importQqPlaylist(qqId: string): Promise<Playlist> {
  const res = await http.post('/qq/playlist/import', { qq_id: qqId })
  return res.data
}

/** 获取当前登录用户的 QQ 歌单列表 */
export async function getQqPlaylists(): Promise<{
  playlists: Array<{
    id: number
    title: string
    picurl: string
    songnum: number
    desc: string
    nick: string
  }>
  total: number
}> {
  const res = await http.get('/qq/playlists')
  return res.data
}

/** 播放歌单中的指定歌曲（获取播放 URL → 返回给前端直接播放） */
export async function playPlaylistSong(song: {
  id: string
  name: string
  artists: Array<{ id: string; name: string }>
  album?: { id: string; name: string }
  cover_url?: string
  duration_ms?: number
}): Promise<{ play_url: string; song: any }> {
  const res = await http.post('/playlist/play', song)
  return res.data
}

/** 同步歌单队列到后端（歌单歌曲播放时调用，使 next/prev 在歌单内切换） */
export async function syncPlaylistQueue(songs: any[]): Promise<void> {
  await http.post('/playlist/sync-queue', { songs })
}

// ---- 1.4 歌单管理 ----

/** 通过网易云歌单分享链接导入歌单 */
export async function importPlaylist(playlistUrl: string): Promise<Playlist> {
  const res = await http.post('/playlist/import', { playlist_url: playlistUrl })
  return res.data
}

/** 查询本地全部导入歌单 */
export async function getPlaylists(): Promise<Playlist[]> {
  const res = await http.get('/playlist/list')
  // 后端返回 {playlists: [...]}，解包返回数组
  const data = res.data || {}
  return data.playlists || []
}

/** 查询单个歌单内所有歌曲详情 */
export async function getPlaylistDetail(playlistId: string): Promise<{
  playlist: Playlist
  songs: Song[]
}> {
  const res = await http.get(`/playlist/${playlistId}`)
  return res.data
}

/** 修改歌单基础信息（歌单名称、备注） */
export async function updatePlaylist(playlistId: string, data: {
  name?: string
  note?: string
}): Promise<void> {
  await http.put(`/playlist/${playlistId}`, data)
}

/** 删除本地存储的指定歌单及歌曲缓存 */
export async function deletePlaylist(playlistId: string): Promise<void> {
  await http.delete(`/playlist/${playlistId}`)
}

/** 新建一个空歌单 */
export async function createPlaylist(name: string): Promise<Playlist> {
  const res = await http.post('/playlist/create', { name })
  return res.data
}

/** 向指定歌单添加一首歌 */
export async function addSongToPlaylist(playlistId: string, song: {
  id: string
  name: string
  artists: Array<{ id: string; name: string }>
  album?: { id: string; name: string }
  cover_url?: string
  duration_ms?: number
  fee?: number
}): Promise<void> {
  await http.post(`/playlist/${playlistId}/songs`, { song })
}

// ---- 1.5 AI画像 ----

/** 手动触发AI分析全部本地歌单，生成/更新用户音乐画像 */
export async function triggerAnalyze(): Promise<{ update_at: number }> {
  const res = await http.post('/user/analyze')
  return res.data
}

/** 查询完整 UserProfits 用户画像数据 */
export async function getUserProfile(): Promise<UserProfits> {
  const res = await http.get('/user/profile')
  return res.data
}

/** 仅手动修改用户基础信息（昵称、头像），AI生成的音乐画像不可手动修改 */
export async function updateUserBaseInfo(data: {
  nickname?: string
  avatar_url?: string
}): Promise<void> {
  await http.put('/user/baseinfo', data)
}

// ---- 1.6 歌曲反馈 ----

/** 发送歌曲反馈 */
export async function sendFeedback(params: {
  song_id: string
  action: 'like' | 'dislike' | 'skip' | 'favorite'
}): Promise<void> {
  await http.post('/feedback', { ...params, ts: Date.now() })
}

// ---- 1.7 播放历史 ----

/** 查询播放历史 */
export async function fetchSongHistory(limit = 50, offset = 0): Promise<{
  total: number
  items: Array<{
    song_id: string
    played_at: number
    feedback: string
    duration_played_ms: number
  }>
}> {
  const res = await http.get('/history/songs', { params: { limit, offset } })
  return res.data
}

/** 查询当前播放列表（已播/正在/接下来） */
export async function fetchCurrentPlaylist(): Promise<{
  current_song: any
  queue: any[]
  played: any[]
}> {
  const res = await http.get('/playlist/current')
  return res.data
}

// ===== WebSocket 连接 =====

/** 创建 WebSocket 连接 */
export function createAgentSocket(): WebSocket {
  const ws = new WebSocket(WS_URL)
  return ws
}

/** 构建 WS 消息 */
export function buildWsMsg<T>(type: string, subtype: string, payload: T, id?: string): string {
  return JSON.stringify({
    type,
    subtype,
    id: id || crypto.randomUUID(),
    ts: Date.now(),
    payload,
  })
}

export { http, AGENT_BASE_URL, WS_URL }
