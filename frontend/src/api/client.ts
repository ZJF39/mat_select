/**
 * MatSelect API 客户端（契约 §4 全量封装）
 * 约定：成功直接返回业务对象；失败抛 ApiError（已解析后端 {error:{code,message}}）。
 */
import type {
  BackupStatus,
  CategoryNode,
  Constraints,
  DiffPayload,
  FeedbackPayload,
  FeedbackRecord,
  GapInsight,
  ImportPreview,
  ImportResult,
  LogEntry,
  MaterialCard,
  MaterialDetail,
  MaterialUpsert,
  NegativeFeedbackRow,
  ParseResult,
  Recommendation,
  Revision,
  SearchResult,
  SelectionTask,
  ShortlistItem,
  ShortlistTag,
  TaskMessage,
  WeightsConfig,
} from './types'

const BASE = '/api'

export class ApiError extends Error {
  code: string
  status: number
  constructor(code: string, message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
  }
}

type Query = Record<string, string | number | boolean | undefined | null | (string | number)[]>

function qs(params?: Query): string {
  if (!params) return ''
  const sp = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => {
    if (v === undefined || v === null || v === '') return
    if (Array.isArray(v)) {
      if (v.length) sp.set(k, v.join(','))
    } else {
      sp.set(k, String(v))
    }
  })
  const s = sp.toString()
  return s ? `?${s}` : ''
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${BASE}${path}`, {
      headers: init?.body instanceof FormData ? undefined : { 'Content-Type': 'application/json' },
      ...init,
    })
  } catch (e) {
    throw new ApiError('NETWORK', '无法连接本地服务，请确认后端已启动（127.0.0.1:8100）', 0)
  }
  if (!res.ok) {
    let code = 'INTERNAL'
    let message = `请求失败（HTTP ${res.status}）`
    try {
      const body = await res.json()
      if (body?.error) {
        code = body.error.code ?? code
        message = body.error.message ?? message
      } else if (body?.detail) {
        message = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
      }
    } catch {
      /* 非 JSON 错误体，保留默认文案 */
    }
    throw new ApiError(code, message, res.status)
  }
  if (res.status === 204) return undefined as T
  const ct = res.headers.get('content-type') ?? ''
  if (!ct.includes('application/json')) return (await res.text()) as unknown as T
  return (await res.json()) as T
}

const get = <T,>(p: string, q?: Query) => request<T>(`${p}${qs(q)}`)
const post = <T,>(p: string, body?: unknown) =>
  request<T>(p, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) })
const put = <T,>(p: string, body?: unknown) =>
  request<T>(p, { method: 'PUT', body: body === undefined ? undefined : JSON.stringify(body) })
const patch = <T,>(p: string, body?: unknown) =>
  request<T>(p, { method: 'PATCH', body: body === undefined ? undefined : JSON.stringify(body) })
const del = <T,>(p: string) => request<T>(p, { method: 'DELETE' })

/* ---------------- 材料 ---------------- */
export interface MaterialQuery {
  q?: string
  category_ids?: number[]
  processes?: string[]
  temp_min?: number
  price_max?: number
  flame?: string
  features?: string[]
  sort?: string
  order?: 'asc' | 'desc'
  archived?: 0 | 1
  page?: number
  page_size?: number
}

export const api = {
  health: () => get<{ ok: boolean; version: string; materials: number }>('/health'),

  /* 材料 */
  listMaterials: (q?: MaterialQuery) =>
    get<{ total: number; items: MaterialCard[] }>('/materials', q as Query),
  getMaterial: (uid: string) => get<MaterialDetail>(`/materials/${uid}`),
  createMaterial: (body: MaterialUpsert) => post<MaterialDetail>('/materials', body),
  updateMaterial: (uid: string, body: MaterialUpsert) =>
    put<{ material: MaterialDetail; new_version: number }>(`/materials/${uid}`, body),
  listRevisions: (uid: string) => get<{ items: Revision[] }>(`/materials/${uid}/revisions`),
  getDiff: (uid: string, a: number, b: number) =>
    get<DiffPayload>(`/materials/${uid}/revisions/${a}/diff`, { against: b }),
  restoreRevision: (uid: string, rid: number) =>
    post<{ material: MaterialDetail; new_version: number }>(
      `/materials/${uid}/revisions/${rid}/restore`,
    ),
  getMaterialFeedback: (uid: string) =>
    get<{ items: { dimension: string; count: number; active: boolean }[] }>(
      `/materials/${uid}/feedback`,
    ),
  clearMaterialFeedback: (uid: string) => del<{ ok: boolean }>(`/materials/${uid}/feedback`),
  listCategories: () => get<{ items: CategoryNode[] }>('/categories'),
  createCategory: (body: { name: string; parent_id?: number | null }) =>
    post<CategoryNode>('/categories', body),
  renameCategory: (id: number, name: string) => patch<CategoryNode>(`/categories/${id}`, { name }),
  deleteCategory: (id: number) => del<{ ok: boolean }>(`/categories/${id}`),

  /* 推荐 */
  parse: (text: string, task_id?: number) =>
    post<ParseResult>('/recommend/parse', { text, task_id }),
  run: (constraints: Constraints, task_id?: number) =>
    post<{ results: Recommendation[]; degraded: boolean; relaxed: string[] }>('/recommend/run', {
      constraints,
      task_id,
    }),

  /* 任务 / 会话 */
  listTasks: (q?: { status?: 'active' | 'archived'; q?: string }) =>
    get<{ items: SelectionTask[] }>('/tasks', q as Query),
  createTask: (body?: { title?: string }) => post<SelectionTask>('/tasks', body ?? {}),
  updateTask: (id: number, body: Partial<Pick<SelectionTask, 'title' | 'pinned' | 'status'>>) =>
    patch<SelectionTask>(`/tasks/${id}`, body),
  listMessages: (id: number) => get<{ items: TaskMessage[] }>(`/tasks/${id}/messages`),
  sendMessage: (id: number, text: string) =>
    post<{ user: TaskMessage; assistant: TaskMessage }>(`/tasks/${id}/messages`, { text }),

  /* 待选 */
  listShortlist: (taskId: number) => get<{ items: ShortlistItem[] }>(`/tasks/${taskId}/shortlist`),
  addShortlist: (taskId: number, material_uid: string, tag?: ShortlistTag) =>
    post<ShortlistItem>(`/tasks/${taskId}/shortlist`, { material_uid, tag }),
  updateShortlist: (itemId: number, body: { user_note?: string; tag?: ShortlistTag }) =>
    patch<ShortlistItem>(`/shortlist/${itemId}`, body),
  reorderShortlist: (taskId: number, ids: number[]) =>
    put<{ items: ShortlistItem[] }>(`/tasks/${taskId}/shortlist/order`, { ids }),
  removeShortlist: (itemId: number) => del<{ ok: boolean }>(`/shortlist/${itemId}`),

  /* 回评 */
  submitFeedback: (taskId: number, body: FeedbackPayload) =>
    post<{ parsed: FeedbackRecord['parsed_reason']; penalty_applied: boolean; feedback_id: number }>(
      `/tasks/${taskId}/feedback`,
      body,
    ),
  getTaskFeedback: (taskId: number) => get<FeedbackRecord | null>(`/tasks/${taskId}/feedback`),
  listGaps: (range: 'week' | 'month' | 'all' = 'week') =>
    get<{ items: GapInsight[] }>('/insights/gaps', { range }),
  listMyFeedback: () => get<{ items: NegativeFeedbackRow[] }>('/settings/feedback'),
  clearMyFeedback: () => del<{ ok: boolean }>('/settings/feedback'),

  /* 导出 / 导入 */
  exportUrl: '/api/export',
  exportMaterials: (body: {
    scope: 'all' | 'filtered' | 'selected' | 'shortlist'
    format: 'json' | 'xlsx' | 'md'
    include_work_data: boolean
    ids?: string[]
    task_id?: number
    dbg?: { q?: string; category_ids?: number[]; processes?: string[]; temp_min?: number }
  }) => post<string | Blob>('/export', body),
  parseImport: (file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return request<ImportPreview>('/import/parse', { method: 'POST', body: fd })
  },
  commitImport: (token: string, conflict_policy: 'skip' | 'overwrite' | 'duplicate') =>
    post<ImportResult>('/import/commit', { token, conflict_policy }),

  /* 设置 / 系统 */
  getWeights: () => get<WeightsConfig>('/settings/weights'),
  saveWeights: (body: { dims: { key: string; weight: number }[]; penalty?: { threshold: number; max: number } }) =>
    put<WeightsConfig>('/settings/weights', body),
  listLogs: (limit = 50) => get<{ items: LogEntry[] }>('/logs', { limit }),
  search: (q: string, limit = 8) => get<SearchResult>('/search', { q, limit }),
  backupStatus: () => get<BackupStatus>('/backup/status'),
  runBackup: () => post<{ ok: boolean; last_backup_at: string; location: string }>('/backup/run'),
}

/** 触发浏览器下载（导出接口返回文件流时使用） */
export async function downloadExport(body: Parameters<typeof api.exportMaterials>[0]) {
  const res = await fetch(api.exportUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new ApiError('EXPORT_FAILED', '导出失败，请重试', res.status)
  const cd = res.headers.get('content-disposition') ?? ''
  const m = /filename\*?=(?:UTF-8'')?"?([^\";]+)"?/i.exec(cd)
  const filename = m ? decodeURIComponent(m[1]) : 'MatSelect_导出.bin'
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
  return filename
}
