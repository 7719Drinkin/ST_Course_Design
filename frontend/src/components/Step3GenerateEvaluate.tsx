import { useEffect, useMemo, useState } from 'react'
import {
  Button,
  Card,
  Col,
  Input,
  Row,
  Select,
  Space,
  Spin,
  Table,
  Tag,
  Typography,
} from 'antd'
import { useAppStore } from '../store/appStore'
import { generateFSM, getOracleResults, getTestCases } from '../services/api'
import type { RiskLevel, TestCaseStatus } from '../types'
import { DataStatusTag } from './shared'
import { RevisionPanel } from './RevisionPanel'

const { Title, Text } = Typography

export function Step3GenerateEvaluate() {
  const [tcLive, setTcLive] = useState<boolean>()
  const [tcPending, setTcPending] = useState<string>()
  const [fsmLive, setFsmLive] = useState<boolean>()
  const [statusFilter, setStatusFilter] = useState<TestCaseStatus | 'all'>('all')

  const requirements = useAppStore((s) => s.requirements)
  const testCases = useAppStore((s) => s.testCases)
  const setTestCases = useAppStore((s) => s.setTestCases)
  const updateTestCase = useAppStore((s) => s.updateTestCase)
  const oracleResults = useAppStore((s) => s.oracleResults)
  const setOracleResults = useAppStore((s) => s.setOracleResults)
  const fsm = useAppStore((s) => s.fsm)
  const setFsm = useAppStore((s) => s.setFsm)
  const highlightedRequirementId = useAppStore((s) => s.highlightedRequirementId)
  const setHighlightedRequirementId = useAppStore((s) => s.setHighlightedRequirementId)
  const setCurrentStep = useAppStore((s) => s.setCurrentStep)

  const reqIdsKey = requirements.map((r) => r.requirement_id).join(',')

  useEffect(() => {
    const ids = reqIdsKey ? reqIdsKey.split(',') : undefined
    getTestCases(ids).then((r) => {
      const cases = r.data.map((c) => ({ ...c, status: c.status ?? 'Draft' }))
      setTestCases(cases)
      setTcLive(r.isLive)
      setTcPending(r.pendingFrom)
      getOracleResults(cases.map((c) => c.test_id)).then((o) => setOracleResults(o.data))
    })
    const fsmIds = ids?.length ? ids : ['REQ-AUT-008']
    generateFSM(fsmIds).then((r) => {
      setFsm(r.data)
      setFsmLive(r.isLive)
    })
  }, [reqIdsKey, setTestCases, setOracleResults, setFsm])

  const oracleMap = useMemo(() => {
    const m = new Map<string, (typeof oracleResults)[0]>()
    oracleResults.forEach((o) => m.set(o.test_id, o))
    return m
  }, [oracleResults])

  const filteredCases = testCases.filter((tc) =>
    statusFilter === 'all' ? true : tc.status === statusFilter,
  )

  return (
    <Space direction="vertical" size={24} className="full-width">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
        <span>
          <Title level={4} style={{ margin: 0, display: 'inline' }}>生成与复核 (FR3/4/5)</Title>
          <DataStatusTag isLive={tcLive} pendingFrom={tcPending} />
        </span>
        <Space>
          <Select
            value={statusFilter}
            style={{ width: 140 }}
            onChange={setStatusFilter}
            options={[
              { value: 'all', label: '全部状态' },
              { value: 'Draft', label: 'Draft' },
              { value: 'Approved', label: 'Approved' },
              { value: 'Rejected', label: 'Rejected' },
            ]}
          />
          <Button type="primary" onClick={() => setCurrentStep(3)}>下一步: 优化与导出</Button>
        </Space>
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={16}>
          <Card title="测试用例池 · Designer Review (FR3.0)">
            <Table
              rowKey="test_id"
              size="small"
              pagination={{ pageSize: 6 }}
              dataSource={filteredCases}
              rowClassName={(record) =>
                record.requirement_id === highlightedRequirementId ? 'row-highlight' : ''
              }
              columns={[
                {
                  title: 'Req ID',
                  dataIndex: 'requirement_id',
                  width: 120,
                  render: (id: string) => (
                    <Button type="link" size="small" onClick={() => setHighlightedRequirementId(id)}>
                      {id}
                    </Button>
                  ),
                },
                { title: 'Technique', dataIndex: 'technique', width: 80, render: (v) => <Tag>{v}</Tag> },
                {
                  title: 'Expected Result',
                  dataIndex: 'expected_result',
                  render: (v, record) => (
                    <Input
                      size="small"
                      value={v}
                      onChange={(e) =>
                        updateTestCase(record.test_id, { expected_result: e.target.value })
                      }
                    />
                  ),
                },
                {
                  title: 'Risk',
                  dataIndex: 'risk_level',
                  width: 100,
                  render: (v: RiskLevel, record) => (
                    <Select
                      size="small"
                      value={v}
                      style={{ width: 90 }}
                      onChange={(level) => updateTestCase(record.test_id, { risk_level: level })}
                      options={['High', 'Medium', 'Low'].map((x) => ({ value: x, label: x }))}
                    />
                  ),
                },
                {
                  title: 'Confidence',
                  width: 90,
                  render: (_, record) => {
                    const o = oracleMap.get(record.test_id)
                    if (!o) return <Tag>—</Tag>
                    return (
                      <Tag color={o.confidence >= 0.85 ? 'green' : o.confidence >= 0.7 ? 'gold' : 'volcano'}>
                        {o.confidence.toFixed(2)}
                      </Tag>
                    )
                  },
                },
                {
                  title: 'Status',
                  width: 200,
                  render: (_, record) => (
                    <Space size="small">
                      {(['Approved', 'Rejected', 'Draft'] as TestCaseStatus[]).map((s) => (
                        <Button
                          key={s}
                          size="small"
                          type={record.status === s ? 'primary' : 'default'}
                          danger={s === 'Rejected'}
                          onClick={() => updateTestCase(record.test_id, { status: s })}
                        >
                          {s}
                        </Button>
                      ))}
                    </Space>
                  ),
                },
              ]}
            />
            {highlightedRequirementId && (
              <Text type="secondary" style={{ fontSize: 12, marginTop: 8, display: 'block' }}>
                追溯高亮：{highlightedRequirementId}
                <Button type="link" size="small" onClick={() => setHighlightedRequirementId(null)}>清除</Button>
              </Text>
            )}
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card title="FSM (FR4.0)">
            <DataStatusTag isLive={fsmLive} />
            {fsm ? <pre className="mermaid-block">{fsm.mermaid}</pre> : <Spin />}
          </Card>
        </Col>
      </Row>

      <RevisionPanel />
    </Space>
  )
}
