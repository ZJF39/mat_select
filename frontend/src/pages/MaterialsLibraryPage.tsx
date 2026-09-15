import { useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { api, downloadExport, type MaterialQuery } from '../api/client'
import { SidePanel } from '../layout/SidePanel'
import { CategoryTree } from '../components/CategoryTree'
import { FilterSelect, type FilterOption } from '../components/FilterSelect'
import { MaterialCard } from '../components/MaterialCard'
import { MaterialTable, type MaterialSort } from '../components/MaterialTable'
import { EmptyState } from '../components/EmptyState'
import { Notice } from '../components/Notice'
import { SkeletonCard, SkeletonRow, SkeletonTreeRow } from '../components/Skeleton'
import { Icon } from '../icons'
import { toast, ToastHost } from '../components/Toast'
import './pages.css'

/** 01 卡片视图 + 02 表格视图（原型 02 §01/§02） */

const PROCESS_OPTS: FilterOption[] = [
  { value: '注塑', label: '注塑' },
  { value: '挤出', label: '挤出' },
  { value: '吹塑', label: '吹塑' },
  { value: '热成型', label: '热成型' },
  { value: '压缩模塑', label: '压缩模塑' },
  { value: '发泡', label: '发泡' },
]

const FEATURE_OPTS: FilterOption[] = [
  { value: '阻燃', label: '阻燃' },
  { value: '耐高温', label: '耐高温' },
  { value: '高刚性', label: '高刚性' },
  { value: '高韧性', label: '高韧性' },
  { value: '耐化学', label: '耐化学' },
  { value: '低翘曲', label: '低翘曲' },
  { value: '轻量化', label: '轻量化' },
  { value: '电绝缘', label: '电绝缘' },
]

const FLAME_OPTS: FilterOption[] = [
  { value: 'V-0', label: 'UL94 V-0' },
  { value: 'V-1', label: 'UL94 V-1' },
  { value: 'V-2', label: 'UL94 V-2' },
  { value: 'HB', label: 'UL94 HB' },
  { value: '5VA', label: 'UL94 5VA' },
]

const SORTS: { key: string; label: string; sort: MaterialSort; order: 'asc' | 'desc' }[] = [
  { key: 'cat', label: '类别 · 名称', sort: 'category_name', order: 'asc' },
  { key: 'density', label: '密度 ↑', sort: 'density', order: 'asc' },
  { key: 'temp', label: '耐温上限 ↓', sort: 'service_temp_limit', order: 'desc' },
  { key: 'price', label: '参考价 ↑', sort: 'price', order: 'asc' },
]

const PAGE_STEP = 48

export default function MaterialsLibraryPage() {
  const navigate = useNavigate()
  const [sp, setSp] = useSearchParams()
  const [sortOpen, setSortOpen] = useState(false)
  const [selected, setSelected] = useState<string[]>([])

  const view = sp.get('view') === 'table' ? 'table' : 'card'
  const q = sp.get('q') ?? ''
  const sortKey = sp.get('sort') ?? 'cat'
  const cats = useMemo(
    () => (sp.get('cat') ?? '').split(',').filter(Boolean).map((x) => Number(x)),
    [sp],
  )
  const procs = useMemo(() => (sp.get('proc') ?? '').split(',').filter(Boolean), [sp])
  const feats = useMemo(() => (sp.get('feat') ?? '').split(',').filter(Boolean), [sp])
  const flame = sp.get('flame') ?? ''
  const tempMin = sp.get('temp_min') ? Number(sp.get('temp_min')) : undefined
  const priceMax = sp.get('price_max') ? Number(sp.get('price_max')) : undefined
  const pageSize = sp.get('size') ? Number(sp.get('size')) : PAGE_STEP

  const activeSort = SORTS.find((s) => s.key === sortKey) ?? SORTS[0]

  /** 写 URL（筛选项即时生效，用 replace 避免污染后退栈） */
  const patch = (next: Record<string, string | undefined>, replace = true) => {
    const p = new URLSearchParams(sp)
    Object.entries(next).forEach(([k, v]) => {
      if (v === undefined || v === '') p.delete(k)
      else p.set(k, v)
    })
    setSp(p, { replace })
  }

  const clearAll = () => patch({ q: undefined, cat: undefined, proc: undefined, feat: undefined, flame: undefined, temp_min: undefined, price_max: undefined, size: undefined })

  const params = useMemo<MaterialQuery>(
    () => ({
      q: q || undefined,
      category_ids: cats.length ? cats : undefined,
      processes: procs.length ? procs : undefined,
      features: feats.length ? feats : undefined,
      flame: flame || undefined,
      temp_min: tempMin,
      price_max: priceMax,
      sort: activeSort.sort,
      order: activeSort.order,
      page: 1,
      page_size: pageSize,
    }),
    [q, cats, procs, feats, flame, tempMin, priceMax, activeSort, pageSize],
  )

  /** placeholderData: 加载更多时 queryKey 变化（size 变大），保留上一份数据渲染，
   *  已有卡片（uid 作 key）不卸载、新卡片在下方追加，避免骨架屏闪烁导致滚动跳回顶部。 */
  const materials = useQuery({
    queryKey: ['materials', params],
    queryFn: () => api.listMaterials(params),
    staleTime: 30_000,
    placeholderData: keepPreviousData,
  })

  const categories = useQuery({
    queryKey: ['categories'],
    queryFn: () => api.listCategories(),
    staleTime: 60_000,
  })

  const activeCount =
    (q ? 1 : 0) + cats.length + procs.length + feats.length + (flame ? 1 : 0) + (tempMin != null ? 1 : 0) + (priceMax != null ? 1 : 0)

  const items = materials.data?.items ?? []
  const total = materials.data?.total ?? 0
  /** 加载更多请求在途（placeholder 数据展示期间或后台刷新中） */
  const loadingMore = materials.isPlaceholderData || materials.isFetching

  const catOptions: FilterOption[] = useMemo(() => {
    const roots = categories.data?.items ?? []
    const flat: FilterOption[] = []
    roots.forEach((n) => {
      flat.push({ value: String(n.id), label: n.name, count: n.count })
      ;(n.children ?? []).forEach((c) => flat.push({ value: String(c.id), label: `　${c.name}`, count: c.count }))
    })
    return flat
  }, [categories.data])

  const toggleSelect = (uid: string) =>
    setSelected((s) => (s.includes(uid) ? s.filter((x) => x !== uid) : [...s, uid]))

  const exportSelected = async () => {
    try {
      await downloadExport({
        scope: 'selected',
        format: 'xlsx',
        include_work_data: false,
        ids: selected,
      })
      toast(`已导出 ${selected.length} 条材料行为 Excel`, 'success')
    } catch {
      toast('导出失败，请重试', 'danger')
    }
  }

  return (
    <>
      <ToastHost />
      <SidePanel
        title="材料分类"
        sub="两级体系 · 点击筛选"
        foot={<span>分类为两级结构，材料归属到子类；「全部分类」可清除分类筛选。</span>}
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
            selectedId={cats.length === 1 ? cats[0] : null}
            onSelect={(id) => patch({ cat: id == null ? undefined : String(id), size: undefined })}
          />
        )}
      </SidePanel>

      <main className="ms-main">
        <div className="ms-page-header">
          <div>
            <h1 className="ms-page-header__title">全部材料</h1>
            <div className="ms-page-header__sub">
              共 {total} 条 · 参数更新与来源可在详情页查看
            </div>
          </div>
          <div className="ms-page-header__actions">
            <div className="ms-segmented" role="tablist" aria-label="视图切换">
              <button
                type="button"
                role="tab"
                aria-selected={view === 'card'}
                className={`ms-segmented__item${view === 'card' ? ' ms-segmented__item--active' : ''}`}
                onClick={() => patch({ view: undefined }, false)}
              >
                <Icon name="layers" size={13} />
                卡片
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={view === 'table'}
                className={`ms-segmented__item${view === 'table' ? ' ms-segmented__item--active' : ''}`}
                onClick={() => patch({ view: 'table' }, false)}
              >
                <Icon name="database" size={13} />
                表格
              </button>
            </div>
            <button className="ms-btn ms-btn--primary ms-newbtn" onClick={() => navigate('/materials/new')}>
              <Icon name="plus" size={14} />
              新建材料
            </button>
          </div>
        </div>

        {/* 筛选条 */}
        <div className="ms-filterbar">
          <FilterSelect
            mode="multi"
            label="分类"
            active={cats.length > 0}
            display={`分类 · ${cats.length} 项`}
            options={catOptions}
            value={cats.map(String)}
            onChange={(v) => patch({ cat: v.join(',') || undefined, size: undefined })}
          />
          <FilterSelect
            mode="multi"
            label="工艺"
            active={procs.length > 0}
            display={`工艺 · ${procs.join('/')}`}
            options={PROCESS_OPTS}
            value={procs}
            onChange={(v) => patch({ proc: v.join(',') || undefined, size: undefined })}
          />
          <FilterSelect
            mode="range"
            label="耐温上限"
            unit="°C"
            active={tempMin != null}
            display={tempMin != null ? `耐温 ≥ ${tempMin} °C` : undefined}
            value={{ min: tempMin }}
            onChange={(v) => patch({ temp_min: v.min != null ? String(v.min) : undefined, size: undefined })}
          />
          <FilterSelect
            mode="range"
            label="参考价"
            unit="元/kg"
            active={priceMax != null}
            display={priceMax != null ? `参考价 ≤ ${priceMax} 元/kg` : undefined}
            value={{ max: priceMax }}
            onChange={(v) => patch({ price_max: v.max != null ? String(v.max) : undefined, size: undefined })}
          />
          <FilterSelect
            mode="single"
            label="阻燃等级"
            active={!!flame}
            display={`阻燃 · ${flame}`}
            options={FLAME_OPTS}
            value={flame ? [flame] : []}
            onChange={(v) => patch({ flame: v.length ? v[v.length - 1] : undefined, size: undefined })}
          />
          <FilterSelect
            mode="multi"
            label="特性标签"
            active={feats.length > 0}
            display={`特性 · ${feats.join('/')}`}
            options={FEATURE_OPTS}
            value={feats}
            onChange={(v) => patch({ feat: v.join(',') || undefined, size: undefined })}
          />
          {activeCount > 0 && (
            <button className="ms-selected-note" onClick={clearAll}>
              已选 {activeCount} 项 · 清除
            </button>
          )}
          <div className="ms-filterbar__spacer" />
          <span className="ms-filterbar__hit">
            命中 {items.length} / {total} 条
          </span>
          <div style={{ position: 'relative' }}>
            <button className="ms-filterbar__sort" aria-haspopup="true" aria-expanded={sortOpen} onClick={() => setSortOpen((o) => !o)}>
              排序：{activeSort.label}
              <Icon name="chevronDown" size={10} />
            </button>
            {sortOpen && (
              <>
                <div
                  style={{ position: 'fixed', inset: 0, zIndex: 39 }}
                  onClick={() => setSortOpen(false)}
                  aria-hidden
                />
                <div className="ms-filter-pop" style={{ right: 0, left: 'auto', width: 180, zIndex: 40 }}>
                  {SORTS.map((s) => (
                    <button
                      key={s.key}
                      className={`ms-edit__nav-item${s.key === sortKey ? ' ms-edit__nav-item--active' : ''}`}
                      onClick={() => {
                        patch({ sort: s.key === 'cat' ? undefined : s.key })
                        setSortOpen(false)
                      }}
                    >
                      {s.label}
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>

        {/* 数据面 */}
        {materials.isError ? (
          <Notice tone="danger">
            <div className="ms-col" style={{ gap: 6 }}>
              <span>材料列表加载失败：{materials.error instanceof Error ? materials.error.message : '未知错误'}</span>
              <button className="ms-link" style={{ background: 'none', border: 'none', alignSelf: 'flex-start' }} onClick={() => materials.refetch()}>
                重试
              </button>
            </div>
          </Notice>
        ) : materials.data === undefined ? (
          view === 'card' ? (
            <div className="ms-card-grid">
              {[0, 1, 2, 3, 4, 5].map((i) => (
                <SkeletonCard key={i} />
              ))}
            </div>
          ) : (
            <div className="ms-table-wrap">
              {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11].map((i) => (
                <SkeletonRow key={i} cols={9} />
              ))}
            </div>
          )
        ) : items.length === 0 ? (
          <EmptyState
            icon="search"
            title="未找到匹配材料"
            desc="试试减少筛选条件，或换个关键词。已选筛选条件不会被自动清除。"
            action={
              activeCount > 0 ? (
                <button className="ms-btn ms-btn--secondary" onClick={clearAll}>
                  清除全部筛选
                </button>
              ) : (
                <button className="ms-btn ms-btn--primary" onClick={() => navigate('/materials/new')}>
                  <Icon name="plus" size={14} />
                  新建材料
                </button>
              )
            }
          />
        ) : view === 'card' ? (
          <>
            <div className="ms-card-grid">
              {items.map((m) => (
                <MaterialCard key={m.uid} material={m} onOpen={(uid) => navigate(`/materials/${uid}`)} />
              ))}
            </div>
            {items.length < total && (
              <div className="ms-row" style={{ justifyContent: 'center' }}>
                <button
                  className="ms-btn ms-btn--secondary"
                  disabled={loadingMore}
                  onClick={() => patch({ size: String(pageSize + PAGE_STEP) })}
                >
                  {loadingMore ? '加载中…' : `加载更多（已显示 ${items.length} / ${total} 条）`}
                </button>
              </div>
            )}
          </>
        ) : (
          <MaterialTable
            materials={items}
            selectable
            selectedIds={selected}
            onToggleSelect={toggleSelect}
            sort={activeSort.sort}
            onSort={(s) => {
              const hit = SORTS.find((x) => x.sort === s)
              patch({ sort: hit ? (hit.key === 'cat' ? undefined : hit.key) : undefined })
            }}
            onOpen={(uid) => navigate(`/materials/${uid}`)}
            onExportSelected={exportSelected}
            total={total}
            onLoadMore={() => patch({ size: String(pageSize + PAGE_STEP) })}
          />
        )}
      </main>
    </>
  )
}
