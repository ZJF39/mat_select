import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, downloadExport } from '../api/client'
import type { Constraints, FeedbackPayload, Recommendation, ShortlistTag, TaskMessage } from '../api/types'
import { TaskListPanel } from '../components/TaskListPanel'
import { ShortlistPanel } from '../components/ShortlistPanel'
import { ConstraintChips } from '../components/ConstraintChips'
import { FeedbackModal } from '../components/FeedbackModal'
import { Modal } from '../components/Modal'
import { Notice } from '../components/Notice'
import { EmptyState } from '../components/EmptyState'
import { Skeleton } from '../components/Skeleton'
import { Icon } from '../icons'
import { formatTime, pct } from '../utils/format'
import { toast, ToastHost } from '../components/Toast'
import { SessionHeader } from '../features/workbench/SessionHeader'
import { Composer } from '../features/workbench/Composer'
import { ReviewBar } from '../features/workbench/ReviewBar'
import { RecommendationList } from '../features/recommend/RecommendationList'
import './pages.css'

/** 04 选型任务工作台 ★核心屏（原型 02 §04 + 05 §1.1） */

const EXAMPLES = [
  '保险丝座，耐温 150°C，注塑',
  '连接器外壳，需要阻燃 V-0，成本敏感',
  '发动机舱支架，长期 120°C，要求高刚性',
]

const PROCESS_CHOICES = ['注塑', '挤出', '吹塑', '热成型', '压缩模塑']

export default function TaskWorkbenchPage() {
  const { id = '' } = useParams()
  const taskId = Number(id)
  const valid = Number.isFinite(taskId) && taskId > 0
  const navigate = useNavigate()
  const qc = useQueryClient()

  const [pendingConstraints, setPendingConstraints] = useState<Record<number, Constraints>>({})
  const [confirmedResults, setConfirmedResults] = useState<Record<number, Recommendation[]>>({})
  const [relaxedNote, setRelaxedNote] = useState<Record<number, string[]>>({})
  const [runningId, setRunningId] = useState<number | null>(null)
  const [pendingText, setPendingText] = useState<string | null>(null)
  const [sendError, setSendError] = useState<string | null>(null)
  const [failedText, setFailedText] = useState<string | null>(null)
  const [inline, setInline] = useState<Record<number, { process: string; temp: string }>>({})
  const [newIds, setNewIds] = useState<number[]>([])
  const [feedbackOpen, setFeedbackOpen] = useState(false)
  const [archiveOpen, setArchiveOpen] = useState(false)
  const [renameOpen, setRenameOpen] = useState(false)
  const [renameValue, setRenameValue] = useState('')
  const feedbackTrigger = useRef<HTMLButtonElement>(null)
  const flowRef = useRef<HTMLDivElement>(null)

  const tasks = useQuery({ queryKey: ['tasks'], queryFn: () => api.listTasks(), staleTime: 10_000 })
  const messages = useQuery({
    queryKey: ['messages', taskId],
    queryFn: () => api.listMessages(taskId),
    enabled: valid,
    staleTime: 30_000,
  })
  const shortlist = useQuery({
    queryKey: ['shortlist', taskId],
    queryFn: () => api.listShortlist(taskId),
    enabled: valid,
    staleTime: 30_000,
  })
  const feedback = useQuery({
    queryKey: ['task-feedback', taskId],
    queryFn: () => api.getTaskFeedback(taskId),
    enabled: valid,
    staleTime: 30_000,
  })

  const task = useMemo(() => tasks.data?.items.find((t) => t.id === taskId), [tasks.data, taskId])
  const msgList = messages.data?.items ?? []
  const shortlistItems = shortlist.data?.items ?? []

  /* 新消息自动滚到底 */
  useEffect(() => {
    const el = flowRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [msgList.length, pendingText, runningId])

  /* ---------- 发送（③ 回显约束，不出结果） ---------- */
  const sendMutation = useMutation({
    mutationFn: (text: string) => api.sendMessage(taskId, text),
    onSuccess: (res) => {
      setPendingText(null)
      setSendError(null)
      setFailedText(null)
      if (res.assistant?.constraints) {
        setPendingConstraints((p) => ({ ...p, [res.assistant.id]: res.assistant.constraints! }))
      }
      qc.invalidateQueries({ queryKey: ['messages', taskId] })
      qc.invalidateQueries({ queryKey: ['tasks'] })
    },
    onError: (e, text) => {
      setPendingText(null)
      setSendError(e instanceof Error ? e.message : '发送失败')
      setFailedText(text)
    },
  })

  const send = (text: string) => {
    setPendingText(text)
    setSendError(null)
    sendMutation.mutate(text)
  }

  /* ---------- 确认约束 → 生成推荐（④） ---------- */
  const runMutation = useMutation({
    mutationFn: ({ constraints }: { msgId: number; constraints: Constraints }) => api.run(constraints, taskId),
    onSuccess: (res, vars) => {
      setConfirmedResults((s) => ({ ...s, [vars.msgId]: res.results }))
      setRelaxedNote((s) => ({ ...s, [vars.msgId]: res.relaxed ?? [] }))
      setPendingConstraints((p) => {
        const n = { ...p }
        delete n[vars.msgId]
        return n
      })
      setRunningId(null)
      qc.invalidateQueries({ queryKey: ['messages', taskId] })
      qc.invalidateQueries({ queryKey: ['tasks'] })
      if (!res.results.length) toast('没有同时满足的材料，请按提示放宽或修改约束', 'danger')
      else toast(`已生成 ${res.results.length} 条推荐`, 'success')
    },
    onError: (e) => {
      setRunningId(null)
      toast(e instanceof Error ? e.message : '生成推荐失败', 'danger')
    },
  })

  const confirmConstraints = (msgId: number, c: Constraints) => {
    setRunningId(msgId)
    runMutation.mutate({ msgId, constraints: c })
  }

  /* ---------- 待选 ---------- */
  const addMutation = useMutation({
    mutationFn: (uid: string) => api.addShortlist(taskId, uid),
    onSuccess: (item) => {
      setNewIds((s) => [...s, item.id])
      qc.invalidateQueries({ queryKey: ['shortlist', taskId] })
      qc.invalidateQueries({ queryKey: ['tasks'] })
      toast('已加入待选', 'success')
      window.setTimeout(() => setNewIds((s) => s.filter((x) => x !== item.id)), 800)
    },
    onError: (e) => toast(e instanceof Error ? e.message : '加入待选失败', 'danger'),
  })

  const patchShortlist = useCallback(
    (id: number, body: { user_note?: string; tag?: ShortlistTag }, optimistic: (items: ReturnType<typeof Object>) => unknown) => {
      const key = ['shortlist', taskId]
      const prev = qc.getQueryData<{ items: typeof shortlistItems }>(key)
      qc.setQueryData(key, (old: { items: typeof shortlistItems } | undefined) =>
        old ? { items: old.items.map((it) => (it.id === id ? { ...it, ...body } : it)) } : old,
      )
      void optimistic
      return api
        .updateShortlist(id, body)
        .then(() => {
          qc.invalidateQueries({ queryKey: key })
        })
        .catch((e) => {
          if (prev) qc.setQueryData(key, prev)
          toast(e instanceof Error ? e.message : '保存失败，已回滚', 'danger')
        })
    },
    [qc, taskId, shortlistItems],
  )

  const removeMutation = useMutation({
    mutationFn: (itemId: number) => api.removeShortlist(itemId),
    onMutate: async (itemId: number) => {
      const key = ['shortlist', taskId]
      await qc.cancelQueries({ queryKey: key })
      const prev = qc.getQueryData<{ items: typeof shortlistItems }>(key)
      qc.setQueryData(key, (old: { items: typeof shortlistItems } | undefined) =>
        old ? { items: old.items.filter((it) => it.id !== itemId) } : old,
      )
      return { prev }
    },
    onError: (e, _id, ctx) => {
      if (ctx?.prev) qc.setQueryData(['shortlist', taskId], ctx.prev)
      toast(e instanceof Error ? e.message : '移出待选失败，已回滚', 'danger')
    },
    onSuccess: () => {
      toast('已移出待选', 'success')
      qc.invalidateQueries({ queryKey: ['shortlist', taskId] })
      qc.invalidateQueries({ queryKey: ['tasks'] })
    },
  })

  const reorderMutation = useMutation({
    mutationFn: (ids: number[]) => api.reorderShortlist(taskId, ids),
    onMutate: async (ids: number[]) => {
      const key = ['shortlist', taskId]
      await qc.cancelQueries({ queryKey: key })
      const prev = qc.getQueryData<{ items: typeof shortlistItems }>(key)
      qc.setQueryData(key, (old: { items: typeof shortlistItems } | undefined) =>
        old
          ? {
              items: ids
                .map((i, idx) => {
                  const hit = old.items.find((x) => x.id === i)
                  return hit ? { ...hit, sort_order: idx } : undefined
                })
                .filter((x): x is (typeof shortlistItems)[number] => Boolean(x)),
            }
          : old,
      )
      return { prev }
    },
    onError: (e, _ids, ctx) => {
      if (ctx?.prev) qc.setQueryData(['shortlist', taskId], ctx.prev)
      toast(e instanceof Error ? e.message : '排序保存失败，已回滚', 'danger')
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ['shortlist', taskId] }),
  })

  /* ---------- 任务操作 ---------- */
  const updateTask = useMutation({
    mutationFn: (body: { title?: string; pinned?: boolean; status?: 'active' | 'archived' }) =>
      api.updateTask(taskId, body),
    onSuccess: (_r, body) => {
      setArchiveOpen(false)
      setRenameOpen(false)
      toast(body.status === 'archived' ? '任务已归档' : body.title ? '已重命名' : '已更新', 'success')
      qc.invalidateQueries({ queryKey: ['tasks'] })
      qc.invalidateQueries({ queryKey: ['messages', taskId] })
    },
    onError: (e) => toast(e instanceof Error ? e.message : '更新失败', 'danger'),
  })

  /* ---------- 回评 ---------- */
  const feedbackMutation = useMutation({
    mutationFn: (payload: FeedbackPayload) => api.submitFeedback(taskId, payload),
    onSuccess: () => {
      setFeedbackOpen(false)
      toast('已记录，下次推荐会参考这条反馈', 'success')
      qc.invalidateQueries({ queryKey: ['task-feedback', taskId] })
    },
    onError: (e) => toast(e instanceof Error ? e.message : '回评提交失败', 'danger'),
  })

  const exportMarkdown = async () => {
    try {
      await downloadExport({ scope: 'shortlist', format: 'md', include_work_data: true, task_id: taskId })
      toast('已导出到下载目录', 'success')
    } catch {
      toast('导出失败，请重试', 'danger')
    }
  }

  const lastAssistant = [...msgList].reverse().find((m) => m.role === 'assistant')
  const recommendedMaterials = (lastAssistant?.results ?? []).map((r) => r.material)

  const archived = task?.status === 'archived'

  /* ---------- 消息渲染 ---------- */
  const renderMessage = (msg: TaskMessage) => {
    if (msg.role === 'user') {
      return (
        <div key={msg.id} className="ms-msg ms-msg--user">
          <div className="ms-msg__bubble">{msg.text}</div>
          <span className="ms-msg__time">{formatTime(msg.created_at)}</span>
        </div>
      )
    }

    const pending = pendingConstraints[msg.id]
    const resolved = confirmedResults[msg.id] ?? msg.results
    const isPending = !!pending

    return (
      <div key={msg.id} className="ms-msg ms-msg--assistant">
        {msg.text && (
          <div className="ms-msg__bubble" style={{ background: 'transparent', padding: 0, color: 'var(--text-2)' }}>
            {msg.text}
          </div>
        )}

        {/* 约束回显块（③） */}
        {pending && (
          <div className="ms-constraints">
            <div className="ms-constraints__hint">已识别约束 · 点击标签可直接修改（确认后才会参与硬约束过滤）</div>
            <ConstraintChips
              constraints={pending}
              onRemove={(key) => {
                setPendingConstraints((p) => {
                  const c = { ...p[msg.id] }
                  if (key === 'extra') c.extra = c.extra.slice(0, -1)
                  else (c as Record<string, unknown>)[key] = null
                  return { ...p, [msg.id]: c }
                })
              }}
              onChange={(key, value) => {
                setPendingConstraints((p) => ({ ...p, [msg.id]: { ...p[msg.id], [key]: value } }))
              }}
              onAdd={(key, value) => {
                setPendingConstraints((p) => {
                  const c = { ...p[msg.id] }
                  if (key === 'extra') c.extra = [...c.extra, String(value)]
                  else (c as Record<string, unknown>)[key] = value
                  return { ...p, [msg.id]: c }
                })
              }}
            />
            <div className="ms-constraints__foot">
              <span className="ms-constraints__conf">
                解析置信度 {msg.confidence != null ? msg.confidence.toFixed(2) : '—'} · 未识别为硬约束的内容将用于语义排序
              </span>
              <button className="ms-btn ms-btn--primary ms-btn--sm" onClick={() => confirmConstraints(msg.id, pending)} disabled={runningId === msg.id}>
                {runningId === msg.id && <span className="ms-spin" style={{ color: '#fff' }} />}
                确认约束并生成推荐
              </button>
            </div>
          </div>
        )}

        {/* 解析失败（无约束、无结果）就地补救 */}
        {!pending && !resolved && !msg.results && (
          <Notice tone="warning">
            <div className="ms-col" style={{ gap: 8 }}>
              <span>没能理解您的需求，请尝试：① 直接选择工艺和温度；② 换个说法</span>
              <div className="ms-row ms-gap-3" style={{ flexWrap: 'wrap' }}>
                <select
                  className="ms-input"
                  style={{ width: 140, height: 30 }}
                  aria-label="成型工艺"
                  value={inline[msg.id]?.process ?? ''}
                  onChange={(e) => setInline((s) => ({ ...s, [msg.id]: { process: e.target.value, temp: s[msg.id]?.temp ?? '' } }))}
                >
                  <option value="">选择工艺</option>
                  {PROCESS_CHOICES.map((p) => (
                    <option key={p} value={p}>
                      {p}
                    </option>
                  ))}
                </select>
                <input
                  className="ms-input ms-input--mono"
                  style={{ width: 110, height: 30 }}
                  type="number"
                  placeholder="温度 °C"
                  aria-label="温度上限"
                  value={inline[msg.id]?.temp ?? ''}
                  onChange={(e) => setInline((s) => ({ ...s, [msg.id]: { process: s[msg.id]?.process ?? '', temp: e.target.value } }))}
                />
                <button
                  className="ms-btn ms-btn--secondary ms-btn--sm"
                  onClick={() =>
                    confirmConstraints(msg.id, {
                      part_type: null,
                      process: inline[msg.id]?.process || null,
                      temp_limit: inline[msg.id]?.temp ? Number(inline[msg.id].temp) : null,
                      extra: [],
                    })
                  }
                  disabled={runningId === msg.id}
                >
                  按此约束生成推荐
                </button>
              </div>
            </div>
          </Notice>
        )}

        {/* 推荐中 */}
        {runningId === msg.id && (
          <div className="ms-col ms-gap-4" style={{ width: '100%' }}>
            <div className="ms-msg__parsing">
              <span className="ms-spin" />
              正在筛选并打分…
            </div>
            <div className="ms-skel-card" style={{ height: 132 }}>
              <Skeleton height={18} width="45%" />
              <Skeleton height={12} width="70%" />
              <Skeleton height={12} width="60%" />
            </div>
          </div>
        )}

        {/* 放宽说明 */}
        {relaxedNote[msg.id]?.length > 0 && (
          <Notice tone="warning">
            <span>已放宽：{relaxedNote[msg.id].join('；')}，结果中标注了被放宽的条件。</span>
          </Notice>
        )}

        {/* 推荐结果（④ 之后才可能出现） */}
        {!pending && runningId !== msg.id && resolved !== undefined && (
          <RecommendationList
            results={resolved}
            alreadyInShortlist={(uid) => shortlistItems.some((it) => it.material.uid === uid)}
            onAddShortlist={(uid) => addMutation.mutate(uid)}
            onAdopt={(uid) => addMutation.mutate(uid)}
            emptyConstraints={msg.constraints ?? undefined}
            onRelax={() => {
              const c = msg.constraints
              if (c?.temp_limit != null) {
                const next = { ...c, temp_limit: Math.max(0, c.temp_limit - 10) }
                setPendingConstraints((p) => ({ ...p, [msg.id]: next }))
                confirmConstraints(msg.id, next)
                toast(`已放宽温度到 ${next.temp_limit} °C 重新推荐`, 'success')
              }
            }}
            onModify={() => {
              const el = flowRef.current?.querySelector('.ms-constraints')
              el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
              toast('点击上方约束标签即可修改')
            }}
          />
        )}

        <span className="ms-msg__time">{formatTime(msg.created_at)}</span>
      </div>
    )
  }

  return (
    <>
      <ToastHost />
      <TaskListPanel
        tasks={tasks.data?.items ?? []}
        activeId={taskId}
        loading={tasks.isLoading}
        error={tasks.isError ? '任务列表加载失败' : null}
        onRetry={() => tasks.refetch()}
        onCreate={async () => {
          try {
            const t = await api.createTask({})
            qc.invalidateQueries({ queryKey: ['tasks'] })
            navigate(`/tasks/${t.id}`)
          } catch (e) {
            toast(e instanceof Error ? e.message : '新建任务失败', 'danger')
          }
        }}
        onSelect={(next) => navigate(`/tasks/${next}`)}
      />

      {!valid ? (
        <main className="ms-main">
          <EmptyState
            icon="search"
            title="任务不存在"
            desc="链接里的任务编号无效，返回任务列表重新选择。"
            action={
              <button className="ms-btn ms-btn--primary" onClick={() => navigate('/tasks')}>
                返回任务列表
              </button>
            }
          />
        </main>
      ) : (
        <div className="ms-wb">
          <section className="ms-wb__session">
            {tasks.isLoading ? (
              <div className="ms-wb__head">
                <Skeleton height={16} width={200} />
              </div>
            ) : (
              <SessionHeader
                title={task?.title ?? '选型任务'}
                statusLabel={archived ? '已归档' : `进行中 · ${task?.recommendation_count ?? 0} 条推荐`}
                archived={archived}
                onRename={() => {
                  setRenameValue(task?.title ?? '')
                  setRenameOpen(true)
                }}
                onPin={() => updateTask.mutate({ pinned: !task?.pinned })}
                onArchive={() => setArchiveOpen(true)}
                onExport={exportMarkdown}
              />
            )}

            <div className="ms-wb__flow" ref={flowRef}>
              {messages.isError ? (
                <Notice tone="danger">
                  <div className="ms-col" style={{ gap: 6 }}>
                    <span>会话加载失败：{messages.error instanceof Error ? messages.error.message : '未知错误'}</span>
                    <button className="ms-link" style={{ background: 'none', border: 'none', alignSelf: 'flex-start' }} onClick={() => messages.refetch()}>
                      重试
                    </button>
                  </div>
                </Notice>
              ) : messages.isLoading ? (
                <div className="ms-msg-list">
                  <div className="ms-msg ms-msg--user">
                    <Skeleton height={40} width={280} />
                  </div>
                  <div className="ms-msg ms-msg--assistant">
                    <Skeleton height={16} width={220} />
                    <Skeleton height={12} width={320} />
                  </div>
                </div>
              ) : msgList.length === 0 && !pendingText ? (
                <EmptyState
                  icon="sparkles"
                  title="用一句话说清选材需求"
                  desc="系统会先回显识别到的硬约束，由你确认后再生成推荐。点一个示例直接开始："
                  action={
                    <div className="ms-col ms-gap-3" style={{ justifyContent: 'center' }}>
                      {EXAMPLES.map((ex) => (
                        <button key={ex} className="ms-btn ms-btn--secondary" onClick={() => send(ex)}>
                          {ex}
                        </button>
                      ))}
                    </div>
                  }
                />
              ) : (
                <div className="ms-msg-list">
                  {msgList.map(renderMessage)}
                  {pendingText && (
                    <>
                      <div className="ms-msg ms-msg--user">
                        <div className="ms-msg__bubble">{pendingText}</div>
                      </div>
                      <div className="ms-msg ms-msg--assistant">
                        <div className="ms-msg__parsing">
                          <span className="ms-spin" />
                          正在解析约束…
                        </div>
                      </div>
                    </>
                  )}
                </div>
              )}

              {sendError && (
                <Notice tone="danger">
                  <div className="ms-row ms-gap-4" style={{ flexWrap: 'wrap' }}>
                    <span>{sendError}</span>
                    <button className="ms-btn ms-btn--sm ms-btn--secondary" onClick={() => failedText && send(failedText)}>
                      重新发送
                    </button>
                  </div>
                </Notice>
              )}

              {archived && (
                <Notice tone="warning">
                  <div className="ms-row ms-gap-4" style={{ flexWrap: 'wrap' }}>
                    <span>已归档任务不可继续追问，可复制为新任务。</span>
                    <button
                      className="ms-btn ms-btn--sm ms-btn--secondary"
                      onClick={async () => {
                        try {
                          const t = await api.createTask({ title: `${task?.title ?? '选型任务'}（副本）` })
                          qc.invalidateQueries({ queryKey: ['tasks'] })
                          navigate(`/tasks/${t.id}`)
                        } catch (e) {
                          toast(e instanceof Error ? e.message : '复制失败', 'danger')
                        }
                      }}
                    >
                      复制为新任务
                    </button>
                  </div>
                </Notice>
              )}

              {msgList.length > 0 && !archived && (
                <ReviewBar
                  result={feedback.data?.result ?? null}
                  onSuccess={() => feedbackMutation.mutate({ result: 'success' })}
                  onFail={() => setFeedbackOpen(true)}
                  onSkip={() => feedbackMutation.mutate({ result: 'skipped' })}
                  onEdit={() => setFeedbackOpen(true)}
                />
              )}
            </div>

            <Composer
              onSend={send}
              disabled={archived || sendMutation.isPending}
              placeholder={
                archived
                  ? '已归档任务不可继续追问'
                  : '描述你的选材需求，例如「保险丝座，耐温 150°C，注塑」'
              }
            />
          </section>

          <ShortlistPanel
            items={shortlistItems}
            loading={shortlist.isLoading}
            error={shortlist.isError ? '待选加载失败' : null}
            onRetry={() => shortlist.refetch()}
            newIds={newIds}
            onReorder={(ids) => reorderMutation.mutate(ids)}
            onRemove={(itemId) => removeMutation.mutate(itemId)}
            onNoteChange={(itemId, note) => {
              void patchShortlist(itemId, { user_note: note }, () => undefined)
              toast('备注已保存', 'success')
            }}
            onTagChange={(itemId, tag) => {
              void patchShortlist(itemId, { tag }, () => undefined)
            }}
            onExport={async () => {
              try {
                await downloadExport({ scope: 'shortlist', format: 'xlsx', include_work_data: true, task_id: taskId })
                toast('已导出对比表', 'success')
              } catch {
                toast('导出失败，请重试', 'danger')
              }
            }}
          />
        </div>
      )}

      <FeedbackModal
        open={feedbackOpen}
        triggerRef={feedbackTrigger}
        materials={recommendedMaterials}
        taskTitle={task?.title ?? '选型任务'}
        submitting={feedbackMutation.isPending}
        onClose={() => setFeedbackOpen(false)}
        onSubmit={(payload) => feedbackMutation.mutate(payload)}
      />

      <Modal
        open={renameOpen}
        title="重命名任务"
        width={420}
        onClose={() => setRenameOpen(false)}
        footer={
          <>
            <span />
            <div className="ms-row ms-gap-3">
              <button className="ms-btn ms-btn--ghost" onClick={() => setRenameOpen(false)}>
                取消
              </button>
              <button className="ms-btn ms-btn--primary" onClick={() => renameValue.trim() && updateTask.mutate({ title: renameValue.trim() })}>
                保存
              </button>
            </div>
          </>
        }
      >
        <input
          className="ms-input"
          autoFocus
          value={renameValue}
          aria-label="任务名称"
          onChange={(e) => setRenameValue(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && renameValue.trim() && updateTask.mutate({ title: renameValue.trim() })}
        />
      </Modal>

      <Modal
        open={archiveOpen}
        title="归档任务"
        width={420}
        onClose={() => setArchiveOpen(false)}
        footer={
          <>
            <span className="ms-muted" style={{ fontSize: 'var(--fs-caption)' }}>
              归档不删除数据，随时可在「已归档任务」中找回
            </span>
            <div className="ms-row ms-gap-3">
              <button className="ms-btn ms-btn--ghost" onClick={() => setArchiveOpen(false)}>
                取消
              </button>
              <button className="ms-btn ms-btn--primary" onClick={() => updateTask.mutate({ status: 'archived' })} disabled={updateTask.isPending}>
                确认归档
              </button>
            </div>
          </>
        }
      >
        <span>归档后不在默认列表显示，可在「已归档任务」检索到。</span>
      </Modal>
    </>
  )
}
