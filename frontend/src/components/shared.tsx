import type { ReactNode } from 'react'
import { Tag, Tooltip, Typography } from 'antd'

const { Paragraph, Title } = Typography

export function DataStatusTag({
  isLive,
  pendingFrom,
}: {
  isLive?: boolean
  pendingFrom?: string
}) {
  if (isLive === undefined) return null
  if (isLive) return <Tag color="green" style={{ marginLeft: 8 }}>Live</Tag>
  return (
    <Tooltip title={`待对接：${pendingFrom}`}>
      <Tag color="orange" style={{ marginLeft: 8, cursor: 'help' }}>
        接口待接入
      </Tag>
    </Tooltip>
  )
}

export function WorkflowEmptyState({
  title,
  description,
  action,
}: {
  title: string
  description: string
  action?: ReactNode
}) {
  return (
    <div className="workflow-empty">
      <div className="workflow-empty-visual" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
      <div>
        <Title level={4}>{title}</Title>
        <Paragraph>{description}</Paragraph>
        {action && <div className="workflow-empty-action">{action}</div>}
      </div>
    </div>
  )
}
