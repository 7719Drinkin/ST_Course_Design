import { useEffect, useMemo, useState } from 'react'
import { Space, Tag, Typography } from 'antd'
import { getDashboard } from '../services/api'
import { useAppStore } from '../store/appStore'
import type { DashboardSummary } from '../types'

const { Text } = Typography

function summaryFromStore(
  requirements: { requirement_id: string }[],
  testCases: unknown[],
  riskEntries: { level: string }[],
): DashboardSummary {
  return {
    total_requirements: requirements.length,
    generated_tests: testCases.length,
    high_risk_count: riskEntries.filter((e) => e.level === 'High').length,
    ci_status: 'passing',
  }
}

export function PipelineSummary() {
  const requirements = useAppStore((s) => s.requirements)
  const testCases = useAppStore((s) => s.testCases)
  const riskEntries = useAppStore((s) => s.riskEntries)
  const [remote, setRemote] = useState<DashboardSummary | null>(null)

  useEffect(() => {
    getDashboard().then((r) => setRemote(r.data.summary))
  }, [])

  const local = useMemo(
    () => summaryFromStore(requirements, testCases, riskEntries),
    [requirements, testCases, riskEntries],
  )

  const s =
    requirements.length > 0 || testCases.length > 0
      ? {
          ...local,
          total_requirements: requirements.length || local.total_requirements,
          high_risk_count:
            riskEntries.length > 0
              ? riskEntries.filter((e) => e.level === 'High').length
              : local.high_risk_count,
        }
      : remote ?? local

  return (
    <Space size="middle" wrap className="pipeline-summary">
      <Text type="secondary">需求 {s.total_requirements}</Text>
      <Text type="secondary">用例 {s.generated_tests}</Text>
      <Text type="secondary">高风险 {s.high_risk_count}</Text>
      <Tag color={s.ci_status === 'passing' ? 'success' : 'warning'}>{s.ci_status}</Tag>
    </Space>
  )
}
