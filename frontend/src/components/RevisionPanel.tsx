import { Card, List, Typography } from 'antd'
import { useAppStore } from '../store/appStore'

const { Text } = Typography

export function RevisionPanel() {
  const revisions = useAppStore((s) => s.revisions)
  if (revisions.length === 0) return null

  return (
    <Card title={`修订记录 (${revisions.length})`} size="small" className="revision-panel">
      <List
        size="small"
        dataSource={[...revisions].reverse().slice(0, 8)}
        renderItem={(r) => (
          <List.Item>
            <Text type="secondary" style={{ fontSize: 12 }}>
              {r.id} · Step {r.step + 1} · {r.entity_type} · {r.entity_id}
            </Text>
            <br />
            <Text style={{ fontSize: 12 }}>
              {r.field}: <Text delete>{r.old_value}</Text> → <Text strong>{r.new_value}</Text>
            </Text>
          </List.Item>
        )}
      />
    </Card>
  )
}
