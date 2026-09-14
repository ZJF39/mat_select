import { useMemo, useState } from 'react'
import type { MaterialCard, FeedbackResult } from '../api/types'
import { Modal } from './Modal'
import { Chip } from './Chip'
import { Icon } from '../icons'
import './ui.css'

const RESULT_OPTS: { value: FeedbackResult; label: string }[] = [
  { value: 'success', label: '有帮助' },
  { value: 'fail', label: '没帮助' },
  { value: 'skipped', label: '暂不评价' },
]

const PROBLEM_TAGS = [
  '① 没有满足硬条件的材料',
  '② 推荐了不相关的材料',
  '③ 参数或数值有误',
  '④ 价格与实际不符',
  '⑤ 材料信息缺失，无法判断',
  '⑥ 其他',
]

export interface FeedbackModalProps {
  open: boolean
  triggerRef?: React.RefObject<HTMLElement>
  materials: MaterialCard[]
  taskTitle: string
  onClose: () => void
  onSubmit: (payload: { result: FeedbackResult; reason_text?: string; reason_tags?: string[]; material_uids?: string[] }) => void
  submitting?: boolean
}

/** 回评弹窗（06 屏失败态）：评价 + 失败理由(必填) + 问题类型 + 指向材料 + 拆解预览 + 校验。 */
export function FeedbackModal({ open, triggerRef, materials, taskTitle, onClose, onSubmit, submitting }: FeedbackModalProps) {
  const [result, setResult] = useState<FeedbackResult>('fail')
  const [reason, setReason] = useState('')
  const [tags, setTags] = useState<string[]>([])
  const [uids, setUids] = useState<string[]>([])
  const [touched, setTouched] = useState(false)

  const reasonError = result === 'fail' && reason.trim() === ''

  const toggleTag = (t: string) => setTags((s) => (s.includes(t) ? s.filter((x) => x !== t) : [...s, t]))
  const toggleUid = (u: string) => setUids((s) => (s.includes(u) ? s.filter((x) => x !== u) : [...s, u]))

  const preview = useMemo(() => {
    const names = materials.filter((m) => uids.includes(m.uid)).map((m) => m.name)
    const dims = tags.map((t) => t.replace(/^[①②③④⑤⑥]\s*/, ''))
    const kws = reason.replace(/[，。、；\s]+/g, ' ').split(' ').filter(Boolean).slice(0, 4)
    const conf = reason.trim() && tags.length ? 0.87 : 0.6
    return `涉及材料 [${names.join(' / ') || '—'}] · 问题维度 [${dims.join(' / ') || '—'}] · 关键词 [${kws.join(' / ') || '—'}] · 置信度 ${conf}`
  }, [materials, uids, tags, reason])

  const submit = () => {
    setTouched(true)
    if (reasonError) return
    onSubmit({ result, reason_text: reason.trim() || undefined, reason_tags: tags, material_uids: uids })
  }

  return (
    <Modal
      open={open}
      title="回评：标记失败"
      triggerRef={triggerRef}
      onClose={onClose}
      footer={
        <>
          <span className="ms-muted" style={{ fontSize: 'var(--fs-caption)' }}>
            回评对象：{taskTitle} · {new Date().toISOString().slice(0, 16).replace('T', ' ')}
          </span>
          <div className="ms-row ms-gap-3">
            <button className="ms-btn ms-btn--ghost" onClick={onClose} disabled={submitting}>取消</button>
            <button className="ms-btn ms-btn--primary" onClick={submit} disabled={submitting}>
              {submitting && <span className="ms-spin" style={{ color: '#fff' }} />}
              提交回评
            </button>
          </div>
        </>
      }
    >
      <div className="ms-col" style={{ gap: 'var(--sp-8)' }}>
        <div className="ms-col" style={{ gap: 'var(--sp-4)' }}>
          <div className="ms-field__label">本次推荐有帮助吗？</div>
          <div className="ms-row ms-gap-3">
            {RESULT_OPTS.map((o) => (
              <button
                key={o.value}
                className={`ms-chip ms-chip--26${result === o.value ? ' ms-chip--selected' : ''}`}
                style={{ height: 32, borderRadius: 'var(--radius-lg)', border: '1px solid var(--border-control)', background: result === o.value ? 'var(--color-accent-soft)' : 'var(--bg-surface)', cursor: 'pointer' }}
                onClick={() => setResult(o.value)}
              >
                {o.label}
              </button>
            ))}
          </div>
        </div>

        <div className="ms-col" style={{ gap: 'var(--sp-3)' }}>
          <div className="ms-field__label">
            失败理由（必填）<span className="ms-field__req"> *</span>
          </div>
          <textarea
            className={`ms-input${touched && reasonError ? ' ms-input--error' : ''}`}
            style={{ height: 72, padding: 10, resize: 'none', lineHeight: 19 }}
            placeholder="描述越具体越准；系统只做语义拆解入库，不会直接改写推荐规则。"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            onBlur={() => setTouched(true)}
            aria-invalid={touched && reasonError}
          />
          {touched && reasonError && <div className="ms-field__err">请填写失败理由</div>}
          <div className="ms-muted" style={{ fontSize: 'var(--fs-caption)' }}>
            描述越具体越准；系统只做语义拆解入库，不会直接改写推荐规则。
          </div>
        </div>

        <div className="ms-col" style={{ gap: 'var(--sp-4)' }}>
          <div className="ms-field__label">问题类型（可多选）</div>
          <div className="ms-chips-edit">
            {PROBLEM_TAGS.map((t) => (
              <Chip key={t} size="24" selected={tags.includes(t)} onClick={() => toggleTag(t)}>
                {t}
              </Chip>
            ))}
          </div>
        </div>

        {materials.length > 0 && (
          <div className="ms-col" style={{ gap: 'var(--sp-4)' }}>
            <div className="ms-field__label">指向材料（可选）</div>
            <div className="ms-chips-edit">
              {materials.map((m) => (
                <Chip key={m.uid} size="24" selected={uids.includes(m.uid)} onClick={() => toggleUid(m.uid)}>
                  {m.name}
                </Chip>
              ))}
            </div>
          </div>
        )}

        <div className="ms-info-block">
          <div className="ms-field__label" style={{ color: 'var(--text-6)' }}>
            提交后系统将拆解为（仅作反馈标签记录，不直接改写推荐规则）
          </div>
          <div className="ms-mono" style={{ fontSize: 'var(--fs-small)', color: 'var(--text-3)', marginTop: 4 }}>
            {preview}
          </div>
        </div>
      </div>
    </Modal>
  )
}

export default FeedbackModal
