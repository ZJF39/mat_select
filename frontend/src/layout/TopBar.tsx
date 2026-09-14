import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { Icon } from '../icons'

/**
 * 顶栏（原型 02 §0.1）
 * - 品牌 / 全局搜索（Ctrl+K 聚焦、输入即搜防抖 200ms、Enter 跳材料库、Esc 清空）
 * - 右侧：导入材料包 / 导出 快捷入口 + 本机备份状态
 */

/** 全局搜索结果项（材料 / 任务 / 场景 三类统一形状，sub 可选） */
interface SearchItem {
  kind: string
  label: string
  sub?: string
  to: string
}
export function TopBar() {
  const navigate = useNavigate()
  const inputRef = useRef<HTMLInputElement>(null)
  const [text, setText] = useState('')
  const [debounced, setDebounced] = useState('')
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)

  // Ctrl/Cmd + K 聚焦
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        inputRef.current?.focus()
        inputRef.current?.select()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  // 输入防抖 200ms（原型 05 §5）
  useEffect(() => {
    const t = window.setTimeout(() => setDebounced(text.trim()), 200)
    return () => window.clearTimeout(t)
  }, [text])

  const { data } = useQuery({
    queryKey: ['search', debounced],
    queryFn: () => api.search(debounced, 8),
    enabled: debounced.length > 0,
    staleTime: 15_000,
  })

  const flat = useMemo<SearchItem[]>(() => {
    if (!data) return []
    return [
      ...data.materials.map((m) => ({
        kind: '材料',
        label: m.name,
        sub: m.category_name ?? undefined,
        to: `/materials/${m.uid}`,
      })),
      ...data.tasks.map((t) => ({ kind: '选型任务', label: t.title, to: `/tasks/${t.id}` })),
      ...data.scenes.map((s) => ({
        kind: '应用场景',
        label: s,
        to: `/materials?q=${encodeURIComponent(s)}`,
      })),
    ]
  }, [data])

  const go = (to: string) => {
    setOpen(false)
    setText('')
    navigate(to)
  }

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Escape') {
      setText('')
      setOpen(false)
      inputRef.current?.blur()
      return
    }
    if (e.key === 'Enter') {
      if (flat[active]) go(flat[active].to)
      else if (text.trim()) go(`/materials?q=${encodeURIComponent(text.trim())}`)
      return
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActive((a) => Math.min(a + 1, Math.max(flat.length - 1, 0)))
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActive((a) => Math.max(a - 1, 0))
    }
  }

  const backup = useQuery({
    queryKey: ['backup-status'],
    queryFn: () => api.backupStatus(),
    staleTime: 60_000,
    retry: 0,
  })

  const backupText = backup.data?.last_backup_at
    ? `本机数据已备份 · ${backup.data.last_backup_at.slice(5, 16).replace('T', ' ')}`
    : '本机数据未备份'

  return (
    <header className="ms-topbar">
      <div className="ms-topbar__brand">
        <div className="ms-topbar__logo">
          <Icon name="layers" size={16} />
        </div>
        <div className="ms-topbar__brandtext">
          <span className="ms-topbar__name">MatSelect</span>
          <span className="ms-topbar__slogan">材料选型工作台</span>
        </div>
      </div>

      <div style={{ position: 'relative', flex: 1, minWidth: 0, maxWidth: 560 }}>
        <div className="ms-topbar__search">
          <Icon name="search" size={14} style={{ color: 'var(--text-6)' }} />
          <input
            ref={inputRef}
            value={text}
            aria-label="全局搜索"
            placeholder="搜索材料名称 / 别名 / 牌号 / 应用场景，例如 PP、PA66+GF30、保险丝座"
            onChange={(e) => {
              setText(e.target.value)
              setOpen(true)
              setActive(0)
            }}
            onFocus={() => setOpen(true)}
            onBlur={() => window.setTimeout(() => setOpen(false), 150)}
            onKeyDown={onKeyDown}
          />
          <span className="ms-kbd">Ctrl K</span>
        </div>

        {open && debounced && flat.length > 0 && (
          <div className="ms-searchpop" role="listbox">
            {flat.map((it, i) => (
              <div
                key={`${it.kind}-${it.label}-${i}`}
                role="option"
                aria-selected={i === active}
                data-active={i === active}
                className="ms-searchpop__item"
                onMouseDown={(e) => {
                  e.preventDefault()
                  go(it.to)
                }}
                onMouseEnter={() => setActive(i)}
              >
                <span className="ms-chip">{it.kind}</span>
                <span className="ms-ellipsis">{it.label}</span>
                {it.sub && <span className="ms-muted" style={{ marginLeft: 'auto' }}>{it.sub}</span>}
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="ms-topbar__actions">
        <button className="ms-btn ms-btn--sm ms-btn--secondary" onClick={() => navigate('/data')}>
          <Icon name="upload" size={14} />
          导入材料包
        </button>
        <button className="ms-btn ms-btn--sm ms-btn--secondary" onClick={() => navigate('/data')}>
          <Icon name="download" size={14} />
          导出
        </button>
        <span className="ms-topbar__sep" />
        <span className="ms-topbar__backup" title={backup.data?.location}>
          <span className={backup.data?.last_backup_at ? 'ms-dot' : 'ms-dot ms-dot--off'} />
          {backupText}
        </span>
      </div>
    </header>
  )
}

export default TopBar
