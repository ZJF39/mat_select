import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import type { MaterialDetail } from '../api/types'
import { SidePanel } from '../layout/SidePanel'
import { CategoryTree } from '../components/CategoryTree'
import { ParamRow } from '../components/ParamRow'
import { Chip } from '../components/Chip'
import { Notice } from '../components/Notice'
import { EmptyState } from '../components/EmptyState'
import { Modal } from '../components/Modal'
import { Skeleton, SkeletonTreeRow } from '../components/Skeleton'
import { Icon } from '../icons'
import { formatPrice, formatRange, formatTime } from '../utils/format'
import { toast, ToastHost } from '../components/Toast'
import './pages.css'

/** 03 材料详情页（原型 02 §03） */

const VALUE_TYPE_LABEL: Record<string, string> = { typical: '典型值', guaranteed: '保证值' }

export default function MaterialDetailPage() {
  const { uid = '' } = useParams()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [pickerOpen, setPickerOpen] = useState(false)
  const [addedTask, setAddedTask] = useState<number | null>(null)

  const material = useQuery({
    queryKey: ['material', uid],
    queryFn: () => api.getMaterial(uid),
    enabled: !!uid,
    staleTime: 30_000,
  })

  const categories = useQuery({
    queryKey: ['categories'],
    queryFn: () => api.listCategories(),
    staleTime: 60_000,
  })

  const tasks = useQuery({
    queryKey: ['tasks', 'picker'],
    queryFn: () => api.listTasks({ status: 'active' }),
    staleTime: 30_000,
  })

  const add = useMutation({
    mutationFn: (taskId: number) => api.addShortlist(taskId, uid),
    onSuccess: (_r, taskId) => {
      setAddedTask(taskId)
      setPickerOpen(false)
      toast('已加入待选', 'success')
      qc.invalidateQueries({ queryKey: ['shortlist', taskId] })
      qc.invalidateQueries({ queryKey: ['tasks'] })
    },
    onError: (e) => toast(e instanceof Error ? e.message : '加入待选失败', 'danger'),
  })

  const m: MaterialDetail | undefined = material.data
  const notFound = material.isError && (material.error as { status?: number })?.status === 404

  return (
    <>
      <ToastHost />
      <SidePanel
        title="材料分类"
        sub="点击浏览同类材料"
        foot={<span>在当前材料所属分类下浏览，便于横向比较同类牌号。</span>}
      >
        {categories.isError ? (
          <Notice tone="danger">
            <div className="ms-col" style={{ gap: 6 }}>
              <span>分类加载失败</span>
              <button className="ms-link" style={{ background: 'none', border: 'none', alignSelf: 'flex-start' }} onClick={() => categories.refetch()}>
                重试
              </button>
            </div>
          </Notice>
        ) : categories.isLoading ? (
          <>
            <SkeletonTreeRow />
            <SkeletonTreeRow />
            <SkeletonTreeRow />
          </>
        ) : (
          <CategoryTree
            nodes={categories.data?.items ?? []}
            selectedId={m?.category_id ?? null}
            onSelect={(id) => navigate(id == null ? '/materials' : `/materials?cat=${id}`)}
          />
        )}
      </SidePanel>

      <main className="ms-main">
        {notFound ? (
          <EmptyState
            icon="search"
            title="材料不存在"
            desc={`没有找到 uid 为「${uid}」的材料，它可能已被删除或改名。`}
            action={
              <button className="ms-btn ms-btn--primary" onClick={() => navigate('/materials')}>
                <Icon name="layers" size={14} />
                返回材料库
              </button>
            }
          />
        ) : material.isError ? (
          <Notice tone="danger">
            <div className="ms-col" style={{ gap: 6 }}>
              <span>材料详情加载失败：{material.error instanceof Error ? material.error.message : '未知错误'}</span>
              <button className="ms-link" style={{ background: 'none', border: 'none', alignSelf: 'flex-start' }} onClick={() => material.refetch()}>
                重试
              </button>
            </div>
          </Notice>
        ) : material.isLoading || !m ? (
          <div className="ms-detail">
            <div className="ms-detail__main">
              <div className="ms-card" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                <Skeleton height={22} width="42%" />
                <Skeleton height={14} width="28%" />
                <Skeleton height={12} width="60%" />
              </div>
              <div className="ms-card" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                <Skeleton height={16} width="30%" />
                <Skeleton height={12} />
                <Skeleton height={12} />
                <Skeleton height={12} />
              </div>
            </div>
            <div className="ms-detail__side">
              <div className="ms-card"><Skeleton height={16} width="50%" /></div>
              <div className="ms-card"><Skeleton height={16} width="50%" /></div>
            </div>
          </div>
        ) : (
          <>
            <div className="ms-crumbs">
              <Link to="/materials">材料库</Link>
              {(m.category_path ?? []).map((p) => (
                <span key={p}> / {p}</span>
              ))}
              <span> / {m.name}</span>
            </div>

            <div className="ms-card ms-headcard">
              <div className="ms-headcard__title">
                <div style={{ minWidth: 0 }}>
                  <div className="ms-headcard__name">{m.name}</div>
                  <div className="ms-headcard__alias">
                    {m.aliases?.length ? m.aliases.join('、') : '—'}
                    <span className="ms-mono" style={{ marginLeft: 8, color: 'var(--text-7)' }}>
                      #{m.uid.slice(-6)}
                    </span>
                  </div>
                </div>
                {m.category_name && (
                  <Chip size="24" tone="accent">
                    {m.category_name}
                  </Chip>
                )}
                <div className="ms-headcard__actions">
                  {addedTask != null ? (
                    <button className="ms-btn ms-btn--primary" onClick={() => navigate(`/tasks/${addedTask}/shortlist`)}>
                      已加入 · 查看待选
                    </button>
                  ) : (
                    <button className="ms-btn ms-btn--primary" onClick={() => setPickerOpen(true)} disabled={add.isPending}>
                      <Icon name="plus" size={14} />
                      加入待选
                    </button>
                  )}
                  <button className="ms-btn ms-btn--secondary" onClick={() => navigate(`/materials/${m.uid}/edit`)}>
                    编辑材料
                  </button>
                  <button className="ms-btn ms-btn--ghost" onClick={() => navigate(`/materials/${m.uid}/history`)}>
                    查看变更历史
                  </button>
                </div>
              </div>
              <div className="ms-headcard__meta">
                <span>来源 · {m.source ?? '—'}</span>
                <span className="ms-mono">最后更新 · {formatTime(m.updated_at, true)}</span>
                <span>参数类型 · {VALUE_TYPE_LABEL[m.value_type] ?? '典型值'}</span>
              </div>
            </div>

            <div className="ms-detail">
              <div className="ms-detail__main">
                <div className="ms-card">
                  <div className="ms-card__title">关键参数与性能</div>
                  {/* 力学 / 热学两组，中间竖向分隔线；组内每行「名称 | 数值+单位」，行间浅色细线 */}
                  <div className="ms-detail__two ms-params">
                    <section className="ms-param-group">
                      <div className="ms-param-group__title">力学参数</div>
                      <div className="ms-param-list">
                        <ParamRow label="密度" unit="g/cm³" value={formatRange(m.density_min, m.density_max)} empty={m.density_min == null && m.density_max == null} />
                        <ParamRow label="拉伸强度" unit="MPa" value={formatRange(m.tensile_strength_min, m.tensile_strength_max)} empty={m.tensile_strength_min == null && m.tensile_strength_max == null} />
                        <ParamRow label="弹性模量" unit="GPa" value={formatRange(m.elastic_modulus_min, m.elastic_modulus_max)} empty={m.elastic_modulus_min == null && m.elastic_modulus_max == null} />
                        <ParamRow label="断裂伸长率" unit="%" value={formatRange(m.elongation_min, m.elongation_max)} empty={m.elongation_min == null && m.elongation_max == null} />
                        <ParamRow label="缺口冲击强度" unit="kJ/m²" value={formatRange(m.notch_impact_min, m.notch_impact_max)} empty={m.notch_impact_min == null && m.notch_impact_max == null} />
                      </div>
                    </section>
                    <section className="ms-param-group">
                      <div className="ms-param-group__title">热学参数</div>
                      <div className="ms-param-list">
                        <ParamRow label="热变形温度 HDT" unit="°C" value={formatRange(m.hdt_min, m.hdt_max, 'temp')} empty={m.hdt_min == null && m.hdt_max == null} />
                        <ParamRow label="长期使用温度范围" unit="°C" value={formatRange(m.service_temp_min, m.service_temp_max, 'temp')} empty={m.service_temp_min == null && m.service_temp_max == null} />
                        <ParamRow
                          label="长期使用温度上限"
                          unit="°C"
                          value={m.service_temp_limit == null ? '—' : String(m.service_temp_limit)}
                          empty={m.service_temp_limit == null}
                          emphasis
                        />
                      </div>
                    </section>
                  </div>
                </div>

                <div className="ms-card">
                  <div className="ms-card__title">主要特性与注意项</div>
                  <div className="ms-chips-edit">
                    {(m.features ?? []).length ? (
                      (m.features ?? []).map((f) => (
                        <Chip key={f} size="20">
                          {f}
                        </Chip>
                      ))
                    ) : (
                      <span className="ms-muted">—</span>
                    )}
                  </div>
                  {(m.cautions ?? []).length > 0 && (
                    <div style={{ marginTop: 'var(--sp-6)', display: 'flex', flexDirection: 'column', gap: 'var(--sp-4)' }}>
                      {m.cautions.map((c, i) => (
                        <Notice key={i} tone="warning">
                          {c.type ? `${c.type}：` : ''}
                          {c.content}
                        </Notice>
                      ))}
                    </div>
                  )}
                </div>

                <div className="ms-card">
                  <div className="ms-card__title">典型应用场景</div>
                  <div className="ms-chips-edit">
                    {(m.applications ?? []).length ? (
                      (m.applications ?? []).map((a) => (
                        <Chip key={a} size="20" onClick={() => navigate(`/materials?q=${encodeURIComponent(a)}`)} title="按该场景筛选材料库">
                          {a}
                        </Chip>
                      ))
                    ) : (
                      <span className="ms-muted">—</span>
                    )}
                  </div>
                </div>

                <div className="ms-card">
                  <div className="ms-detail__two">
                    <div>
                      <div className="ms-card__title" style={{ marginBottom: 'var(--sp-4)' }}>
                        认证与合规
                      </div>
                      <div className="ms-chips-edit">
                        {m.certifications?.ul94 && <Chip size="20">UL94 {m.certifications.ul94}</Chip>}
                        {m.certifications?.ul_yellow_card && <Chip size="20">黄卡 {m.certifications.ul_yellow_card}</Chip>}
                        {m.certifications?.rohs != null && <Chip size="20">RoHS {m.certifications.rohs ? '符合' : '未声明'}</Chip>}
                        {m.certifications?.reach != null && <Chip size="20">REACH {m.certifications.reach ? '符合' : '未声明'}</Chip>}
                        {m.certifications?.iatf && <Chip size="20">IATF {m.certifications.iatf}</Chip>}
                        {!m.certifications?.ul94 &&
                          m.certifications?.rohs == null &&
                          !m.certifications?.iatf &&
                          !m.certifications?.ul_yellow_card && <span className="ms-muted">—</span>}
                      </div>
                    </div>
                    <div>
                      <div className="ms-card__title" style={{ marginBottom: 'var(--sp-4)' }}>
                        失效模式 / 不适用场景
                      </div>
                      {(m.limitations ?? []).length ? (
                        <ul style={{ margin: 0, paddingLeft: 16, color: 'var(--text-2)', lineHeight: '20px', fontSize: 'var(--fs-body)' }}>
                          {(m.limitations ?? []).map((l, i) => (
                            <li key={i}>{l}</li>
                          ))}
                        </ul>
                      ) : (
                        <span className="ms-muted">—</span>
                      )}
                    </div>
                  </div>
                </div>
              </div>

              <div className="ms-detail__side">
                <div className="ms-card ms-card--tight">
                  <div className="ms-card__title">价格与工艺</div>
                  <ParamRow label="市场价格参考" value={formatPrice(m.price_min, m.price_max, m.price_unit)} empty={m.price_min == null && m.price_max == null} />
                  <ParamRow label="推荐成型工艺" value={m.molding_process?.[0] ?? '—'} empty={!m.molding_process?.length} mono={false} />
                  <div className="ms-muted" style={{ fontSize: 'var(--fs-caption)', marginTop: 'var(--sp-5)' }}>
                    {m.price_note ?? '* 随原料行情波动，以最新报价为准'}
                  </div>
                </div>

                <div className="ms-card ms-card--tight">
                  <div className="ms-card__title">历史反馈</div>
                  {(m.negative_feedback ?? []).filter((f) => f.active).length > 0 ? (
                    <>
                      <Notice tone="danger">
                        曾被标记「
                        {(m.negative_feedback ?? [])
                          .filter((f) => f.active)
                          .map((f) => f.dimension)
                          .join('、')}
                        」共{' '}
                        {(m.negative_feedback ?? []).filter((f) => f.active).reduce((s, f) => s + f.count, 0)} 次，已在推荐排序中软降权
                      </Notice>
                      <button className="ms-btn ms-btn--ghost ms-btn--sm" style={{ marginTop: 'var(--sp-5)' }} onClick={() => navigate('/settings?tab=feedback')}>
                        管理我的反馈
                      </button>
                    </>
                  ) : (
                    <EmptyState compact icon="check" title="还没有关于这个材料的记录" desc="推荐里标记失败并指向该材料后，这里会出现统计。" />
                  )}
                </div>

                <div className="ms-card ms-card--tight">
                  <div className="ms-card__title">变更记录</div>
                  {(m.recent_revisions ?? []).length ? (
                    <div className="ms-col ms-gap-4">
                      {(m.recent_revisions ?? []).slice(0, 3).map((r, i) => (
                        <div key={i} className="ms-row ms-gap-4" style={{ fontSize: 'var(--fs-small)', color: 'var(--text-3)' }}>
                          <span className="ms-mono" style={{ color: 'var(--text-5)', flex: 'none' }}>
                            {formatTime(r.changed_at)}
                          </span>
                          <span className="ms-ellipsis">{r.summary}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <span className="ms-muted" style={{ fontSize: 'var(--fs-small)' }}>
                      暂无变更记录
                    </span>
                  )}
                  <button className="ms-btn ms-btn--ghost ms-btn--sm" style={{ marginTop: 'var(--sp-5)' }} onClick={() => navigate(`/materials/${m.uid}/history`)}>
                    查看全部变更（Git 式对比）
                  </button>
                </div>
              </div>
            </div>
          </>
        )}
      </main>

      <Modal
        open={pickerOpen}
        title="选择要加入的选型任务"
        width={480}
        onClose={() => setPickerOpen(false)}
        footer={
          <>
            <span className="ms-muted" style={{ fontSize: 'var(--fs-caption)' }}>
              同一任务内同一材料只会入待选一次
            </span>
            <button className="ms-btn ms-btn--ghost" onClick={() => setPickerOpen(false)}>
              取消
            </button>
          </>
        }
      >
        {tasks.isError ? (
          <Notice tone="danger">
            <div className="ms-col" style={{ gap: 6 }}>
              <span>任务列表加载失败</span>
              <button className="ms-link" style={{ background: 'none', border: 'none', alignSelf: 'flex-start' }} onClick={() => tasks.refetch()}>
                重试
              </button>
            </div>
          </Notice>
        ) : tasks.isLoading ? (
          <>
            <Skeleton height={40} />
            <Skeleton height={40} />
          </>
        ) : (tasks.data?.items ?? []).length === 0 ? (
          <div className="ms-col" style={{ gap: 'var(--sp-5)' }}>
            <span className="ms-muted">还没有进行中的选型任务。</span>
            <button
              className="ms-btn ms-btn--primary"
              onClick={async () => {
                try {
                  const t = await api.createTask({ title: `关于 ${m?.name ?? ''} 的选型` })
                  setPickerOpen(false)
                  navigate(`/tasks/${t.id}`)
                } catch (e) {
                  toast(e instanceof Error ? e.message : '新建任务失败', 'danger')
                }
              }}
            >
              <Icon name="plus" size={14} />
              新建选型任务
            </button>
          </div>
        ) : (
          <div className="ms-col ms-gap-3">
            {(tasks.data?.items ?? []).map((t) => (
              <button key={t.id} className="ms-task-item" onClick={() => add.mutate(t.id)} disabled={add.isPending}>
                <span className="ms-task-item__title ms-ellipsis">{t.title}</span>
                <span className="ms-task-item__meta">
                  {t.recommendation_count} 条推荐 · {t.shortlist_count} 待选 · {formatTime(t.updated_at)}
                </span>
              </button>
            ))}
          </div>
        )}
      </Modal>
    </>
  )
}
