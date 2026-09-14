import { useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api, downloadExport } from '../api/client'
import type { ImportPreview } from '../api/types'
import { ExportPanel, type ExportFormat, type ExportScope } from '../components/ExportPanel'
import { ImportPanel, type ConflictPolicy } from '../components/ImportPanel'
import { Notice } from '../components/Notice'
import { Icon } from '../icons'
import { toast, ToastHost } from '../components/Toast'
import { formatTime } from '../utils/format'
import './pages.css'

/** 09 · 数据导出 / 导入（原型 02 §09）
 *  分享闭环：导出（E1）+ 导入（E2）才构成完整闭环；校验失败必须拒绝且不写库。 */

export default function DataPage() {
  const qc = useQueryClient()
  const [exporting, setExporting] = useState(false)
  const [parsing, setParsing] = useState(false)
  const [committing, setCommitting] = useState(false)
  const [preview, setPreview] = useState<ImportPreview | null>(null)
  const [importError, setImportError] = useState<string | null>(null)

  const materials = useQuery({
    queryKey: ['materials', { page: 1, page_size: 1 }],
    queryFn: () => api.listMaterials({ page: 1, page_size: 1 }),
    staleTime: 30_000,
  })
  const tasks = useQuery({
    queryKey: ['tasks', 'active'],
    queryFn: () => api.listTasks({ status: 'active' }),
    staleTime: 30_000,
  })
  const logs = useQuery({
    queryKey: ['logs', 20],
    queryFn: () => api.listLogs(20),
    staleTime: 15_000,
  })

  const totalCount = materials.data?.total ?? 0
  const latestTask = tasks.data?.items?.[0] ?? null
  const recentExports = useMemo(
    () => (logs.data?.items ?? []).filter((l) => l.action === '导出').slice(0, 3),
    [logs.data],
  )

  const onExport = async (body: {
    scope: ExportScope
    format: ExportFormat
    include_work_data: boolean
    ids?: string[]
  }) => {
    if (body.scope === 'selected') {
      toast('「手动勾选的材料」请在材料库表格视图中勾选后再导出', 'danger')
      return
    }
    if (body.scope === 'shortlist' && !latestTask) {
      toast('还没有选型任务，无法导出待选清单', 'danger')
      return
    }
    setExporting(true)
    try {
      const filename = await downloadExport({
        scope: body.scope,
        format: body.format,
        include_work_data: body.include_work_data,
        task_id: body.scope === 'shortlist' ? latestTask?.id : undefined,
      })
      toast(`已导出到下载目录：${filename}`, 'success')
      qc.invalidateQueries({ queryKey: ['logs'] })
    } catch (e) {
      toast(e instanceof Error ? e.message : '导出失败，请重试', 'danger')
    } finally {
      setExporting(false)
    }
  }

  const onFile = async (file: File) => {
    setImportError(null)
    setPreview(null)
    if (!file.name.toLowerCase().endsWith('.json')) {
      setImportError('仅支持 .json 材料包（E1 导出的产物）')
      return
    }
    setParsing(true)
    try {
      const prev = await api.parseImport(file)
      setPreview(prev)
    } catch (e) {
      setImportError(e instanceof Error ? e.message : '解析失败，请重新选择文件')
    } finally {
      setParsing(false)
    }
  }

  const onCommit = async (policy: ConflictPolicy) => {
    if (!preview) return
    setCommitting(true)
    setImportError(null)
    try {
      const res = await api.commitImport(preview.token, policy)
      toast(res.message || '导入完成', 'success')
      setPreview(null)
      qc.invalidateQueries({ queryKey: ['materials'] })
      qc.invalidateQueries({ queryKey: ['categories'] })
      qc.invalidateQueries({ queryKey: ['logs'] })
    } catch (e) {
      setImportError(e instanceof Error ? e.message : '导入失败，未写入任何数据')
    } finally {
      setCommitting(false)
    }
  }

  return (
    <>
      <ToastHost />
      <main className="ms-main">
        <div className="ms-page-header">
          <div>
            <h1 className="ms-page-header__title">数据分享</h1>
            <div className="ms-page-header__sub">
              本机共 {totalCount} 条材料 · JSON 可被同事再导入，Excel / Markdown 便于阅读
            </div>
          </div>
        </div>

        <Notice tone="info">
          材料包内嵌包版本、导出时间、条数与<strong>校验和</strong>；导入时先本地校验（版本 / 校验和 / 必填字段），
          <strong>校验不通过直接拒绝且不写入任何数据</strong>，不会产生半截数据。
        </Notice>

        <div className="ms-data-grid">
          <ExportPanel
            totalCount={totalCount}
            filteredCount={totalCount}
            shortlistCount={latestTask?.shortlist_count ?? 0}
            selectedCount={0}
            exporting={exporting}
            onExport={onExport}
          />
          <ImportPanel
            preview={preview}
            parsing={parsing}
            committing={committing}
            error={importError}
            onFile={onFile}
            onCommit={onCommit}
            onClear={() => {
              setPreview(null)
              setImportError(null)
            }}
          />
        </div>

        <div className="ms-card">
          <div className="ms-card__title">
            <span>最近导出记录</span>
            <button
              className="ms-btn ms-btn--ghost"
              onClick={async () => {
                try {
                  const r = await api.runBackup()
                  toast(`已备份到 ${r.location}`, 'success')
                  qc.invalidateQueries({ queryKey: ['backup-status'] })
                } catch {
                  toast('备份失败，请重试', 'danger')
                }
              }}
            >
              <Icon name="database" size={14} />
              立即备份本机数据
            </button>
          </div>
          {logs.isLoading ? (
            <div className="ms-col" style={{ gap: 8 }}>
              <span className="ms-mono ms-muted">加载中…</span>
            </div>
          ) : recentExports.length === 0 ? (
            <div className="ms-col" style={{ gap: 4 }}>
              <span className="ms-muted-aa" style={{ fontSize: 'var(--fs-small)' }}>
                还没有导出过。导出的材料包同时可作为冷备份手段。
              </span>
            </div>
          ) : (
            <div className="ms-col" style={{ gap: 6 }}>
              {recentExports.map((l, i) => (
                <div key={i} className="ms-row ms-gap-4" style={{ fontSize: 'var(--fs-small)' }}>
                  <span className="ms-mono ms-muted" style={{ width: 130 }}>
                    {formatTime(l.at, true)}
                  </span>
                  <span className="ms-mono">{l.target}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </>
  )
}
