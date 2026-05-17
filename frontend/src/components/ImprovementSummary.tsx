import { Card, Col, Row, Statistic, Typography } from 'antd'
import { useAppStore } from '../store/appStore'

const { Text } = Typography

export function ImprovementSummary() {
  const revisions = useAppStore((s) => s.revisions)
  const coverageItems = useAppStore((s) => s.coverageItems)
  const testCases = useAppStore((s) => s.testCases)
  const requirements = useAppStore((s) => s.requirements)

  const designerAddedCov = coverageItems.filter((c) => c.designer_added).length
  const approved = testCases.filter((t) => t.status === 'Approved').length
  const confirmedReq = requirements.filter((r) => r.designer_confirmed).length
  const byStep = [0, 1, 2].map((s) => revisions.filter((r) => r.step === s).length)

  if (revisions.length === 0 && designerAddedCov === 0) return null

  return (
    <Card title="改进证据 · Improvement with Evidence (Mainly)" size="small">
      <Row gutter={16}>
        <Col xs={12} sm={6}>
          <Statistic title="人工修订" value={revisions.length} />
        </Col>
        <Col xs={12} sm={6}>
          <Statistic title="已确认需求" value={confirmedReq} />
        </Col>
        <Col xs={12} sm={6}>
          <Statistic title="新增覆盖项" value={designerAddedCov} />
        </Col>
        <Col xs={12} sm={6}>
          <Statistic title="已批准用例" value={approved} />
        </Col>
      </Row>
      <Text type="secondary" style={{ fontSize: 12, marginTop: 8, display: 'block' }}>
        修订分布 — Step1: {byStep[0]} · Step2: {byStep[1]} · Step3: {byStep[2]}
      </Text>
    </Card>
  )
}
