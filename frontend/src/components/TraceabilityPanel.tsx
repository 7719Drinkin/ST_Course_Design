import { Card, List, Tag, Typography } from 'antd'
import { useAppStore } from '../store/appStore'

const { Text } = Typography

export function TraceabilityPanel() {
  const highlightedRequirementId = useAppStore((s) => s.highlightedRequirementId)
  const requirements = useAppStore((s) => s.requirements)
  const coverageItems = useAppStore((s) => s.coverageItems)
  const testCases = useAppStore((s) => s.testCases)

  if (!highlightedRequirementId) {
    return (
      <Card title="可追溯性 (Mainly)" size="small">
        <Text type="secondary" style={{ fontSize: 12 }}>
          在用例表中点击 Req ID，查看需求 → 覆盖项 → 用例链路。
        </Text>
      </Card>
    )
  }

  const req = requirements.find((r) => r.requirement_id === highlightedRequirementId)
  const cov = coverageItems.filter((c) => c.requirement_id === highlightedRequirementId)
  const tcs = testCases.filter((t) => t.requirement_id === highlightedRequirementId)

  return (
    <Card title={`追溯 · ${highlightedRequirementId}`} size="small" className="trace-panel">
      {req && (
        <Text style={{ fontSize: 12, display: 'block', marginBottom: 8 }}>
          {req.raw_requirement.slice(0, 120)}
          {req.raw_requirement.length > 120 ? '…' : ''}
        </Text>
      )}
      <Text strong style={{ fontSize: 12 }}>覆盖项 ({cov.length})</Text>
      <List
        size="small"
        dataSource={cov}
        locale={{ emptyText: '无覆盖项' }}
        renderItem={(c) => (
          <List.Item>
            <Tag>{c.coverage_item_id}</Tag>
            <Text style={{ fontSize: 12 }}>{c.techniques.join('/')}</Text>
          </List.Item>
        )}
      />
      <Text strong style={{ fontSize: 12 }}>关联用例 ({tcs.length})</Text>
      <List
        size="small"
        dataSource={tcs}
        locale={{ emptyText: '无用例' }}
        renderItem={(t) => (
          <List.Item>
            <Tag color={t.status === 'Approved' ? 'green' : undefined}>{t.test_id}</Tag>
            <Tag>{t.technique}</Tag>
          </List.Item>
        )}
      />
    </Card>
  )
}
