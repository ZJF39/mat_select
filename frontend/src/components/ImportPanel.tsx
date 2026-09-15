import { useRef, useState } from 'react'
import type { ImportPreview, ImportDetail } from '../api/types'
import { Chip } from './Chip'
import { Icon } from '../icons'
import { Notice } from './Notice'
import { Skeleton } from './Skeleton'
import './ui.css'

export type ConflictPolicy = 'skip' | 'overwrite' | 'duplicate'

export interface ImportPanelProps {
  preview: ImportPreview | null
  parsing?: boolean
  committing?: boolean
  error?: string | null
  onFile: (file: File) => void
  onCommit: (policy: ConflictPolicy) => void
  onClear?: () => void
}

const POLICIES: { value: ConflictPolicy; label: string }[] = [
  { value: 'skip', label: '跳过 · 保留本机' },
  { value: 'overwrite', label: '覆盖 · 用导入值' },
  { value: 'duplicate', label: '另存副本 · 更名后新建' },
]

/** 导入材料包（09 屏右卡）：落地区 + 导入预览 + 冲突策略 + 确认导入。 */
export function ImportPanel({ preview, parsing, committing, error, onFile, onCommit, onClear }: ImportPanelProps) {
  const [over, setOver] = useState(false)
  const [policy, setPolicy] = useState<ConflictPolicy>('skip')
  const [expanded, setExpanded] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const stats: { kind: ImportDetail['kind']; label: string; tone: 'success' | 'info' | 'warning' | 'danger' }[] = [
    { kind: 'add', label: `新增 ${preview?.added ?? 0} 条`, tone: 'success' },
    { kind: 'update', label: `更新 ${preview?.updated ?? 0} 条`, tone: 'info' },
    { kind: 'conflict', label: `冲突 ${preview?.conflicted ?? 0} 条`, tone: 'warning' },
    { kind: 'invalid', label: `校验失败 ${preview?.invalid ?? 0} 条`, tone: 'danger' },
  ]

  return (
    <div className="ms-card">
      <div className="ms-card__title">导入材料包</div>
      <div className="ms-col" style={{ gap: 'var(--sp-6)' }}>
        <div
          className={`ms-dropzone${over ? ' ms-dropzone--over' : ''}`}
          onDragOver={(e) => {
            e.preventDefault()
            setOver(true)
          }}
          onDragLeave={() => setOver(false)}
          onDrop={(e) => {
            e.preventDefault()
            setOver(false)
            const f = e.dataTransfer.files?.[0]
            if (f) onFile(f)
          }}
          onClick={() => inputRef.current?.click()}
          role="button"
          tabIndex={0}
          aria-label="选择或拖入材料包"
          onKeyDown={(e) => e.key === 'Enter' && inputRef.current?.click()}
        >
          <Icon name="upload" size={22} style={{ color: 'var(--text-4)' }} />
          <div style={{ fontSize: 'var(--fs-body)', fontWeight: 'var(--fw-medium)', color: 'var(--text-3)' }}>
            拖入 .json 材料包，或点击选择文件
          </div>
          <div style={{ fontSize: 'var(--fs-caption)', color: 'var(--text-6)' }}>
            支持 E1 导出的材料包，也支持大模型输出的原始 JSON（自动补校验和）
          </div>
          {preview && (
            <div className="ms-mono" style={{ fontSize: 'var(--fs-caption)', color: 'var(--text-7)' }}>
              导出人 {preview.exported_by} · 校验和{preview.checksum_ok ? '正常' : '异常'}
            </div>
          )}
          <input ref={inputRef} type="file" accept=".json,application/json" style={{ display: 'none' }} onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])} />
        </div>

        {parsing && (
          <div className="ms-col" style={{ gap: 8 }} aria-busy="true" aria-live="polite">
            <span className="ms-muted" style={{ fontSize: 'var(--fs-caption)' }}>正在解析材料包并本地校验…</span>
            <Skeleton height={20} width="40%" />
            <Skeleton height={52} />
            <div className="ms-row ms-gap-3">
              <Skeleton height={30} width={104} />
              <Skeleton height={30} width={104} />
              <Skeleton height={30} width={104} />
              <Skeleton height={30} width={104} />
            </div>
          </div>
        )}
        {error && (
          <Notice tone="danger">
            <div className="ms-col" style={{ gap: 6 }}>
              <span>{error}</span>
              <button
                className="ms-link"
                style={{ background: 'none', border: 'none', alignSelf: 'flex-start' }}
                onClick={() => (preview ? onCommit(policy) : inputRef.current?.click())}
              >
                重试
              </button>
            </div>
          </Notice>
        )}
        {!error && preview && !preview.checksum_ok && (
          <Notice tone="danger">校验和异常，建议不要导入，避免数据不一致。</Notice>
        )}

        {preview && (
          <>
            <div className="ms-data__section">
              <div className="ms-data__step-label">导入预览（确认后才会写库）</div>
              <div className="ms-preview-stats">
                {stats.map((s) => (
                  <button
                    key={s.kind}
                    className="ms-chip ms-chip--30"
                    style={{ cursor: 'pointer', border: expanded === s.kind ? '1px solid var(--color-accent)' : '1px solid var(--border-control)', background: s.kind === 'add' ? 'var(--success-soft)' : s.kind === 'update' ? 'var(--info-soft)' : s.kind === 'conflict' ? 'var(--warning-soft)' : 'var(--danger-soft)', color: s.kind === 'add' ? 'var(--success-strong)' : s.kind === 'update' ? 'var(--info-text)' : s.kind === 'conflict' ? 'var(--warning-strong)' : 'var(--danger-strong)' }}
                    onClick={() => setExpanded((e) => (e === s.kind ? null : s.kind))}
                  >
                    {s.label}
                  </button>
                ))}
              </div>
              {expanded && (
                <div className="ms-col" style={{ gap: 4, marginTop: 8 }}>
                  {preview.details.filter((d) => d.kind === expanded).length === 0 && (
                    <span className="ms-muted" style={{ fontSize: 'var(--fs-small)' }}>无明细</span>
                  )}
                  {preview.details
                    .filter((d) => d.kind === expanded)
                    .map((d, i) => (
                      <div key={i} className="ms-row ms-gap-3" style={{ fontSize: 'var(--fs-small)' }}>
                        <span className="ms-ellipsis" style={{ flex: 1 }}>{d.name}</span>
                        {d.reason && <span className="ms-muted" style={{ color: 'var(--text-6)' }}>{d.reason}</span>}
                      </div>
                    ))}
                </div>
              )}
            </div>

            <div className="ms-data__section">
              <div className="ms-data__step-label">冲突处理策略（同一 uid 已存在时）</div>
              <div className="ms-chips-edit">
                {POLICIES.map((p) => (
                  <Chip key={p.value} size="26" selected={policy === p.value} onClick={() => setPolicy(p.value)}>
                    {p.label}
                  </Chip>
                ))}
              </div>
            </div>

            <Notice tone="info">
              导入完成后会自动重建全文检索索引与语义向量；冲突项可在预览列表中逐条改为对应策略。
            </Notice>

            <div className="ms-row" style={{ justifyContent: 'space-between' }}>
              <button className="ms-btn ms-btn--ghost" onClick={onClear}>取消</button>
              <button className="ms-btn ms-btn--primary" disabled={committing} onClick={() => onCommit(policy)}>
                {committing && <span className="ms-spin" style={{ color: '#fff' }} />}
                确认导入 {preview.added + preview.updated + preview.conflicted} 条
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

export default ImportPanel
