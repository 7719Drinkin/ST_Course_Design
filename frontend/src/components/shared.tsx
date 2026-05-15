import { Tag, Tooltip } from 'antd'

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
        Mock · 待接入
      </Tag>
    </Tooltip>
  )
}
