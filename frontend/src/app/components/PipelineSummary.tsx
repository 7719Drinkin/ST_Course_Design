import { useMemo } from 'react'
import { Space, Tag, Typography } from 'antd'
import { useAppStore } from '@/app/store/appStore'
import type { DashboardSummary } from '@/shared/types'

const { Text } = Typography

function summaryFromStore(
  requirements: { requirement_id: string }[],
  testCases: { status?: string }[],
  riskEntries: { level: string }[],
  revisionCount: number,
): DashboardSummary {
  return {
    total_requirements: requirements.length,
    generated_tests: testCases.length,
    high_risk_count: riskEntries.filter((entry) => entry.level === 'High').length,
    revision_count: revisionCount,
    approved_count: testCases.filter((testCase) => testCase.status === 'Approved').length,
    ci_status: 'ready',
  }
}

export function PipelineSummary() {
  const requirements = useAppStore((s) => s.requirements)
  const testCases = useAppStore((s) => s.testCases)
  const riskEntries = useAppStore((s) => s.riskEntries)
  const revisions = useAppStore((s) => s.revisions)

  const summary = useMemo(
    () => summaryFromStore(requirements, testCases, riskEntries, revisions.length),
    [requirements, testCases, riskEntries, revisions.length],
  )

  return (
    <Space size="middle" wrap className="pipeline-summary">
      <Text type="secondary">需求 {summary.total_requirements}</Text>
      <Text type="secondary">用例 {summary.generated_tests}</Text>
      <Text type="secondary">修订 {summary.revision_count}</Text>
      <Text type="secondary">通过 {summary.approved_count}</Text>
      <Tag color={summary.high_risk_count > 0 ? 'red' : 'success'}>
        高风险 {summary.high_risk_count}
      </Tag>
    </Space>
  )
}
