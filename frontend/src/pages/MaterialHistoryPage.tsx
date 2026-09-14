import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { SidePanel } from '../layout/SidePanel'
import { CategoryTree } from '../components/CategoryTree'
import { DiffRow } from '../components/DiffRow'
import { Notice } from '../components/Notice'
import { EmptyState } from '../components/EmptyState'
import { Modal } from '../components/Modal'
import { Skeleton, SkeletonTreeRow } from '../components/Skeleton'
import { Icon } from '../icons'
import { formatTime } from '../utils/format'
import { toast, ToastHost } from '../components/Toast'
import './pages.css'

/** 08 变更历史 · diff（原型 02 §08） */

export default function MaterialHistoryPage() {
  const { uid = '' } = useParams()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [toVersion, setToVersion] = useState<number | null>(null)
  const [confirmRestore, setConfirmRestore] = useState<number | null>(null)

  const material = useQuery({
    queryKey: ['material', uid],
    queryFn: () => api.getMaterial(uid),
    enabled: !!uid,
    staleTime: 30_000,
  })

  const revisions = useQuery({
    queryKey: ['revisions', uid],
    queryFn: () => api.listRevisions(uid),
    enabled: !!uid,
  })

  const categories = useQuery({
    queryKey: ['categories'],
    queryFn: () => api.listCategories(),
    staleTime: 60_000,
  })

  const list = useMemo(
    () => [...(revisions.data?.items ?? [])].sort((a, b) => a.version - b.version),
    [revisions.data],
  )

  useEffect(() => {
    if (toVersion == null && list.length) setToVersion(list[list.length - 1].version)
  }, [list, toVersion])

  const toIdx = list.findIndex((r) => r.version === toVersion)
  const from = toIdx > 0 ? list[toIdx - 1] : undefined
  const to = toIdx >= 0 ? list[toIdx] : undefined

  const diff = useQuery({
    queryKey: ['diff', uid, from?.version ?? 0, to?.version ?? 0],
    queryFn: () => api.getDiff(uid, to!.version, from!.version),
    enabled: !!uid && !!from && !!to,
    staleTime: 60_000,
  })

  const restore = useMutation({
    mutationFn: (rid: number) => api.restoreRevision(uid, rid),
    onSuccess: (res) => {
      setConfirmRestore(null)
      toast(`已恢复 · 生成 v${res.new_version} 快照`, 'success')
      qc.invalidateQueries({ queryKey: ['revisions', uid] })
      qc.invalidateQueries({ queryKey: ['material', uid] })
      qc.invalidateQueries({ queryKey: ['materials'] })
      navigate(`/materials/${uid}`)
    },
    onError: (e) => toast(e instanceof Error ? e.message : '恢复失败', 'danger'),
  })

  const exportRecord = () => {
    const payload = diff.data
    if (!payload) return
    const lines = [
      `# 变更记录 · ${material.data?.name ?? uid}`,
      ``,
      `版本 v${payload.from_version} → v${payload.to_version}`,
      ``,
      `摘要：${payload.summary}`,
      ``,
      `| 字段 | 变更前 | 变更后 | 类型 |`,
      `| --- | --- | --- | --- |`,
      ...payload.rows.map(
        (r) =>
          `| ${r.field} | ${(r.before_items.length ? r.before_items.join('、') : r.before) ?? '—'} | ${
            (r.after_items.length ? r.after_items.join('、') : r.after) ?? '—'
          } | ${r.type} |`,
      ),
    ]
    const blob = new Blob([lines.join('\n')], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `MatSelect_变更记录_${material.data?.name ?? uid}_v${payload.from_version}-v${payload.to_version}.md`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
    toast('变更记录已导出', 'success')
  }

  return (
    <>
      <ToastHost />
      <SidePanel title="材料分类" sub="点击浏览同类材料" foot={<span>变更历史按材料维度记录，切换材料请从材料库进入。</span>}>
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
          <CategoryTree nodes={categories.data?.items ?? []} selectedId={material.data?.category_id ?? null} onSelect={(id) => navigate(id == null ? '/materials' : `/materials?cat=${id}`)} />
        )}
      </SidePanel>

      <main className="ms-main">
        <div className="ms-page-header">
          <div>
            <h1 className="ms-page-header__title">变更历史 · {material.data?.name ?? '载入中'}</h1>
            <div className="ms-page-header__sub">共 {list.length} 个版本 · 单机版不记录账号，仅记录时间与操作类型</div>
          </div>
          <div className="ms-page-header__actions">
            <div className="ms-row ms-gap-3" style={{ flexWrap: 'wrap' }}>
              {list.map((r) => {
                const isCur = r.version === (list[list.length - 1]?.version ?? 0)
                const isActive = r.version === toVersion
                return (
                  <button
                    key={r.id}
                    className={`ms-btn ms-btn--sm ${isActive ? 'ms-btn--primary' : 'ms-btn--secondary'}`}
                    style={{ fontFamily: 'var(--font-mono)' }}
                    onClick={() => setToVersion(r.version)}
                    title={`${formatTime(r.changed_at, true)} · ${r.summary}`}
                  >
                    v{r.version}
                    {isCur ? ' 当前' : ''}
                  </button>
                )
              })}
            </div>
            <button className="ms-btn ms-btn--secondary" onClick={() => navigate(`/materials/${uid}`)}>
              返回材料详情
            </button>
          </div>
        </div>

        {revisions.isError ? (
          <Notice tone="danger">
            <div className="ms-col" style={{ gap: 6 }}>
              <span>变更历史加载失败：{revisions.error instanceof Error ? revisions.error.message : '未知错误'}</span>
              <button className="ms-link" style={{ background: 'none', border: 'none', alignSelf: 'flex-start' }} onClick={() => revisions.refetch()}>
                重试
              </button>
            </div>
          </Notice>
        ) : revisions.isLoading ? (
          <div className="ms-col" style={{ gap: 'var(--sp-4)' }}>
            <Skeleton height={36} />
            <Skeleton height={52} />
            <Skeleton height={52} />
            <Skeleton height={52} />
          </div>
        ) : list.length === 0 ? (
          <EmptyState
            icon="fileText"
            title="该材料还没有变更记录"
            desc="首次保存后系统会生成版本快照，之后的每次修改都会留下可对比的 diff。"
            action={
              <button className="ms-btn ms-btn--primary" onClick={() => navigate(`/materials/${uid}/edit`)}>
                <Icon name="edit" size={14} />
                编辑材料
              </button>
            }
          />
        ) : !from ? (
          <EmptyState icon="fileText" title="这是第一个版本" desc="没有更早的版本可对比，修改一次材料后即可看到逐字段 diff。" />
        ) : diff.isError ? (
          <Notice tone="danger">
            <div className="ms-col" style={{ gap: 6 }}>
              <span>diff 加载失败：{diff.error instanceof Error ? diff.error.message : '未知错误'}</span>
              <button className="ms-link" style={{ background: 'none', border: 'none', alignSelf: 'flex-start' }} onClick={() => diff.refetch()}>
                重试
              </button>
            </div>
          </Notice>
        ) : diff.isLoading || !diff.data ? (
          <div className="ms-col" style={{ gap: 'var(--sp-4)' }}>
            <Skeleton height={36} />
            <Skeleton height={52} />
            <Skeleton height={52} />
            <Skeleton height={52} />
          </div>
        ) : (
          <>
            <Notice tone="info">
              <span className="ms-row ms-gap-4" style={{ flexWrap: 'wrap' }}>
                <span>本次修改了 {diff.data.rows.length} 个字段</span>
                <span className="ms-mono">{formatTime(to?.changed_at, true)}</span>
                <span className="ms-mono">
                  版本 v{diff.data.from_version} → v{diff.data.to_version}
                </span>
                <span>变更说明：{diff.data.summary || '—'}</span>
              </span>
            </Notice>

            <div className="ms-diff">
              {diff.data.rows.length === 0 ? (
                <EmptyState compact icon="check" title="这两个版本之间没有字段差异" desc="可能只更新了来源或备注等非关键字段。" />
              ) : (
                diff.data.rows.map((r, i) => <DiffRow key={`${r.field}-${r.key}-${i}`} row={r} />)
              )}
            </div>

            <div className="ms-card ms-card--flat">
              <div className="ms-compare-foot">
                <span>
                  共 {diff.data.rows.length} 个字段变更 · 快照保留最近 20 个版本（可在设置中调整）
                </span>
                <div className="ms-row ms-gap-4">
                  <button className="ms-btn ms-btn--ghost" onClick={exportRecord}>
                    <Icon name="download" size={14} />
                    导出变更记录
                  </button>
                  <button className="ms-btn ms-btn--secondary" onClick={() => setConfirmRestore(to!.id)}>
                    恢复到此版本
                  </button>
                </div>
              </div>
            </div>
          </>
        )}
      </main>

      <Modal
        open={confirmRestore != null}
        title="恢复到此版本"
        width={460}
        onClose={() => setConfirmRestore(null)}
        footer={
          <>
            <span className="ms-muted" style={{ fontSize: 'var(--fs-caption)' }}>
              恢复会保留历史，不会丢失旧版本
            </span>
            <div className="ms-row ms-gap-3">
              <button className="ms-btn ms-btn--ghost" onClick={() => setConfirmRestore(null)} disabled={restore.isPending}>
                取消
              </button>
              <button className="ms-btn ms-btn--primary" onClick={() => confirmRestore != null && restore.mutate(confirmRestore)} disabled={restore.isPending}>
                {restore.isPending && <span className="ms-spin" style={{ color: '#fff' }} />}
                确认恢复
              </button>
            </div>
          </>
        }
      >
        <span>
          将以 v{list.find((r) => r.id === confirmRestore)?.version ?? '?'} 的内容覆盖当前 v
          {list[list.length - 1]?.version ?? '?'}，并生成新的快照版本。
        </span>
      </Modal>
    </>
  )
}
