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
    <Tooltip title="接口已配置，但当前请求暂未返回有效数据；可能仍在生成、超时、无结果或服务暂时不可用。">
      <Tag color="gold" style={{ marginLeft: 8, cursor: 'help' }}>
        等待服务返回
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
