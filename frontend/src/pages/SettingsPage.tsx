import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import type { CategoryNode } from '../api/types'
import { WeightSlider } from '../components/WeightSlider'
import { Notice } from '../components/Notice'
import { EmptyState } from '../components/EmptyState'
import { Skeleton } from '../components/Skeleton'
import { Icon } from '../icons'
import { PromptDialog } from '../components/PromptDialog'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { toast, ToastHost } from '../components/Toast'
import { formatTime } from '../utils/format'
import './pages.css'

/** 10 · 设置（原型 02 §10）
 *  Tab：分类体系 / 推荐权重 / 反馈与知识盲区 / 操作日志 · 备份
 *  权重口径为百分制，保存时后端自动归一化到 Σ=100。 */

const TABS = [
  { key: 'weights', label: '推荐权重' },
  { key: 'categories', label: '分类体系' },
  { key: 'insights', label: '反馈与知识盲区' },
  { key: 'logs', label: '操作日志 / 备份' },
] as const

type TabKey = (typeof TABS)[number]['key']

export default function SettingsPage() {
  const qc = useQueryClient()
  const [tab, setTab] = useState<TabKey>('weights')
  const [draft, setDraft] = useState<Record<string, number>>({})
  const [newCatName, setNewCatName] = useState('')
  const [gapRange, setGapRange] = useState<'week' | 'month' | 'all'>('week')
  // 破坏性 / 需输入的操作统一走自定义弹窗（不使用 window.prompt / confirm）
  const [renameTarget, setRenameTarget] = useState<{ id: number; name: string } | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<{ id: number; name: string } | null>(null)
  const [resetConfirmOpen, setResetConfirmOpen] = useState(false)
  const [clearConfirmOpen, setClearConfirmOpen] = useState(false)

  const weights = useQuery({ queryKey: ['weights'], queryFn: () => api.getWeights(), staleTime: 30_000 })
  const categories = useQuery({ queryKey: ['categories'], queryFn: () => api.listCategories(), staleTime: 60_000 })
  const gaps = useQuery({ queryKey: ['gaps', gapRange], queryFn: () => api.listGaps(gapRange), staleTime: 30_000 })
  const myFeedback = useQuery({ queryKey: ['my-feedback'], queryFn: () => api.listMyFeedback(), staleTime: 30_000 })
  const logs = useQuery({ queryKey: ['logs', 50], queryFn: () => api.listLogs(50), staleTime: 15_000 })
  const backup = useQuery({ queryKey: ['backup-status'], queryFn: () => api.backupStatus(), staleTime: 30_000 })

  // 服务端权重就绪后初始化草稿（用户改动只存在 draft 里，直到「保存配置」）
  useEffect(() => {
    if (weights.data?.dims) {
      setDraft(Object.fromEntries(weights.data.dims.map((d) => [d.key, d.weight])))
    }
  }, [weights.data])

  const sum = useMemo(() => Object.values(draft).reduce((a, b) => a + b, 0), [draft])
  const dirty = useMemo(() => {
    if (!weights.data?.dims) return false
    return weights.data.dims.some((d) => Math.abs((draft[d.key] ?? 0) - d.weight) > 1e-6)
  }, [draft, weights.data])

  const saveWeights = useMutation({
    mutationFn: () =>
      api.saveWeights({
        dims: Object.entries(draft).map(([key, weight]) => ({ key, weight })),
        penalty: weights.data?.penalty,
      }),
    onSuccess: (data) => {
      toast(`配置已保存（权重已自动归一化，合计 ${data.sum}%）`, 'success')
      qc.invalidateQueries({ queryKey: ['weights'] })
    },
    onError: (e) => toast(e instanceof Error ? e.message : '保存失败', 'danger'),
  })

  const resetWeights = () => {
    if (!weights.data?.dims) return
    // 恢复默认：把草稿重置为后端当前默认（后端 DEFAULT_WEIGHTS 归一化后的百分制）
    const fallback: Record<string, number> = {}
    weights.data.dims.forEach((d) => {
      fallback[d.key] = Math.round(({ temp: 30, semantic: 25, cost: 20, mechanics: 15, process: 10 } as Record<string, number>)[d.key] ?? d.weight)
    })
    setDraft(fallback)
    toast('已恢复默认权重，点「保存配置」后生效', 'default')
  }

  const addCategory = useMutation({
    mutationFn: (name: string) => api.createCategory({ name }),
    onSuccess: () => {
      toast('分类已新增', 'success')
      setNewCatName('')
      qc.invalidateQueries({ queryKey: ['categories'] })
    },
    onError: (e) => toast(e instanceof Error ? e.message : '新增失败', 'danger'),
  })

  const renameCategory = useMutation({
    mutationFn: (v: { id: number; name: string }) => api.renameCategory(v.id, v.name),
    onSuccess: () => {
      toast('分类已重命名', 'success')
      qc.invalidateQueries({ queryKey: ['categories'] })
    },
    onError: (e) => toast(e instanceof Error ? e.message : '重命名失败', 'danger'),
  })

  const deleteCategory = useMutation({
    mutationFn: (id: number) => api.deleteCategory(id),
    onSuccess: () => {
      toast('分类已删除', 'success')
      qc.invalidateQueries({ queryKey: ['categories'] })
    },
    onError: (e) => toast(e instanceof Error ? e.message : '删除失败', 'danger'),
  })

  const clearFeedback = useMutation({
    mutationFn: () => api.clearMyFeedback(),
    onSuccess: () => {
      toast('已清空我的反馈', 'success')
      qc.invalidateQueries({ queryKey: ['my-feedback'] })
      qc.invalidateQueries({ queryKey: ['gaps'] })
    },
  })

  const runBackup = useMutation({
    mutationFn: () => api.runBackup(),
    onSuccess: (r) => {
      toast(`已备份：${r.location}`, 'success')
      qc.invalidateQueries({ queryKey: ['backup-status'] })
      qc.invalidateQueries({ queryKey: ['logs'] })
    },
    onError: () => toast('备份失败，请重试', 'danger'),
  })

  const exportGaps = () => {
    const rows = gaps.data?.items ?? []
    const md = [
      '# 知识盲区报告',
      '',
      `范围：${gapRange === 'week' ? '近一周' : gapRange === 'month' ? '近一月' : '全部'}`,
      '',
      '| 缺口维度 | 失败次数 | 建议动作 |',
      '| --- | --- | --- |',
      ...rows.map((g) => `| ${g.dimension} | ${g.count} | ${g.suggestion} |`),
    ].join('\n')
    navigator.clipboard
      .writeText(md)
      .then(() => toast('盲区报告已复制为 Markdown', 'success'))
      .catch(() => toast('复制失败，请检查浏览器权限', 'danger'))
  }

  const roots: CategoryNode[] = categories.data?.items ?? []

  return (
    <>
      <ToastHost />
      <main className="ms-main">
        <div className="ms-page-header">
          <div>
            <h1 className="ms-page-header__title">设置</h1>
            <div className="ms-page-header__sub">
              权重与阈值配置化 · 单机单人，不记录「谁」，仅记录时间与操作类型
            </div>
          </div>
        </div>

        <div className="ms-tabs" role="tablist" aria-label="设置分组">
          {TABS.map((t) => (
            <button
              key={t.key}
              role="tab"
              aria-selected={tab === t.key}
              className={`ms-tab${tab === t.key ? ' ms-tab--active' : ''}`}
              onClick={() => setTab(t.key)}
            >
              {t.label}
            </button>
          ))}
        </div>

        {tab === 'weights' && (
          <div className="ms-settings">
            <div className="ms-settings__main">
              <div className="ms-card">
                <div className="ms-card__title">推荐权重（匹配度分数的构成）</div>
                {weights.isLoading ? (
                  <div className="ms-col" style={{ gap: 'var(--sp-6)' }}>
                    {[0, 1, 2, 3, 4].map((i) => (
                      <div key={i} className="ms-col" style={{ gap: 8 }}>
                        <Skeleton height={14} width="45%" />
                        <Skeleton height={8} />
                      </div>
                    ))}
                  </div>
                ) : weights.isError ? (
                  <Notice tone="danger">
                    <div className="ms-col" style={{ gap: 6 }}>
                      <span>权重配置加载失败</span>
                      <button className="ms-link" style={{ background: 'none', border: 'none', alignSelf: 'flex-start' }} onClick={() => weights.refetch()}>
                        重试
                      </button>
                    </div>
                  </Notice>
                ) : (
                  <div className="ms-col" style={{ gap: 'var(--sp-6)' }}>
                    {(weights.data?.dims ?? []).map((d) => (
                      <WeightSlider
                        key={d.key}
                        label={d.label}
                        hint={d.hint}
                        value={draft[d.key] ?? d.weight}
                        onChange={(v) => setDraft((s) => ({ ...s, [d.key]: v }))}
                      />
                    ))}
                    <div className={`ms-weights-sum${Math.abs(sum - 100) > 0.01 ? ' ms-weights-sum--warn' : ''}`}>
                      权重合计 {sum.toFixed(0)}%（{Math.abs(sum - 100) > 0.01 ? '保存时将自动归一化' : '已归一化'}） · 反馈降权：
                      同维度负面达 {weights.data?.penalty.threshold ?? 2} 次后生效，单次最高扣 {weights.data?.penalty.max ?? 15} 分，
                      软降权（材料仍保留在列表中并标注「因历史反馈降分」）
                    </div>
                    <div className="ms-row" style={{ justifyContent: 'flex-end', gap: 'var(--sp-4)' }}>
                      <button className="ms-btn ms-btn--ghost" onClick={() => setResetConfirmOpen(true)}>
                        恢复默认权重
                      </button>
                      <button className="ms-btn ms-btn--primary" disabled={!dirty || saveWeights.isPending} onClick={() => saveWeights.mutate()}>
                        {saveWeights.isPending && <span className="ms-spin" style={{ color: '#fff' }} />}
                        保存配置
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>

            <div className="ms-settings__side">
              <div className="ms-card">
                <div className="ms-card__title">配置说明</div>
                <div className="ms-col" style={{ gap: 'var(--sp-4)', fontSize: 'var(--fs-small)', color: 'var(--text-3)', lineHeight: 17 }}>
                  <span>· 硬约束（耐温上限、成型工艺）<strong>不参与打分</strong>，在打分前直接过滤，绝不越界。</span>
                  <span>· 语义相似度仅在硬约束过滤后的候选集内计算。</span>
                  <span>· 成本敏感时自动提高成本维度权重（追问「再便宜点」即触发）。</span>
                  <span>· 单条负面反馈只提示、不降权；达阈值才软降权，幅度可配置。</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {tab === 'categories' && (
          <div className="ms-settings">
            <div className="ms-settings__main">
              <div className="ms-card">
                <div className="ms-card__title">分类体系（两级）</div>
                {categories.isLoading ? (
                  <div className="ms-col" style={{ gap: 8 }}>
                    {[0, 1, 2].map((i) => (
                      <Skeleton key={i} height={22} />
                    ))}
                  </div>
                ) : categories.isError ? (
                  <Notice tone="danger">
                    <div className="ms-col" style={{ gap: 6 }}>
                      <span>分类加载失败</span>
                      <button className="ms-link" style={{ background: 'none', border: 'none', alignSelf: 'flex-start' }} onClick={() => categories.refetch()}>
                        重试
                      </button>
                    </div>
                  </Notice>
                ) : roots.length === 0 ? (
                  <EmptyState
                    icon="layers"
                    title="暂无分类"
                    desc="在下方输入名称创建第一个一级分类"
                  />
                ) : (
                  <div className="ms-cols-2" style={{ gap: 'var(--sp-8)' }}>
                    {roots.map((n) => (
                      <div key={n.id} className="ms-col" style={{ gap: 4 }}>
                        <div className="ms-row ms-gap-3" style={{ height: 30 }}>
                          <span style={{ fontSize: 'var(--fs-body)', fontWeight: 'var(--fw-medium)' }}>{n.name}</span>
                          <span className="ms-tree-row__count">{n.count}</span>
                          <button
                            className="ms-icon-btn"
                            title="重命名"
                            aria-label={`重命名分类 ${n.name}`}
                            onClick={() => setRenameTarget({ id: n.id, name: n.name })}
                          >
                            <Icon name="edit" size={13} />
                          </button>
                          <button
                            className="ms-icon-btn ms-icon-btn--danger"
                            title="删除"
                            aria-label={`删除分类 ${n.name}`}
                            onClick={() => setDeleteTarget({ id: n.id, name: n.name })}
                          >
                            <Icon name="trash" size={13} />
                          </button>
                        </div>
                        {(n.children ?? []).map((c) => (
                          <div key={c.id} className="ms-row ms-gap-3" style={{ height: 30, paddingLeft: 16 }}>
                            <span style={{ fontSize: 'var(--fs-small)', color: 'var(--text-2)' }}>{c.name}</span>
                            <span className="ms-tree-row__count">{c.count}</span>
                            <button
                              className="ms-icon-btn"
                              title="重命名"
                              aria-label={`重命名分类 ${c.name}`}
                              onClick={() => setRenameTarget({ id: c.id, name: c.name })}
                            >
                              <Icon name="edit" size={13} />
                            </button>
                            <button
                              className="ms-icon-btn ms-icon-btn--danger"
                              title="删除"
                              aria-label={`删除分类 ${c.name}`}
                              onClick={() => setDeleteTarget({ id: c.id, name: c.name })}
                            >
                              <Icon name="trash" size={13} />
                            </button>
                          </div>
                        ))}
                      </div>
                    ))}
                  </div>
                )}

                <div className="ms-row ms-gap-4" style={{ marginTop: 'var(--sp-8)' }}>
                  <input
                    className="ms-field"
                    style={{ flex: 1 }}
                    placeholder="输入一级分类名称，例如「热塑性塑料」"
                    aria-label="新增分类名称"
                    value={newCatName}
                    onChange={(e) => setNewCatName(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && newCatName.trim()) addCategory.mutate(newCatName.trim())
                    }}
                  />
                  <button
                    className="ms-btn ms-btn--secondary"
                    disabled={!newCatName.trim() || addCategory.isPending}
                    onClick={() => addCategory.mutate(newCatName.trim())}
                  >
                    <Icon name="plus" size={14} />
                    新增分类
                  </button>
                </div>
                <div style={{ marginTop: 'var(--sp-4)' }}>
                  <Notice tone="warning">
                    删除分类前需先移走该分类下的材料（有引用时后端会拒绝并提示）；删除一级分类会将其子类提升为顶级。
                  </Notice>
                </div>
              </div>
            </div>
            <div className="ms-settings__side">
              <div className="ms-card">
                <div className="ms-card__title">分类约定</div>
                <div className="col" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-4)', fontSize: 'var(--fs-small)', color: 'var(--text-3)', lineHeight: 17 }}>
                  <span>· 两级结构：大类（热塑性塑料 / 热固性塑料 / 金属 / 弹性体 / 复合材料）+ 子类。</span>
                  <span>· 材料归属到<strong>子类</strong>；面包屑按「大类 / 子类」展示。</span>
                  <span>· 计数为该子类下<strong>未归档</strong>材料条数。</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {tab === 'insights' && (
          <div className="ms-settings">
            <div className="ms-settings__main">
              <div className="ms-card">
                <div className="ms-card__title">
                  <span>知识盲区报告</span>
                  <div className="ms-row ms-gap-3">
                    {(['week', 'month', 'all'] as const).map((r) => (
                      <button
                        key={r}
                        className={`ms-segmented__item${gapRange === r ? ' ms-segmented__item--active' : ''}`}
                        onClick={() => setGapRange(r)}
                      >
                        {r === 'week' ? '近一周' : r === 'month' ? '近一月' : '全部'}
                      </button>
                    ))}
                  </div>
                </div>
                {gaps.isError ? (
                  <Notice tone="danger">
                    <div className="ms-col" style={{ gap: 6 }}>
                      <span>盲区数据加载失败：{gaps.error instanceof Error ? gaps.error.message : '未知错误'}</span>
                      <button
                        className="ms-link"
                        style={{ background: 'none', border: 'none', alignSelf: 'flex-start' }}
                        onClick={() => gaps.refetch()}
                      >
                        重试
                      </button>
                    </div>
                  </Notice>
                ) : gaps.isLoading ? (
                  <Skeleton height={60} />
                ) : (gaps.data?.items ?? []).length === 0 ? (
                  <EmptyState icon="shield" title="本周没有失败回评" desc="说明推荐质量稳定；回评失败会在这里沉淀为可补的数据缺口" compact />
                ) : (
                  <table className="ms-table">
                    <thead>
                      <tr>
                        <th>缺口维度</th>
                        <th style={{ width: 100 }}>失败次数</th>
                        <th>建议动作</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(gaps.data?.items ?? []).map((g) => (
                        <tr key={g.dimension}>
                          <td className="is-name">{g.dimension}</td>
                          <td className="is-mono">{g.count}</td>
                          <td>{g.suggestion}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
                <div className="ms-row" style={{ justifyContent: 'flex-end', marginTop: 'var(--sp-6)' }}>
                  <button className="ms-btn ms-btn--ghost" onClick={exportGaps} disabled={(gaps.data?.items ?? []).length === 0}>
                    <Icon name="download" size={14} />
                    导出盲区报告
                  </button>
                </div>
              </div>
            </div>

            <div className="ms-settings__side">
              <div className="ms-card">
                <div className="ms-card__title">我的负面反馈（可清空）</div>
                {myFeedback.isLoading ? (
                  <Skeleton height={48} />
                ) : (myFeedback.data?.items ?? []).length === 0 ? (
                  <span className="ms-muted-aa" style={{ fontSize: 'var(--fs-small)' }}>还没有负面反馈记录</span>
                ) : (
                  <div className="ms-col" style={{ gap: 'var(--sp-4)' }}>
                    {(myFeedback.data?.items ?? []).map((f, i) => (
                      <div key={i} className="ms-col" style={{ gap: 2 }}>
                        <span style={{ fontSize: 'var(--fs-small)', color: 'var(--text-2)' }}>
                          {f.material_name} · {f.dimension}
                        </span>
                        <span className="ms-mono ms-muted-aa" style={{ fontSize: 'var(--fs-caption)' }}>
                          命中 {f.hit_count} 次 · {f.active ? '生效中' : '已停用'}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
                <div className="ms-row" style={{ justifyContent: 'flex-end', marginTop: 'var(--sp-6)' }}>
                  <button className="ms-btn ms-btn--danger" disabled={clearFeedback.isPending} onClick={() => setClearConfirmOpen(true)}>
                    <Icon name="trash" size={14} />
                    清空我的反馈
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {tab === 'logs' && (
          <div className="ms-settings">
            <div className="ms-settings__main">
              <div className="ms-card">
                <div className="ms-card__title">
                  <span>操作日志（单机不记录账号，仅记时间与操作）</span>
                  <button className="ms-btn ms-btn--ghost" onClick={() => logs.refetch()}>
                    <Icon name="refresh" size={14} />
                    刷新
                  </button>
                </div>
                {logs.isLoading ? (
                  <div className="ms-col" style={{ gap: 6 }}>
                    {[0, 1, 2, 3, 4].map((i) => (
                      <Skeleton key={i} height={14} />
                    ))}
                  </div>
                ) : logs.isError ? (
                  <Notice tone="danger">
                    <div className="ms-col" style={{ gap: 6 }}>
                      <span>日志加载失败</span>
                      <button className="ms-link" style={{ background: 'none', border: 'none', alignSelf: 'flex-start' }} onClick={() => logs.refetch()}>
                        重试
                      </button>
                    </div>
                  </Notice>
                ) : (logs.data?.items ?? []).length === 0 ? (
                  <span className="ms-muted-aa" style={{ fontSize: 'var(--fs-small)' }}>还没有操作记录</span>
                ) : (
                  <div className="ms-col" style={{ gap: 6 }}>
                    {(logs.data?.items ?? []).map((l, i) => (
                      <div key={i} className="ms-row ms-gap-4" style={{ fontSize: 'var(--fs-small)' }}>
                        <span className="ms-mono ms-muted" style={{ width: 140 }}>{formatTime(l.at, true)}</span>
                        <span style={{ width: 80, color: 'var(--text-2)' }}>{l.action}</span>
                        <span className="ms-mono ms-ellipsis" style={{ flex: 1 }}>{l.target}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            <div className="ms-settings__side">
              <div className="ms-card">
                <div className="ms-card__title">数据备份</div>
                <div className="ms-col" style={{ gap: 'var(--sp-4)' }}>
                  <div className="ms-info-block">
                    <span className="ms-mono" style={{ fontSize: 'var(--fs-small)', color: 'var(--text-3)' }}>
                      {backup.data?.last_backup_at
                        ? `上次备份：${formatTime(backup.data.last_backup_at, true)}`
                        : '本机数据尚未备份'}
                    </span>
                  </div>
                  <span className="ms-muted-aa" style={{ fontSize: 'var(--fs-caption)', lineHeight: 15 }}>
                    备份位置：{backup.data?.location ?? '—'}
                  </span>
                  <button className="ms-btn ms-btn--primary" disabled={runBackup.isPending} onClick={() => runBackup.mutate()}>
                    <Icon name="database" size={14} />
                    立即备份
                  </button>
                  <Notice tone="warning">
                    数据即本机单个 SQLite 文件；建议定期备份 + 导出材料包作为冷备份。
                  </Notice>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* 重命名分类（原型 03 §3.7：自定义输入弹窗，替代 window.prompt） */}
      <PromptDialog
        open={renameTarget != null}
        title="重命名分类"
        label="分类名称"
        defaultValue={renameTarget?.name ?? ''}
        confirmText="保存"
        pending={renameCategory.isPending}
        validate={(v) => (v.trim() === '' ? '分类名称不能为空' : null)}
        onCancel={() => setRenameTarget(null)}
        onSubmit={(v) => {
          const name = v.trim()
          if (renameTarget && name !== renameTarget.name) renameCategory.mutate({ id: renameTarget.id, name })
          setRenameTarget(null)
        }}
      />

      {/* 删除分类：破坏性操作需二次确认（05 §1.2） */}
      <ConfirmDialog
        open={deleteTarget != null}
        title="删除分类"
        tone="danger"
        confirmText="删除"
        pending={deleteCategory.isPending}
        note="该分类下仍有材料时后端会拒绝删除"
        onCancel={() => setDeleteTarget(null)}
        onConfirm={() => {
          if (deleteTarget) deleteCategory.mutate(deleteTarget.id)
          setDeleteTarget(null)
        }}
      >
        <span>确认删除分类「{deleteTarget?.name}」？删除一级分类会将其子类提升为顶级。</span>
      </ConfirmDialog>

      {/* 恢复默认权重：会覆盖当前草稿（02 §10） */}
      <ConfirmDialog
        open={resetConfirmOpen}
        title="恢复默认权重"
        confirmText="恢复默认"
        note="需再点「保存配置」才会写入后端"
        onCancel={() => setResetConfirmOpen(false)}
        onConfirm={() => {
          resetWeights()
          setResetConfirmOpen(false)
        }}
      >
        <span>将把五个维度的权重重置为默认值：温度 30 / 语义 25 / 成本 20 / 力学 15 / 工艺 10。</span>
      </ConfirmDialog>

      {/* 清空我的反馈：不可撤销 */}
      <ConfirmDialog
        open={clearConfirmOpen}
        title="清空我的反馈"
        tone="danger"
        confirmText="清空"
        pending={clearFeedback.isPending}
        note="此操作不可撤销"
        onCancel={() => setClearConfirmOpen(false)}
        onConfirm={() => {
          clearFeedback.mutate()
          setClearConfirmOpen(false)
        }}
      >
        <span>将删除本机全部负面反馈记录，已生效的软降权会一并解除且无法恢复。</span>
      </ConfirmDialog>
    </>
  )
}
