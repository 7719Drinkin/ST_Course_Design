import type { ReactNode } from 'react'
import { Tag, Tooltip, Typography } from 'antd'

const { Paragraph, Title } = Typography

export function DataStatusTag({
  isLive,
}: {
  isLive?: boolean
}) {
  if (isLive === undefined) return null
  if (isLive) return <Tag color="green" style={{ marginLeft: 8 }}>已连接</Tag>
  return (
    <Tooltip title="部分服务暂未接入，当前结果可能为空或等待生成。">
      <Tag color="orange" style={{ marginLeft: 8, cursor: 'help' }}>
        服务待接入
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
