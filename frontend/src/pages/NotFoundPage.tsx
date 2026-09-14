import { useNavigate } from 'react-router-dom'
import { EmptyState } from '../components/EmptyState'
import { Icon } from '../icons'
import './pages.css'

/** 全页空态（05 §2）：未匹配路由 → 返回材料库。 */
export default function NotFoundPage() {
  const navigate = useNavigate()
  return (
    <main className="ms-main">
      <EmptyState
        icon="search"
        title="页面不存在"
        desc="你访问的地址没有对应页面，返回材料库继续选材。"
        action={
          <button className="ms-btn ms-btn--primary" onClick={() => navigate('/materials')}>
            <Icon name="layers" size={14} />
            返回材料库
          </button>
        }
      />
    </main>
  )
}
