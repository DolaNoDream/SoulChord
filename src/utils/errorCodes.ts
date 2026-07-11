/**
 * 通用错误码映射（对齐 frontend-agent-api.md 0.3 节）
 * 用于前端展示异常提示信息
 */

export const ERROR_CODE_MAP: Record<number, string> = {
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

/** 根据错误码获取用户可读的错误消息 */
export function getErrorMessage(code: number, fallback?: string): string {
  return ERROR_CODE_MAP[code] || fallback || `未知错误 (code: ${code})`
}

/** 检查是否为 APIKey/登录未配置的错误 */
export function isAuthError(code: number): boolean {
  return code === 1002
}

/** 检查是否为 LLM 调用失败 */
export function isLlmError(code: number): boolean {
  return code === 2001 || code === 2002 || code === 2003
}

/** 检查是否为网易云服务错误 */
export function isNeteaseError(code: number): boolean {
  return code === 3001 || code === 3002
}
