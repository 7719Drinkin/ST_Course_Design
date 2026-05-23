import { useEffect, useId, useRef, useState } from 'react'
import { Spin, Typography } from 'antd'

const { Text } = Typography

let mermaidReady = false

async function renderMermaid(container: HTMLElement, chart: string, renderId: string) {
  const mermaid = (await import('mermaid')).default
  if (!mermaidReady) {
    mermaid.initialize({ startOnLoad: false, theme: 'neutral', securityLevel: 'loose' })
    mermaidReady = true
  }
  const { svg } = await mermaid.render(renderId, chart)
  container.innerHTML = svg
}

export function MermaidView({ chart }: { chart: string }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const reactId = useId().replace(/:/g, '')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const el = containerRef.current
    if (!el || !chart.trim()) return
    setLoading(true)
    setError(null)
    renderMermaid(el, chart, `mmd-${reactId}-${Date.now()}`)
      .catch(() => setError('FSM 图渲染失败，已回退为源码展示'))
      .finally(() => setLoading(false))
  }, [chart, reactId])

  if (error) {
    return (
      <>
        <Text type="danger" style={{ fontSize: 12 }}>{error}</Text>
        <pre className="mermaid-block">{chart}</pre>
      </>
    )
  }

  return (
    <div className="mermaid-wrap">
      {loading && <Spin size="small" />}
      <div ref={containerRef} className="mermaid-render" style={{ opacity: loading ? 0.4 : 1 }} />
    </div>
  )
}
