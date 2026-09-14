import { useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, downloadExport } from '../api/client'
import type { ShortlistItem, ShortlistTag } from '../api/types'
import { SidePanel } from '../layout/SidePanel'
import { CompareRow } from '../components/CompareRow'
import { EmptyState } from '../components/EmptyState'
import { Notice } from '../components/Notice'
import { Skeleton } from '../components/Skeleton'
import { Icon } from '../icons'
import { toast, ToastHost } from '../components/Toast'
import { TAG_LABEL } from '../utils/format'
import './pages.css'

/** 05 · 待选清单 · 对比表（原型 02 §05）
 *  目标：候选材料横向对比 + 记下「只有我知道的信息」。
 *  待选清单是个人工作态数据：不写入材料主库、不参与推荐排序。 */

export default function ShortlistPage() {
  const { id } = useParams<{ id: string }>()
  const taskId = Number(id)
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [dragIndex, setDragIndex] = useState<number | null>(null)
  const [newIds, setNewIds] = useState<number[]>([])
  const [busy, setBusy] = useState(false)

  const task = useQuery({
    queryKey: ['task', taskId],
    queryFn: async () => {
      const { items } = await api.listTasks({ status: 'active' })
      const archived = await api.listTasks({ status: 'archived' })
      return [...items, ...archived.items].find((t) => t.id === taskId) ?? null
    },
    enabled: Number.isFinite(taskId),
    staleTime: 30_000,
  })

  const shortlist = useQuery({
    queryKey: ['shortlist', taskId],
    queryFn: () => api.listShortlist(taskId),
    enabled: Number.isFinite(taskId),
    staleTime: 10_000,
  })

  const items: ShortlistItem[] = shortlist.data?.items ?? []

  const stats = useMemo(() => {
    const acc: Record<string, number> = { key: 0, pending: 0, rejected: 0 }
    items.forEach((i) => {
      if (acc[i.tag] !== undefined) acc[i.tag] += 1
    })
    return acc
  }, [items])

  const update = useMutation({
    mutationFn: (v: { id: number; body: { user_note?: string; tag?: ShortlistTag } }) =>
      api.updateShortlist(v.id, v.body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['shortlist', taskId] }),
    onError: () => {
      toast('保存失败，已回滚', 'danger')
      qc.invalidateQueries({ queryKey: ['shortlist', taskId] })
    },
  })

  const reorder = useMutation({
    mutationFn: (ids: number[]) => api.reorderShortlist(taskId, ids),
    onError: () => {
      toast('排序保存失败，已回滚', 'danger')
      qc.invalidateQueries({ queryKey: ['shortlist', taskId] })
    },
  })

  const remove = useMutation({
    mutationFn: (itemId: number) => api.removeShortlist(itemId),
    onSuccess: () => {
      toast('已移出待选（不影响材料库数据）', 'success')
      qc.invalidateQueries({ queryKey: ['shortlist', taskId] })
    },
  })

  /** 乐观更新：先改本地顺序，再提交；失败由 mutation 的 onError 回滚 */
  const move = (from: number, to: number) => {
    if (from === to || from < 0 || to < 0 || from >= items.length || to >= items.length) return
    const next = [...items]
    const [moved] = next.splice(from, 1)
    next.splice(to, 0, moved)
    qc.setQueryData(['shortlist', taskId], { items: next })
    reorder.mutate(next.map((i) => i.id))
  }

  const exportCompare = async (format: 'xlsx' | 'md') => {
    setBusy(true)
    try {
      if (format === 'xlsx') {
        await downloadExport({ scope: 'shortlist', format: 'xlsx', include_work_data: false, task_id: taskId })
        toast('对比表已导出', 'success')
      } else {
        const text = (await api.exportMaterials({
          scope: 'shortlist',
          format: 'md',
          include_work_data: false,
          task_id: taskId,
        })) as unknown as string
        await navigator.clipboard.writeText(String(text))
        toast('已复制为 Markdown', 'success')
      }
    } catch {
      toast('导出失败，请重试', 'danger')
    } finally {
      setBusy(false)
    }
  }

  const errorMsg = shortlist.error instanceof Error ? shortlist.error.message : null

  return (
    <>
      <ToastHost />
      <SidePanel
        title="选型任务"
        sub={`待选 ${items.length} 条`}
        headExtra={
          <button className="ms-link" style={{ background: 'none', border: 'none' }} onClick={() => navigate('/tasks')}>
            全部任务
          </button>
        }
        foot={<span>待选清单随任务持久化；「删除」即归档，可在已归档任务中检索到。</span>}
      >
        <button className="ms-btn ms-btn--secondary" style={{ width: '100%' }} onClick={() => navigate(`/tasks/${taskId}`)}>
          <Icon name="sparkles" size={14} />
          返回选型工作台
        </button>
        <div className="ms-col" style={{ gap: 'var(--sp-4)', marginTop: 'var(--sp-6)' }}>
          <div className="ms-task-item__meta">任务：{task.data?.title || '加载中…'}</div>
          <div className="ms-task-item__meta">
            {task.data ? `${task.data.recommendation_count} 条推荐 · ${task.data.shortlist_count} 待选` : ''}
          </div>
        </div>
      </SidePanel>

      <main className="ms-main">
        <div className="ms-page-header">
          <div>
            <h1 className="ms-page-header__title">待选清单 · 对比表</h1>
            <div className="ms-page-header__sub">
              共 {items.length} 条候选 · 备注改动即时保存 · 拖拽行首可调整顺序
            </div>
          </div>
          <div className="ms-page-header__actions">
            <button className="ms-btn ms-btn--secondary" disabled={busy || items.length === 0} onClick={() => exportCompare('md')}>
              复制为 Markdown
            </button>
            <button className="ms-btn ms-btn--primary" disabled={busy || items.length === 0} onClick={() => exportCompare('xlsx')}>
              <Icon name="download" size={14} />
              导出对比表 · Excel
            </button>
          </div>
        </div>

        {errorMsg ? (
          <Notice tone="danger">
            <div className="ms-col" style={{ gap: 6 }}>
              <span>待选清单加载失败：{errorMsg}</span>
              <button className="ms-link" style={{ background: 'none', border: 'none', alignSelf: 'flex-start' }} onClick={() => shortlist.refetch()}>
                重试
              </button>
            </div>
          </Notice>
        ) : shortlist.isLoading ? (
          <div className="ms-table-wrap">
            <div className="ms-row" style={{ gap: 12, padding: '0 12px', height: 42, background: 'var(--bg-subtle)' }}>
              {[0, 1, 2, 3, 4, 5, 6, 7].map((i) => (
                <Skeleton key={i} height={12} width={i === 1 ? 140 : 80} />
              ))}
            </div>
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="ms-row" style={{ gap: 12, padding: '0 12px', height: 52, borderBottom: '1px solid var(--border-row)' }}>
                <Skeleton height={12} width={120} />
                <Skeleton height={12} width={70} />
                <Skeleton height={12} width={70} />
                <Skeleton height={12} width={90} />
                <Skeleton height={12} width={80} />
                <Skeleton height={12} width={80} />
              </div>
            ))}
          </div>
        ) : items.length === 0 ? (
          <EmptyState
            icon="layers"
            title="待选还是空的"
            desc="回到任务会话，从推荐结果点击「+ 加入待选」收集候选材料"
            action={
              <button className="ms-btn ms-btn--primary" onClick={() => navigate(`/tasks/${taskId}`)}>
                返回选型工作台
              </button>
            }
          />
        ) : (
          <>
            <div className="ms-table-wrap">
              <table className="ms-table ms-compare-page">
                <thead>
                  <tr>
                    <th style={{ width: 24 }} aria-label="拖拽排序" />
                    <th style={{ width: 180 }}>材料名称</th>
                    <th style={{ width: 76 }}>匹配度</th>
                    <th style={{ width: 80 }}>密度 g/cm³</th>
                    <th style={{ width: 110 }}>拉伸强度 MPa</th>
                    <th style={{ width: 96 }}>耐温上限 °C</th>
                    <th style={{ width: 104 }}>参考价 元/kg</th>
                    <th style={{ width: 100 }}>标记</th>
                    <th style={{ width: 290 }}>备注（自动保存）</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((it, i) => (
                    <CompareRow
                      key={it.id}
                      item={it}
                      index={i}
                      dragging={dragIndex === i}
                      newItem={newIds.includes(it.id)}
                      onDragStart={() => setDragIndex(i)}
                      onDragOver={(e) => e.preventDefault()}
                      onDrop={() => {
                        if (dragIndex !== null) move(dragIndex, i)
                        setDragIndex(null)
                      }}
                      onDragEnd={() => setDragIndex(null)}
                      onNoteChange={(note) => update.mutate({ id: it.id, body: { user_note: note } })}
                      onTagChange={(tag) => update.mutate({ id: it.id, body: { tag } })}
                    />
                  ))}
                </tbody>
              </table>
              <div className="ms-compare-foot">
                <span>
                  标记统计：重点考虑 {stats.key} · 待验证 {stats.pending} · 已淘汰 {stats.rejected}
                </span>
                <span style={{ display: 'flex', gap: 'var(--sp-4)', alignItems: 'center' }}>
                  <span className="ms-muted-aa">拖拽行首可调整顺序 · 备注改动即时保存</span>
                  <button
                    className="ms-link"
                    style={{ background: 'none', border: 'none' }}
                    onClick={() => {
                      const last = items[items.length - 1]
                      if (last) remove.mutate(last.id)
                    }}
                  >
                    移出最后一项
                  </button>
                </span>
              </div>
            </div>

            <Notice tone="info">
              待选清单是个人工作态数据：不写入材料主库、不参与推荐排序；导出材料包时默认不含本清单
              （可在数据分享页勾选「包含我的工作数据」）。标记含义：{TAG_LABEL.key} / {TAG_LABEL.pending} / {TAG_LABEL.rejected}。
            </Notice>
          </>
        )}
      </main>
    </>
  )
}
