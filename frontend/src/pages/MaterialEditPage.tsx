import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import type { Caution, Certification, MaterialUpsert, ValueType } from '../api/types'
import { SidePanel } from '../layout/SidePanel'
import { CategoryTree } from '../components/CategoryTree'
import { Chip } from '../components/Chip'
import { Notice } from '../components/Notice'
import { Skeleton, SkeletonTreeRow } from '../components/Skeleton'
import { Icon } from '../icons'
import { toast, ToastHost } from '../components/Toast'
import './pages.css'

/** 07 材料编辑表单（新建 /materials/new · 编辑 /materials/:uid/edit，原型 02 §07） */

const SECTIONS: { id: string; label: string }[] = [
  { id: 'basic', label: '基本信息' },
  { id: 'mech', label: '力学参数' },
  { id: 'thermal', label: '热学参数' },
  { id: 'risks', label: '特性与风险' },
  { id: 'apps', label: '应用与成本' },
  { id: 'cert', label: '认证与合规' },
  { id: 'source', label: '数据来源与版本' },
]

const RANGES: { key: string; label: string; unit: string }[] = [
  { key: 'density', label: '密度', unit: 'g/cm³' },
  { key: 'tensile_strength', label: '拉伸强度', unit: 'MPa' },
  { key: 'elastic_modulus', label: '弹性模量', unit: 'GPa' },
  { key: 'elongation', label: '断裂伸长率', unit: '%' },
  { key: 'notch_impact', label: '缺口冲击强度', unit: 'kJ/m²' },
]

const THERMAL: { key: string; label: string; unit: string }[] = [
  { key: 'hdt', label: '热变形温度 HDT', unit: '°C' },
  { key: 'service_temp', label: '长期使用温度范围', unit: '°C' },
]

const DRAFT_KEY = (uid: string | undefined) => `matselect:draft:${uid ?? 'new'}`

type FormState = MaterialUpsert

export default function MaterialEditPage() {
  const { uid } = useParams()
  const isEdit = !!uid
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [form, setForm] = useState<FormState>({ name: '' })
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [active, setActive] = useState('basic')
  const [dirty, setDirty] = useState(false)
  const [draftFound, setDraftFound] = useState(false)
  const sectionRefs = useRef<Record<string, HTMLElement | null>>({})
  const loadedRef = useRef(false)

  const material = useQuery({
    queryKey: ['material', uid],
    queryFn: () => api.getMaterial(uid!),
    enabled: isEdit,
    staleTime: 30_000,
  })

  const categories = useQuery({
    queryKey: ['categories'],
    queryFn: () => api.listCategories(),
    staleTime: 60_000,
  })

  /* 载入已有材料 */
  useEffect(() => {
    if (!isEdit || loadedRef.current || !material.data) return
    const m = material.data
    loadedRef.current = true
    setForm({
      name: m.name,
      short_name: m.short_name,
      category_id: m.category_id,
      grade_type: m.grade_type,
      aliases: m.aliases ?? [],
      description: m.description,
      density_min: m.density_min,
      density_max: m.density_max,
      tensile_strength_min: m.tensile_strength_min,
      tensile_strength_max: m.tensile_strength_max,
      elastic_modulus_min: m.elastic_modulus_min,
      elastic_modulus_max: m.elastic_modulus_max,
      elongation_min: m.elongation_min,
      elongation_max: m.elongation_max,
      notch_impact_min: m.notch_impact_min,
      notch_impact_max: m.notch_impact_max,
      hdt_min: m.hdt_min,
      hdt_max: m.hdt_max,
      service_temp_min: m.service_temp_min,
      service_temp_max: m.service_temp_max,
      service_temp_limit: m.service_temp_limit,
      features: m.features ?? [],
      cautions: m.cautions ?? [],
      applications: m.applications ?? [],
      price_min: m.price_min,
      price_max: m.price_max,
      price_unit: m.price_unit,
      price_note: m.price_note,
      molding_process: m.molding_process ?? [],
      certifications: m.certifications ?? {},
      limitations: m.limitations ?? [],
      source: m.source,
      source_date: m.source_date,
      value_type: m.value_type,
    })
  }, [isEdit, material.data])

  /* 草稿恢复检测 */
  useEffect(() => {
    if (!isEdit || !loadedRef.current || draftFound) return
    try {
      if (localStorage.getItem(DRAFT_KEY(uid))) setDraftFound(true)
    } catch {
      /* localStorage 不可用则忽略草稿功能 */
    }
  }, [isEdit, uid, material.data, draftFound])

  /* 每 30s 自动存草稿 */
  useEffect(() => {
    if (!dirty) return
    const t = window.setInterval(() => {
      try {
        localStorage.setItem(DRAFT_KEY(uid), JSON.stringify(form))
      } catch {
        /* ignore */
      }
    }, 30_000)
    return () => window.clearInterval(t)
  }, [dirty, form, uid])

  /* 未保存离开拦截 */
  useEffect(() => {
    if (!dirty) return
    const h = (e: BeforeUnloadEvent) => {
      e.preventDefault()
      e.returnValue = ''
    }
    window.addEventListener('beforeunload', h)
    return () => window.removeEventListener('beforeunload', h)
  }, [dirty])

  /* 锚点高亮 */
  useEffect(() => {
    const obs = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) setActive(e.target.id)
        })
      },
      { rootMargin: '-72px 0px -65% 0px', threshold: 0 },
    )
    SECTIONS.forEach((s) => {
      const el = sectionRefs.current[s.id]
      if (el) obs.observe(el)
    })
    return () => obs.disconnect()
  }, [isEdit, material.data])

  const set = useCallback(<K extends keyof FormState>(k: K, v: FormState[K]) => {
    setForm((f) => ({ ...f, [k]: v }))
    setDirty(true)
  }, [])

  const setNum = useCallback((k: string, v: number | null) => {
    setForm((f) => ({ ...f, [k]: v }) as FormState)
    setDirty(true)
  }, [])

  const num = (k: string) => (form as unknown as Record<string, number | null | undefined>)[k]

  const validate = () => {
    const err: Record<string, string> = {}
    if (!form.name?.trim()) err.name = '材料名称为必填项'
    RANGES.concat(THERMAL).forEach((r) => {
      const min = num(`${r.key}_min`)
      const max = num(`${r.key}_max`)
      if (min != null && max != null && min > max) err[`${r.key}_range`] = '最小值不能大于最大值'
    })
    if (form.price_min != null && form.price_max != null && form.price_min > form.price_max) err.price_range = '价格最小值不能大于最大值'
    setErrors(err)
    return err
  }

  const save = useMutation({
    mutationFn: async () => {
      const err = validate()
      if (Object.keys(err).length) throw new Error(`有 ${Object.keys(err).length} 处需要修正`)
      if (isEdit) return api.updateMaterial(uid!, form)
      return api.createMaterial(form)
    },
    onSuccess: (res) => {
      const detail = 'material' in res ? res.material : res
      try {
        localStorage.removeItem(DRAFT_KEY(uid))
      } catch {
        /* ignore */
      }
      setDirty(false)
      setErrors({})
      toast(isEdit ? `保存成功 · 已生成 v${'new_version' in res ? res.new_version : 1} 快照` : '保存成功 · 材料已创建', 'success')
      qc.invalidateQueries({ queryKey: ['materials'] })
      qc.invalidateQueries({ queryKey: ['categories'] })
      if (!isEdit) navigate(`/materials/${detail.uid}`)
      else qc.invalidateQueries({ queryKey: ['material', uid] })
    },
    onError: (e) => {
      const msg = e instanceof Error ? e.message : '保存失败'
      if (msg.startsWith('有 ')) toast(msg, 'danger')
      else toast(msg, 'danger')
    },
  })

  const scrollTo = (id: string) => {
    const el = sectionRefs.current[id]
    el?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    setActive(id)
  }

  const selectedCatName = useMemo(() => {
    const find = (nodes: { id: number; name: string; children?: { id: number; name: string }[] }[]): string | null => {
      for (const n of nodes) {
        if (n.id === form.category_id) return n.name
        const c = n.children?.find((x) => x.id === form.category_id)
        if (c) return c.name
      }
      return null
    }
    return find(categories.data?.items ?? [])
  }, [categories.data, form.category_id])

  const ref = (id: string) => (el: HTMLElement | null) => {
    sectionRefs.current[id] = el
  }

  const fieldCount = isEdit ? '保存后直接生效（单机无审核流转）' : '新建后写入本机材料主库'

  return (
    <>
      <ToastHost />
      <SidePanel title="材料分类" sub="点击选择材料归属" foot={<span>分类为两级结构；材料可归属到子类，也可暂不归属。</span>}>
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
            selectedId={form.category_id ?? null}
            onSelect={(id) => set('category_id', id)}
          />
        )}
      </SidePanel>

      <main className="ms-main">
        <div className="ms-page-header">
          <div>
            <h1 className="ms-page-header__title">{isEdit ? `编辑材料 · ${form.name || '载入中'}` : '新建材料'}</h1>
            <div className="ms-page-header__sub">{dirty ? '有未保存修改' : '无待保存修改'} · {fieldCount}</div>
          </div>
          <div className="ms-page-header__actions">
            <button
              className="ms-btn ms-btn--secondary"
              onClick={() => {
                try {
                  localStorage.setItem(DRAFT_KEY(uid), JSON.stringify(form))
                  toast('草稿已存到本机', 'success')
                } catch {
                  toast('草稿保存失败', 'danger')
                }
              }}
            >
              存为草稿
            </button>
            <button className="ms-btn ms-btn--primary" onClick={() => save.mutate()} disabled={save.isPending}>
              {save.isPending && <span className="ms-spin" style={{ color: '#fff' }} />}
              保存并生效
            </button>
          </div>
        </div>

        {draftFound && (
          <Notice tone="info">
            <div className="ms-row ms-gap-4" style={{ flexWrap: 'wrap' }}>
              <span>检测到未保存草稿，是否恢复？</span>
              <button
                className="ms-btn ms-btn--sm ms-btn--secondary"
                onClick={() => {
                  try {
                    const raw = localStorage.getItem(DRAFT_KEY(uid))
                    if (raw) setForm(JSON.parse(raw) as FormState)
                    toast('已恢复草稿', 'success')
                  } catch {
                    toast('草稿已损坏，无法恢复', 'danger')
                  }
                  setDraftFound(false)
                }}
              >
                恢复草稿
              </button>
              <button
                className="ms-btn ms-btn--sm ms-btn--ghost"
                onClick={() => {
                  try {
                    localStorage.removeItem(DRAFT_KEY(uid))
                  } catch {
                    /* ignore */
                  }
                  setDraftFound(false)
                }}
              >
                丢弃草稿
              </button>
            </div>
          </Notice>
        )}

        {Object.keys(errors).length > 0 && (
          <Notice tone="danger">
            有 {Object.keys(errors).length} 处需要修正，请检查标红的字段后再次保存。
          </Notice>
        )}

        {isEdit && material.isError && (
          <Notice tone="danger">
            <div className="ms-col" style={{ gap: 6 }}>
              <span>材料加载失败：{material.error instanceof Error ? material.error.message : '未知错误'}</span>
              <button className="ms-link" style={{ background: 'none', border: 'none', alignSelf: 'flex-start' }} onClick={() => material.refetch()}>
                重试
              </button>
            </div>
          </Notice>
        )}

        {isEdit && material.isLoading ? (
          /* 编辑态加载骨架：避免数据未回来时闪现空表单（D-03） */
          <div className="ms-col" style={{ gap: 'var(--sp-6)' }} aria-busy="true" aria-label="表单载入中">
            {[0, 1, 2].map((i) => (
              <div key={i} className="ms-card ms-edit__card">
                <Skeleton height={18} width="30%" />
                <div className="ms-field-grid" style={{ marginTop: 'var(--sp-5)' }}>
                  <Skeleton height={34} />
                  <Skeleton height={34} />
                  <Skeleton height={34} />
                  <Skeleton height={34} />
                </div>
              </div>
            ))}
          </div>
        ) : (
        <div className="ms-edit">
          <nav className="ms-edit__nav" aria-label="表单锚点">
            {SECTIONS.map((s) => (
              <button key={s.id} className={`ms-edit__nav-item${active === s.id ? ' ms-edit__nav-item--active' : ''}`} onClick={() => scrollTo(s.id)}>
                {s.label}
              </button>
            ))}
          </nav>

          <div className="ms-edit__form">
            {/* 基本信息 */}
            <section className="ms-card ms-edit__card" id="basic" ref={ref('basic')}>
              <div className="ms-card__title">基本信息</div>
              <div className="ms-field-grid">
                <Field label="材料名称" required error={errors.name}>
                  <input className={`ms-input${errors.name ? ' ms-input--error' : ''}`} value={form.name ?? ''} onChange={(e) => set('name', e.target.value)} placeholder="例如 PA66+GF30" />
                </Field>
                <Field label="简称 · 牌号">
                  <input className="ms-input" value={form.short_name ?? ''} onChange={(e) => set('short_name', e.target.value)} placeholder="例如 GF30 增强尼龙" />
                </Field>
                <Field label="别名（逗号分隔，参与检索召回）" full>
                  <input
                    className="ms-input"
                    value={(form.aliases ?? []).join('，')}
                    onChange={(e) => set('aliases', e.target.value.split(/[,，]/).map((s) => s.trim()).filter(Boolean))}
                    placeholder="尼龙66+玻纤30、PA66-GF30"
                  />
                </Field>
                <Field label="分类（大类 / 子类）" full>
                  <div className="ms-row ms-gap-4">
                    <span className="ms-chip ms-chip--26">{selectedCatName ?? '未归类'}</span>
                    <span className="ms-muted" style={{ fontSize: 'var(--fs-caption)' }}>在左侧分类树中选择</span>
                  </div>
                </Field>
                <Field label="材料描述" full>
                  <textarea className="ms-input" style={{ height: 64, padding: 10, resize: 'none', lineHeight: 19 }} value={form.description ?? ''} onChange={(e) => set('description', e.target.value)} placeholder="一句话说明这个材料的定位与典型用途" />
                </Field>
              </div>
            </section>

            {/* 力学参数 */}
            <section className="ms-card ms-edit__card" id="mech" ref={ref('mech')}>
              <div className="ms-card__title">力学参数</div>
              <div className="ms-field-grid">
                {RANGES.map((r) => (
                  <RangeField
                    key={r.key}
                    label={r.label}
                    unit={r.unit}
                    min={num(`${r.key}_min`)}
                    max={num(`${r.key}_max`)}
                    error={errors[`${r.key}_range`]}
                    onMin={(v) => setNum(`${r.key}_min`, v)}
                    onMax={(v) => setNum(`${r.key}_max`, v)}
                  />
                ))}
              </div>
            </section>

            {/* 热学参数 */}
            <section className="ms-card ms-edit__card" id="thermal" ref={ref('thermal')}>
              <div className="ms-card__title">热学参数</div>
              <div className="ms-field-grid">
                {THERMAL.map((r) => (
                  <RangeField
                    key={r.key}
                    label={r.label}
                    unit={r.unit}
                    min={num(`${r.key}_min`)}
                    max={num(`${r.key}_max`)}
                    error={errors[`${r.key}_range`]}
                    onMin={(v) => setNum(`${r.key}_min`, v)}
                    onMax={(v) => setNum(`${r.key}_max`, v)}
                  />
                ))}
                <Field label="长期使用温度上限" hint="推荐逻辑核心字段，硬约束以此值过滤" emphasis>
                  <input
                    className="ms-input ms-input--mono"
                    type="number"
                    value={form.service_temp_limit ?? ''}
                    onChange={(e) => set('service_temp_limit', e.target.value === '' ? null : Number(e.target.value))}
                    placeholder="例如 150"
                  />
                </Field>
              </div>
            </section>

            {/* 特性与风险 */}
            <section className="ms-card ms-edit__card" id="risks" ref={ref('risks')}>
              <div className="ms-card__title">特性与风险</div>
              <ChipEditor label="特性标签" items={form.features ?? []} onChange={(v) => set('features', v)} placeholder="例如 阻燃、耐化学" />
              <div style={{ marginTop: 'var(--sp-6)' }}>
                <div className="ms-field__label" style={{ marginBottom: 'var(--sp-4)' }}>
                  注意事项（会被推荐解释引用，建议用警示语气）
                </div>
                <div className="ms-col" style={{ gap: 'var(--sp-4)' }}>
                  {(form.cautions ?? []).map((c, i) => (
                    <div key={i} className="ms-row ms-gap-4">
                      <input
                        className="ms-input"
                        style={{ width: 140, flex: 'none' }}
                        placeholder="类型，如 失效模式"
                        value={c.type}
                        onChange={(e) => {
                          const next = [...(form.cautions ?? [])]
                          next[i] = { ...next[i], type: e.target.value }
                          set('cautions', next)
                        }}
                      />
                      <input
                        className="ms-input"
                        placeholder="内容，例如 长期接触强酸会水解"
                        value={c.content}
                        onChange={(e) => {
                          const next = [...(form.cautions ?? [])]
                          next[i] = { ...next[i], content: e.target.value }
                          set('cautions', next)
                        }}
                      />
                      <button className="ms-icon-btn ms-icon-btn--danger" aria-label="删除注意事项" onClick={() => set('cautions', (form.cautions ?? []).filter((_, j) => j !== i))}>
                        <Icon name="trash" size={14} />
                      </button>
                    </div>
                  ))}
                  <button className="ms-btn ms-btn--secondary ms-btn--sm" style={{ alignSelf: 'flex-start' }} onClick={() => set('cautions', [...(form.cautions ?? []), { type: '', content: '' } as Caution])}>
                    <Icon name="plus" size={14} />
                    添加注意事项
                  </button>
                </div>
              </div>
              <div style={{ marginTop: 'var(--sp-6)' }}>
                <ChipEditor label="失效模式 / 不适用场景" items={form.limitations ?? []} onChange={(v) => set('limitations', v)} placeholder="例如 不耐强酸、易翘曲" />
              </div>
            </section>

            {/* 应用与成本 */}
            <section className="ms-card ms-edit__card" id="apps" ref={ref('apps')}>
              <div className="ms-card__title">应用与成本</div>
              <ChipEditor label="典型应用场景" items={form.applications ?? []} onChange={(v) => set('applications', v)} placeholder="例如 保险丝座、连接器" />
              <div style={{ marginTop: 'var(--sp-6)' }}>
                <ChipEditor label="推荐成型工艺" items={form.molding_process ?? []} onChange={(v) => set('molding_process', v)} placeholder="例如 注塑" />
              </div>
              <div className="ms-field-grid" style={{ marginTop: 'var(--sp-6)' }}>
                <RangeField
                  label="参考价"
                  unit={form.price_unit === '元/kg' || !form.price_unit ? '元/kg' : form.price_unit}
                  min={form.price_min ?? null}
                  max={form.price_max ?? null}
                  error={errors.price_range}
                  onMin={(v) => set('price_min', v)}
                  onMax={(v) => set('price_max', v)}
                />
                <Field label="价格单位">
                  <select className="ms-input" value={form.price_unit ?? '元/kg'} onChange={(e) => set('price_unit', e.target.value)}>
                    <option value="元/kg">元/kg</option>
                    <option value="元/吨">元/吨</option>
                  </select>
                </Field>
                <Field label="价格备注" full>
                  <input className="ms-input" value={form.price_note ?? ''} onChange={(e) => set('price_note', e.target.value)} placeholder="例如 随原料行情波动，以最新报价为准" />
                </Field>
              </div>
            </section>

            {/* 认证与合规 */}
            <section className="ms-card ms-edit__card" id="cert" ref={ref('cert')}>
              <div className="ms-card__title">认证与合规</div>
              <div className="ms-field-grid">
                <Field label="UL94 等级（含厚度）">
                  <input
                    className="ms-input"
                    value={form.certifications?.ul94 ?? ''}
                    onChange={(e) => set('certifications', { ...(form.certifications ?? {}), ul94: e.target.value })}
                    placeholder="例如 V-0 (1.6mm)"
                  />
                </Field>
                <Field label="UL 黄卡编号">
                  <input
                    className="ms-input"
                    value={form.certifications?.ul_yellow_card ?? ''}
                    onChange={(e) => set('certifications', { ...(form.certifications ?? {}), ul_yellow_card: e.target.value })}
                    placeholder="例如 E123456"
                  />
                </Field>
                {(['rohs', 'reach'] as const).map((k) => (
                  <Field key={k} label={k.toUpperCase()}>
                    <select
                      className="ms-input"
                      value={form.certifications?.[k] == null ? '' : form.certifications[k] ? 'yes' : 'no'}
                      onChange={(e) =>
                        set('certifications', {
                          ...(form.certifications ?? {}),
                          [k]: e.target.value === '' ? null : e.target.value === 'yes',
                        } as Certification)
                      }
                    >
                      <option value="">未声明</option>
                      <option value="yes">符合</option>
                      <option value="no">不符合</option>
                    </select>
                  </Field>
                ))}
                <Field label="IATF">
                  <input
                    className="ms-input"
                    value={form.certifications?.iatf ?? ''}
                    onChange={(e) => set('certifications', { ...(form.certifications ?? {}), iatf: e.target.value })}
                    placeholder="例如 16949"
                  />
                </Field>
              </div>
            </section>

            {/* 数据来源与版本 */}
            <section className="ms-card ms-edit__card" id="source" ref={ref('source')}>
              <div className="ms-card__title">数据来源与版本</div>
              <div className="ms-field-grid">
                <Field label="来源">
                  <input className="ms-input" value={form.source ?? ''} onChange={(e) => set('source', e.target.value)} placeholder="例如 供应商 TDS 2025-03" />
                </Field>
                <Field label="来源日期">
                  <input className="ms-input ms-input--mono" type="date" value={(form.source_date ?? '').slice(0, 10)} onChange={(e) => set('source_date', e.target.value)} />
                </Field>
                <Field label="值类型" full>
                  <div className="ms-row ms-gap-3">
                    {(['typical', 'guaranteed'] as ValueType[]).map((v) => (
                      <Chip key={v} size="26" selected={(form.value_type ?? 'typical') === v} onClick={() => set('value_type', v)}>
                        {v === 'typical' ? '典型值' : '保证值'}
                      </Chip>
                    ))}
                  </div>
                </Field>
              </div>
              <div className="ms-row" style={{ justifyContent: 'flex-end', marginTop: 'var(--sp-6)' }}>
                <button className="ms-btn ms-btn--primary" onClick={() => save.mutate()} disabled={save.isPending}>
                  保存并生效
                </button>
              </div>
            </section>
          </div>
        </div>
        )}
      </main>
    </>
  )
}

/* ---------------- 内部小工具 ---------------- */

function Field({
  label,
  children,
  error,
  hint,
  required,
  full,
  emphasis,
}: {
  label: string
  children: React.ReactNode
  error?: string
  hint?: string
  required?: boolean
  full?: boolean
  emphasis?: boolean
}) {
  return (
    <div className={`ms-field${full ? ' ms-field--full' : ''}`}>
      <div className="ms-field__label" style={emphasis ? { color: 'var(--color-accent)' } : undefined}>
        {label}
        {required && <span className="ms-field__req"> *</span>}
        {hint && <span className="ms-muted" style={{ marginLeft: 6, fontWeight: 400 }}>{hint}</span>}
      </div>
      {children}
      {error && <div className="ms-field__err">{error}</div>}
    </div>
  )
}

function RangeField({
  label,
  unit,
  min,
  max,
  error,
  onMin,
  onMax,
}: {
  label: string
  unit: string
  min: number | null | undefined
  max: number | null | undefined
  error?: string
  onMin: (v: number | null) => void
  onMax: (v: number | null) => void
}) {
  const parse = (v: string) => (v === '' ? null : Number.isNaN(Number(v)) ? null : Number(v))
  return (
    <div className="ms-field">
      <div className="ms-field__label">
        {label} <span className="ms-muted" style={{ fontWeight: 400 }}>({unit})</span>
      </div>
      <div className="ms-range-wrap">
        <input className={`ms-input ms-input--mono${error ? ' ms-input--error' : ''}`} type="number" placeholder="最小" aria-label={`${label}最小值`} value={min ?? ''} onChange={(e) => onMin(parse(e.target.value))} />
        <span className="ms-range-sep">–</span>
        <input className={`ms-input ms-input--mono${error ? ' ms-input--error' : ''}`} type="number" placeholder="最大" aria-label={`${label}最大值`} value={max ?? ''} onChange={(e) => onMax(parse(e.target.value))} />
      </div>
      {error && <div className="ms-field__err">{error}</div>}
    </div>
  )
}

function ChipEditor({
  label,
  items,
  onChange,
  placeholder,
}: {
  label: string
  items: string[]
  onChange: (v: string[]) => void
  placeholder?: string
}) {
  const [adding, setAdding] = useState(false)
  const [val, setVal] = useState('')
  const commit = () => {
    const v = val.trim()
    if (v) onChange([...items, v])
    setVal('')
    setAdding(false)
  }
  return (
    <div className="ms-field">
      <div className="ms-field__label">{label}</div>
      <div className="ms-chips-edit">
        {items.map((it, i) => (
          <Chip key={`${it}-${i}`} size="24" closable onClose={() => onChange(items.filter((_, j) => j !== i))}>
            {it}
          </Chip>
        ))}
        {adding ? (
          <input
            className="ms-input"
            style={{ width: 160, height: 30 }}
            autoFocus
            placeholder={placeholder}
            value={val}
            onChange={(e) => setVal(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') commit()
              if (e.key === 'Escape') {
                setAdding(false)
                setVal('')
              }
            }}
            onBlur={commit}
          />
        ) : (
          <button className="ms-link" style={{ background: 'none', border: 'none', fontSize: 'var(--fs-small)', fontWeight: 'var(--fw-medium)' }} onClick={() => setAdding(true)}>
            + 添加{label.replace(/（.*?）/, '')}
          </button>
        )}
      </div>
    </div>
  )
}
