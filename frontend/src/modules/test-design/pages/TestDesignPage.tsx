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
import { useAppStore } from '@/app/store/appStore'
import { generateFSM } from '@/modules/test-design/api/fsmApi'
import { MermaidView } from '@/modules/test-design/components/MermaidView'
import { TraceabilityPanel } from '@/modules/test-design/components/TraceabilityPanel'
import { getOracleResults } from '@/modules/test-design/api/oracleApi'
import { getTestCases } from '@/modules/test-design/api/testCasesApi'
import { ImprovementSummary } from '@/shared/components/ImprovementSummary'
import { RevisionPanel } from '@/shared/components/RevisionPanel'
import { DataStatusTag, WorkflowEmptyState } from '@/shared/components/WorkflowFeedback'
import type { Technique, TestCaseStatus } from '@/shared/types'

const { Title, Text } = Typography
const GENERATE_SLOW_MS = 2000

export function TestDesignPage() {
  const [tcLive, setTcLive] = useState<boolean>()
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
  const riskEntries = useAppStore((s) => s.riskEntries)
  const pipelineActive = useAppStore((s) => s.pipelineActive)

  const reqIdsKey = requirements.map((r) => r.requirement_id).join(',')
  const coverageIdsKey = coverageItems.map((item) => item.coverage_item_id).join(',')
  const riskKey = riskEntries.map((entry) => `${entry.requirement_id}:${entry.risk_score ?? entry.score}`).join(',')
  const hasRequirements = requirements.length > 0

  useEffect(() => {
    if (pipelineActive) return
    if (!reqIdsKey || coverageItems.length === 0) {
      setTestCases([])
      setOracleResults([])
      setFsm(null)
      return
    }
    let active = true
    const slowTimer = window.setTimeout(() => {
      if (active) setSlowWarning(true)
    }, GENERATE_SLOW_MS)

    const load = async () => {
      setFetching(true)
      try {
        const r = await getTestCases(coverageItems, riskEntries)
        if (!active) return
        const cases = r.data.map((c) => ({ ...c, status: c.status ?? 'Draft' }))
        const fsmCasesFromStore = useAppStore.getState().testCases.filter((t) => t.technique === 'FSM')
        setTestCases([...cases, ...fsmCasesFromStore])
        setTcLive(r.isLive)
        if (cases.length === 0) {
          setOracleResults([])
          return
        }
        const o = await getOracleResults(cases, requirements)
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

    generateFSM(requirements, coverageItems).then((r) => {
      if (active) {
        setFsm(r.data)
        setFsmLive(r.isLive)
      }
    })

    return () => {
      active = false
      window.clearTimeout(slowTimer)
    }
  }, [
    pipelineActive,
    reqIdsKey,
    coverageIdsKey,
    coverageItems,
    requirements,
    riskEntries,
    riskKey,
    setTestCases,
    setOracleResults,
    setFsm,
  ])

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
    return !(highlightedRequirementId && tc.requirement_id !== highlightedRequirementId)

  })

  const fsmPaths = useMemo(() => {
    if (!fsm) return []
    if (fsm.coverage) {
      const statePaths = fsm.coverage.all_states.map((s) => `state:${s}`)
      const transPaths = fsm.coverage.all_transitions.map((t) => `transition:${t}`)
      return [...statePaths, ...transPaths]
    }
    return fsm.coverage_paths
  }, [fsm])

  const needsReviewCases = oracleResults.filter((o) => o.needs_review)

  const handleApproveAll = () => {
    const targetIds = new Set(filteredCases.map((tc) => tc.test_id))
    setTestCases(testCases.map((tc) => (
      targetIds.has(tc.test_id) ? { ...tc, status: 'Approved' } : tc
    )))
  }

  const handleRejectAll = () => {
    const targetIds = new Set(filteredCases.map((tc) => tc.test_id))
    setTestCases(testCases.map((tc) => (
      targetIds.has(tc.test_id) ? { ...tc, status: 'Rejected' } : tc
    )))
  }

  return (
    <Space direction="vertical" size={24} className="full-width">
      <div className="stage-toolbar stage-toolbar-wrap">
        <span>
          <Title level={4} style={{ margin: 0, display: 'inline' }}>生成与复核</Title>
          {hasRequirements && <DataStatusTag isLive={tcLive} />}
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
              { value: 'Draft', label: '草稿' },
              { value: 'Approved', label: '通过' },
              { value: 'Rejected', label: '驳回' },
            ]}
          />
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
          title="用例生成超过 2s（NFR 目标），请稍后；后端联调后可优化性能。"
        />
      ) : null}

      {hasRequirements && <Row gutter={[16, 16]}>
        <Col xs={24} lg={16}>
          <Card title="测试用例池 · 人工审查" extra={
            <Space>
              <Button size="small" onClick={handleApproveAll}>全部通过</Button>
              <Button size="small" danger onClick={handleRejectAll}>全部驳回</Button>
            </Space>
          }>
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
                  { title: '用例编号', dataIndex: 'test_id', width: 120, ellipsis: true },
                  {
                    title: '需求',
                    dataIndex: 'requirement_id',
                    width: 108,
                    render: (id: string) => (
                      <Button type="link" size="small" onClick={() => setHighlightedRequirementId(id)}>
                        {id}
                      </Button>
                    ),
                  },
                  { title: '方法', dataIndex: 'technique', width: 64, render: (v) => <Tag>{v}</Tag> },
                  {
                    title: '标题',
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
                    title: '步骤',
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
                    title: '期望结果',
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
                    title: '覆盖项',
                    dataIndex: 'coverage_item_id',
                    width: 130,
                    ellipsis: true,
                  },
                  {
                    title: '依据',
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
                    title: '状态',
                    width: 180,
                    render: (_, record) => (
                      <Space size={4} wrap>
                        {[
                          { value: 'Approved' as TestCaseStatus, label: '通过' },
                          { value: 'Rejected' as TestCaseStatus, label: '驳回' },
                          { value: 'Draft' as TestCaseStatus, label: '草稿' },
                        ].map((statusOption) => (
                          <Button
                            key={statusOption.value}
                            size="small"
                            type={record.status === statusOption.value ? 'primary' : 'default'}
                            danger={statusOption.value === 'Rejected'}
                            onClick={() => updateTestCase(record.test_id, { status: statusOption.value }, undefined, true)}
                          >
                            {statusOption.label}
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
            <Card title="FSM · All States">
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
              {testCases.filter((tc) => tc.technique === 'FSM').length > 0 && (
                <List
                  size="small"
                  style={{ marginTop: 12 }}
                  header={<Text strong>FSM 测试用例</Text>}
                  dataSource={testCases.filter((tc) => tc.technique === 'FSM').slice(0, 6)}
                  renderItem={(tc) => (
                    <List.Item>
                      <Space direction="vertical" size={0}>
                        <Text strong style={{ fontSize: 11 }}>{tc.test_id}</Text>
                        <Text style={{ fontSize: 11 }}>{tc.title}</Text>
                      </Space>
                    </List.Item>
                  )}
                />
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

      {hasRequirements && <Card title="期望结果复核">
        <Table
          size="small"
          rowKey="test_id"
          pagination={false}
          dataSource={oracleResults}
          columns={[
            { title: '用例编号', dataIndex: 'test_id', width: 130 },
            {
              title: '置信度',
              dataIndex: 'confidence',
              render: (v: number) => (
                <Tag color={v >= 0.85 ? 'green' : v >= 0.7 ? 'gold' : 'volcano'}>
                  {v.toFixed(2)}
                </Tag>
              ),
            },
            {
              title: '审查',
              render: (_, record) =>
                record.needs_review ? (
                  <Button
                    size="small"
                    type="primary"
                    onClick={() => updateTestCase(record.test_id, { status: 'Approved' }, undefined, true)}
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
            title={`${needsReviewCases.length} 条用例需人工复核 Oracle 结果`}
          />
        )}
      </Card>}

      {hasRequirements && coverageItems.length > 0 && (
        <Alert
          type="info"
          showIcon
          title={`已加载 ${coverageItems.length} 个覆盖项，用例生成将与之追溯（COV-*）。`}
        />
      )}

      <ImprovementSummary />
      <RevisionPanel />
    </Space>
  )
}
