import { useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Col,
  Input,
  List,
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
import type { Technique, TestCaseStatus } from '../types'
import { DataStatusTag, WorkflowEmptyState } from './shared'
import { RevisionPanel } from './RevisionPanel'
import { MermaidView } from './MermaidView'
import { TraceabilityPanel } from './TraceabilityPanel'
import { ImprovementSummary } from './ImprovementSummary'

const { Title, Text } = Typography
const GENERATE_SLOW_MS = 2000

export function Step3GenerateEvaluate() {
  const [tcLive, setTcLive] = useState<boolean>()
  const [tcPending, setTcPending] = useState<string>()
  const [fsmLive, setFsmLive] = useState<boolean>()
  const [fetching, setFetching] = useState(false)
  const [slowWarning, setSlowWarning] = useState(false)
  const [statusFilter, setStatusFilter] = useState<TestCaseStatus | 'all'>('all')
  const [techniqueFilter, setTechniqueFilter] = useState<Technique | 'all'>('all')

  const requirements = useAppStore((s) => s.requirements)
  const coverageItems = useAppStore((s) => s.coverageItems)
  const testCases = useAppStore((s) => s.testCases)
  const setTestCases = useAppStore((s) => s.setTestCases)
  const updateTestCase = useAppStore((s) => s.updateTestCase)
  const oracleResults = useAppStore((s) => s.oracleResults)
  const setOracleResults = useAppStore((s) => s.setOracleResults)
  const fsm = useAppStore((s) => s.fsm)
  const setFsm = useAppStore((s) => s.setFsm)
  const fsmPathCoverage = useAppStore((s) => s.fsmPathCoverage)
  const setFsmPathCoverage = useAppStore((s) => s.setFsmPathCoverage)
  const highlightedRequirementId = useAppStore((s) => s.highlightedRequirementId)
  const setHighlightedRequirementId = useAppStore((s) => s.setHighlightedRequirementId)
  const setCurrentStep = useAppStore((s) => s.setCurrentStep)

  const reqIdsKey = requirements.map((r) => r.requirement_id).join(',')
  const hasRequirements = requirements.length > 0

  useEffect(() => {
    if (!reqIdsKey) {
      setTestCases([])
      setOracleResults([])
      setFsm(null)
      return
    }
    const ids = reqIdsKey.split(',')
    let active = true
    const slowTimer = window.setTimeout(() => {
      if (active) setSlowWarning(true)
    }, GENERATE_SLOW_MS)

    const load = async () => {
      setFetching(true)
      try {
        const r = await getTestCases(ids)
        if (!active) return
        const cases = r.data.map((c) => ({ ...c, status: c.status ?? 'Draft' }))
        setTestCases(cases)
        setTcLive(r.isLive)
        setTcPending(r.pendingFrom)
        if (cases.length === 0) {
          setOracleResults([])
          return
        }
        const o = await getOracleResults(cases.map((c) => c.test_id))
        if (active) setOracleResults(o.data)
      } finally {
        if (active) {
          window.clearTimeout(slowTimer)
          setFetching(false)
          setSlowWarning(false)
        }
      }
    }

    void load()

    generateFSM(ids).then((r) => {
      if (active) {
        setFsm(r.data)
        setFsmLive(r.isLive)
      }
    })

    return () => {
      active = false
      window.clearTimeout(slowTimer)
    }
  }, [reqIdsKey, setTestCases, setOracleResults, setFsm])

  const techniqueCounts = useMemo(() => {
    const counts: Record<string, number> = { EP: 0, BVA: 0, DT: 0, FSM: 0 }
    testCases.forEach((tc) => {
      counts[tc.technique] = (counts[tc.technique] ?? 0) + 1
    })
    return counts
  }, [testCases])

  const filteredCases = testCases.filter((tc) => {
    if (statusFilter !== 'all' && tc.status !== statusFilter) return false
    if (techniqueFilter !== 'all' && tc.technique !== techniqueFilter) return false
    if (highlightedRequirementId && tc.requirement_id !== highlightedRequirementId) return false
    return true
  })

  const fsmPaths = useMemo(() => {
    if (!fsm) return []
    const statePaths = fsm.coverage.all_states.map((s) => `state:${s}`)
    const transPaths = fsm.coverage.all_transitions.map((t) => `transition:${t}`)
    return [...statePaths, ...transPaths]
  }, [fsm])

  const needsReviewCases = oracleResults.filter((o) => o.needs_review)

  return (
    <Space direction="vertical" size={24} className="full-width">
      <div className="stage-toolbar stage-toolbar-wrap">
        <span>
          <Title level={4} style={{ margin: 0, display: 'inline' }}>生成与复核 (FR3/4/5)</Title>
          {hasRequirements && <DataStatusTag isLive={tcLive} pendingFrom={tcPending} />}
        </span>
        <Space wrap>
          {(['EP', 'BVA', 'DT', 'FSM'] as Technique[]).map((t) => (
            <Tag key={t}>{t}: {techniqueCounts[t] ?? 0}</Tag>
          ))}
          <Select
            value={techniqueFilter}
            style={{ width: 120 }}
            onChange={setTechniqueFilter}
            options={[
              { value: 'all', label: '全部技术' },
              { value: 'EP', label: 'EP' },
              { value: 'BVA', label: 'BVA' },
              { value: 'DT', label: 'DT' },
              { value: 'FSM', label: 'FSM' },
            ]}
          />
          <Select
            value={statusFilter}
            style={{ width: 130 }}
            onChange={setStatusFilter}
            options={[
              { value: 'all', label: '全部状态' },
              { value: 'Draft', label: 'Draft' },
              { value: 'Approved', label: 'Approved' },
              { value: 'Rejected', label: 'Rejected' },
            ]}
          />
          <Button type="primary" disabled={!hasRequirements} onClick={() => setCurrentStep(3)}>
            下一步: 优化与导出
          </Button>
        </Space>
      </div>

      {!hasRequirements ? (
        <WorkflowEmptyState
          title="等待需求生成测试用例"
          description="解析真实需求后，系统才会请求用例生成、Oracle 复核和 FSM 覆盖数据。当前不会展示任何示例用例。"
        />
      ) : slowWarning && fetching ? (
        <Alert
          type="warning"
          showIcon
          message="用例生成超过 2s（NFR 目标），请稍后；后端联调后可优化性能。"
        />
      ) : null}

      {hasRequirements && <Row gutter={[16, 16]}>
        <Col xs={24} lg={16}>
          <Card title="测试用例池 · Designer Review (FR3.0)">
            <Spin spinning={fetching}>
              <Table
                rowKey="test_id"
                size="small"
                pagination={{ pageSize: 5 }}
                dataSource={filteredCases}
                scroll={{ x: 1100 }}
                rowClassName={(record) =>
                  record.requirement_id === highlightedRequirementId ? 'row-highlight' : ''
                }
                columns={[
                  { title: 'ID', dataIndex: 'test_id', width: 120, ellipsis: true },
                  {
                    title: 'Req',
                    dataIndex: 'requirement_id',
                    width: 108,
                    render: (id: string) => (
                      <Button type="link" size="small" onClick={() => setHighlightedRequirementId(id)}>
                        {id}
                      </Button>
                    ),
                  },
                  { title: 'Tech', dataIndex: 'technique', width: 64, render: (v) => <Tag>{v}</Tag> },
                  {
                    title: 'Title',
                    dataIndex: 'title',
                    width: 140,
                    render: (v, record) => (
                      <Input
                        size="small"
                        value={v}
                        onChange={(e) => updateTestCase(record.test_id, { title: e.target.value })}
                      />
                    ),
                  },
                  {
                    title: 'Steps',
                    dataIndex: 'test_steps',
                    width: 120,
                    render: (steps: string[], record) => (
                      <Input
                        size="small"
                        value={steps.join(' → ')}
                        onChange={(e) =>
                          updateTestCase(record.test_id, {
                            test_steps: e.target.value.split('→').map((s) => s.trim()).filter(Boolean),
                          })
                        }
                      />
                    ),
                  },
                  {
                    title: 'Expected',
                    dataIndex: 'expected_result',
                    width: 120,
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
                    title: 'COV',
                    dataIndex: 'coverage_item_id',
                    width: 130,
                    ellipsis: true,
                  },
                  {
                    title: 'Std Ref',
                    dataIndex: 'standard_ref',
                    width: 100,
                    ellipsis: true,
                    render: (v: string) => (
                      <Text style={{ fontSize: 11 }} title={v}>
                        {v?.slice(0, 18) ?? '—'}…
                      </Text>
                    ),
                  },
                  {
                    title: 'Status',
                    width: 180,
                    render: (_, record) => (
                      <Space size={4} wrap>
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
            </Spin>
            {highlightedRequirementId && (
              <Text type="secondary" style={{ fontSize: 12, marginTop: 8, display: 'block' }}>
                追溯筛选：{highlightedRequirementId}
                <Button type="link" size="small" onClick={() => setHighlightedRequirementId(null)}>
                  显示全部
                </Button>
              </Text>
            )}
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Space direction="vertical" size={16} className="full-width">
            <TraceabilityPanel />
            <Card title="FSM · All States (FR4.0)">
              <DataStatusTag isLive={fsmLive} />
              {fsm?.mermaid?.trim() ? (
                <MermaidView chart={fsm.mermaid} />
              ) : fetching ? (
                <Spin />
              ) : (
                <Text type="secondary" style={{ fontSize: 12 }}>
                  暂无 FSM 数据
                </Text>
              )}
              {fsmPaths.length > 0 && (
                <List
                  size="small"
                  style={{ marginTop: 12 }}
                  dataSource={fsmPaths.slice(0, 8)}
                  renderItem={(path) => (
                    <List.Item
                      actions={[
                        <Select
                          key="cov"
                          size="small"
                          value={fsmPathCoverage[path] ?? 'pending'}
                          style={{ width: 110 }}
                          onChange={(v) => setFsmPathCoverage(path, v)}
                          options={[
                            { value: 'covered', label: '已覆盖' },
                            { value: 'uncovered', label: '未覆盖' },
                            { value: 'pending', label: '待确认' },
                          ]}
                        />,
                      ]}
                    >
                      <Text style={{ fontSize: 11 }}>{path}</Text>
                    </List.Item>
                  )}
                />
              )}
            </Card>
          </Space>
        </Col>
      </Row>}

      {hasRequirements && <Card title="Oracle · Expected Result 合成 (FR5.0)">
        <Table
          size="small"
          rowKey="test_id"
          pagination={false}
          dataSource={oracleResults}
          columns={[
            { title: 'Test ID', dataIndex: 'test_id', width: 130 },
            {
              title: 'LLM',
              dataIndex: 'llm_verdict',
              render: (v) => <Tag color={v === 'Pass' ? 'green' : 'red'}>{v}</Tag>,
            },
            {
              title: 'Rule',
              dataIndex: 'rule_verdict',
              render: (v) => <Tag>{v}</Tag>,
            },
            {
              title: 'Confidence',
              dataIndex: 'confidence',
              render: (v: number) => (
                <Tag color={v >= 0.85 ? 'green' : v >= 0.7 ? 'gold' : 'volcano'}>
                  {v.toFixed(2)}
                </Tag>
              ),
            },
            {
              title: 'Review',
              render: (_, record) =>
                record.needs_review ? (
                  <Button
                    size="small"
                    type="primary"
                    onClick={() => updateTestCase(record.test_id, { status: 'Approved' })}
                  >
                    Designer 确认
                  </Button>
                ) : (
                  <Tag color="green">OK</Tag>
                ),
            },
          ]}
        />
        {needsReviewCases.length > 0 && (
          <Alert
            className="top-gap"
            type="warning"
            showIcon
            message={`${needsReviewCases.length} 条用例需人工复核 Oracle 结果`}
          />
        )}
      </Card>}

      {hasRequirements && coverageItems.length > 0 && (
        <Alert
          type="info"
          showIcon
          message={`已加载 ${coverageItems.length} 个覆盖项，用例生成将与之追溯（COV-*）。`}
        />
      )}

      <ImprovementSummary />
      <RevisionPanel />
    </Space>
  )
}
