import { Card, List, Typography } from 'antd'
import { useAppStore } from '@/app/store/appStore'
import { SyncOutlined, CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons'

const { Text } = Typography

export function RevisionPanel() {
  const revisions = useAppStore((s) => s.revisions)
  if (revisions.length === 0) return null

  return (
    <Card title={`修订证据轨 (${revisions.length})`} size="small" className="revision-panel">
      <List
        size="small"
        dataSource={[...revisions].reverse().slice(0, 8)}
        renderItem={(r) => (
          <List.Item
            extra={
              r.syncStatus === 'saving' ? <SyncOutlined spin style={{ color: '#1677ff' }} />
                : r.syncStatus === 'saved' ? <CheckCircleOutlined style={{ color: '#52c41a' }} />
                  : r.syncStatus === 'failed' ? <CloseCircleOutlined style={{ color: '#ff4d4f' }} />
                    : null
            }
          >
            <Text type="secondary" style={{ fontSize: 12 }}>
              {r.id} · Stage {r.step + 1} · {r.entity_type} · {r.entity_id}
            </Text>
            <br />
            <Text style={{ fontSize: 12 }}>
              {r.field}: <Text delete>{r.old_value}</Text> → <Text strong>{r.new_value}</Text>
            </Text>
            {r.reason && (
              <Text type="secondary" style={{ display: 'block', fontSize: 12 }}>
                原因：{r.reason}
              </Text>
            )}
          </List.Item>
        )}
      />
    </Card>
  )
}
