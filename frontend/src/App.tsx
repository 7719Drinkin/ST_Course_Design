import { useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Col,
  Layout,
  List,
  Progress,
  Row,
  Segmented,
  Space,
  Spin,
  Steps,
  Table,
  Tag,
  Tooltip,
  Typography,
  Upload,
} from 'antd'
import type { UploadFile } from 'antd'
import { useAppStore } from './store/appStore'
import {
  generateFSM,
  getExportUrl,
  getOptimizeResult,
  getOracleResults,
  getRiskData,
  getTestCases,
  ingestAndParse,
} from './services/api'
import type { ApiResult, DisplayRequirement, FSMResult, OptimizeMode, OptimizeResult, OracleResult, RiskEntry, TestCase } from './types'

const { Header, Content, Sider } = Layout
const { Title, Text } = Typography

// ── Shared helpers ────────────────────────────────────────────────────────────

function DataStatusTag({
  result,
}: {
  result: { isLive: boolean; pendingFrom?: string } | null
}) {
  if (!result) return null
  if (result.isLive)
    return <Tag color="green" style={{ marginLeft: 8 }}>Live</Tag>
  return (
    <Tooltip title={`待对接：${result.pendingFrom}`}>
      <Tag color="orange" style={{ marginLeft: 8, cursor: 'help' }}>
        Mock · 待接入
      </Tag>
    </Tooltip>
  )
}

function riskColor(level: string) {
  if (level === 'High') return 'volcano'
  if (level === 'Medium') return 'gold'
  return 'green'
}

// ── Step 1: Input & Parse ─────────────────────────────────────────────────────

function Step1InputParse() {
  const [fileList, setFileList] = useState<UploadFile[]>([])
  const [loading, setLoading] = useState(false)
  const [apiResult, setApiResult] = useState<ApiResult<DisplayRequirement[]> | null>(null)
  const setCurrentStep = useAppStore((s) => s.setCurrentStep)

  const handleParse = async () => {
    if (fileList.length === 0) {
      setApiResult({ data: [], isLive: false, pendingFrom: '请先上传文件' })
      return
    }
    setLoading(true)
    // Read first file content as text; fall back to filename as content for mock
    const content = fileList[0].name
    const result = await ingestAndParse(content)
    setApiResult(result)
    setLoading(false)
  }

  const handleReset = () => {
    setFileList([])
    setApiResult(null)
  }

  const missingCount = apiResult?.data.filter((r) => r.missing_fields.length > 0).length ?? 0

  const columns = [
    { title: 'Requirement ID', dataIndex: 'requirement_id', width: 150 },
    { title: 'Expected Action', dataIndex: 'expected_action', ellipsis: true },
    {
      title: 'Input Fields',
      dataIndex: 'input_fields',
      render: (v: string[]) => v.length ? v.join(', ') : <Text type="secondary">—</Text>,
    },
    {
      title: 'Conditions',
      dataIndex: 'conditions',
      render: (v: string[]) => v.length ? v.join(' · ') : <Text type="secondary">—</Text>,
    },
    {
      title: 'Confidence',
      dataIndex: 'confidence',
      width: 110,
      render: (v: number) => (
        <Tag color={v >= 0.85 ? 'green' : v >= 0.7 ? 'gold' : 'volcano'}>{v.toFixed(2)}</Tag>
      ),
    },
    {
      title: 'Missing Fields',
      dataIndex: 'missing_fields',
      width: 130,
      render: (v: string[]) =>
        v.length ? <Tag color="volcano">{v.join(', ')}</Tag> : <Tag color="green">OK</Tag>,
    },
  ]

  return (
    <Space direction="vertical" size={24} className="full-width">
      <Card title="需求文件上传">
        <Upload.Dragger
          multiple
          accept=".csv,.txt,.json"
          beforeUpload={() => false}
          fileList={fileList}
          onChange={(info) => setFileList(info.fileList)}
          className="upload-zone"
        >
          <p className="upload-title">拖拽或点击上传需求文件</p>
          <p className="upload-hint">支持 CSV / TXT / JSON（AUT SRS 格式）</p>
        </Upload.Dragger>

        <Space className="top-gap">
          <Button type="primary" onClick={handleParse} loading={loading}>
            执行解析
          </Button>
          <Button onClick={handleReset}>重置</Button>
        </Space>
      </Card>

      {(loading || apiResult) && (
        <Card
          title={
            <span>
              解析结果 (FR1.1)
              <DataStatusTag result={apiResult} />
            </span>
          }
          extra={
            apiResult && apiResult.data.length > 0 ? (
              <Button type="primary" onClick={() => setCurrentStep(1)}>
                下一步: 风险评估
              </Button>
            ) : null
          }
        >
          <Spin spinning={loading}>
            {!loading && missingCount > 0 && (
              <Alert
                className="bottom-gap"
                type="warning"
                showIcon
                message={`字段完整性提示：${missingCount} 条需求存在缺失字段，已标记。`}
              />
            )}
            <Table
              rowKey="requirement_id"
              size="small"
              pagination={false}
              dataSource={apiResult?.data ?? []}
              columns={columns}
              locale={{ emptyText: '尚未解析，请上传文件并点击"执行解析"' }}
            />
          </Spin>
        </Card>
      )}
    </Space>
  )
}

// ── Step 2: Risk Analysis ─────────────────────────────────────────────────────

function buildHeatmapMatrix(entries: RiskEntry[]): number[][] {
  // 5×5 matrix: rows = likelihood (1-5), cols = impact (1-5), value = count of requirements in cell
  const matrix = Array.from({ length: 5 }, () => Array<number>(5).fill(0))
  entries.forEach(({ impact, likelihood }) => {
    const r = Math.min(5, Math.max(1, likelihood)) - 1
    const c = Math.min(5, Math.max(1, impact)) - 1
    matrix[r][c]++
  })
  return matrix
}

function getCellBg(count: number, row: number, col: number) {
  const score = (row + 1) * (col + 1)
  if (count === 0) return score >= 15 ? 'rgba(248,113,113,0.15)' : score >= 8 ? 'rgba(250,204,21,0.15)' : 'rgba(134,239,172,0.15)'
  if (score >= 15) return '#f87171'
  if (score >= 8) return '#facc15'
  return '#86efac'
}

function Step2RiskAnalysis() {
  const setCurrentStep = useAppStore((s) => s.setCurrentStep)
  const [apiResult, setApiResult] = useState<ApiResult<RiskEntry[]> | null>(null)

  useEffect(() => {
    getRiskData().then(setApiResult)
  }, [])

  const entries = useMemo(() => apiResult?.data ?? [], [apiResult])
  const matrix = useMemo(() => buildHeatmapMatrix(entries), [entries])
  const highCount = entries.filter((e) => e.level === 'High').length
  const medCount = entries.filter((e) => e.level === 'Medium').length
  const lowCount = entries.filter((e) => e.level === 'Low').length

  return (
    <Space direction="vertical" size={24} className="full-width">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span>
          <Title level={4} style={{ margin: 0, display: 'inline' }}>风险矩阵评估</Title>
          <DataStatusTag result={apiResult} />
        </span>
        <Button type="primary" onClick={() => setCurrentStep(2)}>下一步: 测试生成与复核</Button>
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={16}>
          <Card title="Impact × Likelihood 热力图">
            <Spin spinning={!apiResult}>
              <div className="heatmap">
                {matrix.flatMap((row, rIdx) =>
                  row.map((count, cIdx) => (
                    <div
                      key={`${rIdx}-${cIdx}`}
                      className="heatmap-cell"
                      style={{ background: getCellBg(count, rIdx, cIdx) }}
                    >
                      {count > 0 ? count : ''}
                    </div>
                  )),
                )}
              </div>
              <div className="heatmap-legend">
                <span>Low Impact × Likelihood</span>
                <span>Medium</span>
                <span>High</span>
              </div>
              <Text type="secondary" style={{ fontSize: 11, display: 'block', marginTop: 6 }}>
                数字 = 该象限内的需求数量
              </Text>
            </Spin>
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card title="Risk Snapshot">
            <Spin spinning={!apiResult}>
              <List
                size="small"
                dataSource={[
                  `高风险需求：${highCount} 条`,
                  `中风险需求：${medCount} 条`,
                  `低风险需求：${lowCount} 条`,
                ]}
                renderItem={(item) => <List.Item>{item}</List.Item>}
              />
              {entries.length > 0 && (
                <Table
                  size="small"
                  pagination={false}
                  style={{ marginTop: 12 }}
                  rowKey="requirement_id"
                  dataSource={entries}
                  columns={[
                    { title: 'ID', dataIndex: 'requirement_id', ellipsis: true },
                    { title: 'Score', dataIndex: 'score', width: 60 },
                    {
                      title: 'Level',
                      dataIndex: 'level',
                      width: 80,
                      render: (v: string) => <Tag color={riskColor(v)}>{v}</Tag>,
                    },
                  ]}
                />
              )}
            </Spin>
          </Card>
        </Col>
      </Row>
    </Space>
  )
}

// ── Step 3: Generate & Evaluate ───────────────────────────────────────────────

function Step3GenerateEvaluate() {
  const setCurrentStep = useAppStore((s) => s.setCurrentStep)
  const [tcResult, setTcResult] = useState<ApiResult<TestCase[]> | null>(null)
  const [fsmResult, setFsmResult] = useState<ApiResult<FSMResult> | null>(null)
  const [oracleResult, setOracleResult] = useState<ApiResult<OracleResult[]> | null>(null)

  useEffect(() => {
    getTestCases().then(setTcResult)
    generateFSM(['REQ-AUT-008', 'REQ-AUT-012', 'REQ-AUT-001']).then(setFsmResult)
    getOracleResults().then(setOracleResult)
  }, [])

  const testCases = tcResult?.data ?? []
  const oracleMap = useMemo(() => {
    const m = new Map<string, OracleResult>()
    oracleResult?.data.forEach((o) => m.set(o.test_id, o))
    return m
  }, [oracleResult])

  const tcColumns = [
    { title: 'Test ID', dataIndex: 'test_id', width: 150 },
    { title: 'Req ID', dataIndex: 'requirement_id', width: 140 },
    {
      title: 'Technique',
      dataIndex: 'technique',
      width: 90,
      render: (v: string) => <Tag color="geekblue">{v}</Tag>,
    },
    { title: 'Title', dataIndex: 'title', ellipsis: true },
    {
      title: 'Risk',
      dataIndex: 'risk_level',
      width: 90,
      render: (v: string) => <Tag color={riskColor(v)}>{v}</Tag>,
    },
    { title: 'Standard Ref', dataIndex: 'standard_ref', ellipsis: true },
    {
      title: 'Confidence',
      width: 110,
      render: (_: unknown, record: TestCase) => {
        const o = oracleMap.get(record.test_id)
        if (!o) return <Tag>Pending</Tag>
        return (
          <Tag color={o.confidence >= 0.85 ? 'green' : o.confidence >= 0.7 ? 'gold' : 'volcano'}>
            {o.confidence.toFixed(2)}
          </Tag>
        )
      },
    },
    {
      title: 'Oracle',
      width: 130,
      render: (_: unknown, record: TestCase) => {
        const o = oracleMap.get(record.test_id)
        if (!o) return <Tag>Pending</Tag>
        return o.needs_review ? (
          <Button size="small" danger ghost>待复核</Button>
        ) : (
          <Tag color="green">自动通过</Tag>
        )
      },
    },
  ]

  return (
    <Space direction="vertical" size={24} className="full-width">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span>
          <Title level={4} style={{ margin: 0, display: 'inline' }}>生成与复核工作区</Title>
          <DataStatusTag result={tcResult} />
        </span>
        <Button type="primary" onClick={() => setCurrentStep(3)}>下一步: 套件优化与导出</Button>
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={16}>
          <Card
            title={
              <span>
                综合测试用例池 (黑盒 + 白盒)
                <DataStatusTag result={tcResult} />
              </span>
            }
          >
            <Spin spinning={!tcResult}>
              <Table
                rowKey="test_id"
                size="small"
                pagination={false}
                dataSource={testCases}
                columns={tcColumns}
                locale={{ emptyText: '暂无用例数据' }}
              />
            </Spin>
          </Card>
        </Col>

        <Col xs={24} lg={8}>
          <Card
            title={
              <span>
                FSM 状态机
                <DataStatusTag result={fsmResult} />
              </span>
            }
          >
            <Spin spinning={!fsmResult}>
              {fsmResult && (
                <>
                  <pre className="mermaid-block">{fsmResult.data.mermaid}</pre>
                  <div style={{ marginTop: 12 }}>
                    <Text type="secondary" style={{ fontSize: 12 }}>Coverage paths</Text>
                    <List
                      size="small"
                      style={{ marginTop: 4 }}
                      dataSource={fsmResult.data.coverage.all_transitions}
                      renderItem={(t) => <List.Item style={{ fontSize: 12 }}>{t}</List.Item>}
                    />
                  </div>
                </>
              )}
            </Spin>
          </Card>
        </Col>
      </Row>
    </Space>
  )
}

// ── Step 4: Optimize & Export ─────────────────────────────────────────────────

function Step4OptimizeExport() {
  const [mode, setMode] = useState<OptimizeMode>('risk_priority')
  const [apiResult, setApiResult] = useState<ApiResult<OptimizeResult> | null>(null)

  useEffect(() => {
    getOptimizeResult(mode).then(setApiResult)
  }, [mode])

  const opt = apiResult?.data
  const reductionRate = opt?.reduction_rate ?? 0

  return (
    <Space direction="vertical" size={24} className="full-width">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span>
          <Title level={4} style={{ margin: 0, display: 'inline' }}>套件优化与交付</Title>
          <DataStatusTag result={apiResult} />
        </span>
        <Space>
          <Button onClick={() => window.open(getExportUrl('csv'), '_blank')}>导出 CSV</Button>
          <Button onClick={() => window.open(getExportUrl('xlsx'), '_blank')}>导出 XLSX</Button>
          <Button
            type="primary"
            style={{ background: '#0f766e', borderColor: '#0f766e' }}
            onClick={() => window.open(getExportUrl('json'), '_blank')}
          >
            导出 JSON
          </Button>
        </Space>
      </div>

      <Card title="FR7.0 套件优化策略">
        <Space direction="vertical" size={16} className="full-width">
          <Space wrap>
            <Text>优化模式：</Text>
            <Segmented
              value={mode}
              onChange={(v) => setMode(v as OptimizeMode)}
              options={[
                { label: '风险优先', value: 'risk_priority' },
                { label: '标准模式', value: 'normal' },
              ]}
            />
          </Space>

          <Spin spinning={!apiResult}>
            <Row gutter={[16, 16]}>
              <Col xs={24} md={12}>
                <div className="compare-card">
                  <Text type="secondary">优化前用例数</Text>
                  <Title level={3}>{opt?.before_count ?? '—'}</Title>
                </div>
              </Col>
              <Col xs={24} md={12}>
                <div className="compare-card compare-card-green">
                  <Text type="secondary">优化后用例数</Text>
                  <Title level={3}>{opt?.after_count ?? '—'}</Title>
                </div>
              </Col>
            </Row>
            <div style={{ marginTop: 16 }}>
              <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 6 }}>
                缩减率 (Reduction Rate)
              </Text>
              <Progress percent={reductionRate} strokeColor="#0f766e" />
            </div>
          </Spin>
        </Space>
      </Card>
    </Space>
  )
}

// ── App shell ─────────────────────────────────────────────────────────────────

function App() {
  const currentStep = useAppStore((s) => s.currentStep)
  const setCurrentStep = useAppStore((s) => s.setCurrentStep)

  const renderStepContent = () => {
    switch (currentStep) {
      case 0: return <Step1InputParse />
      case 1: return <Step2RiskAnalysis />
      case 2: return <Step3GenerateEvaluate />
      case 3: return <Step4OptimizeExport />
      default: return <Step1InputParse />
    }
  }

  return (
    <Layout className="app-shell" hasSider>
      <Sider
        width={280}
        theme="light"
        className="app-sider"
        style={{ borderRight: '1px solid var(--border)' }}
      >
        <div
          className="brand"
          style={{
            padding: '24px 20px',
            borderBottom: '1px solid var(--border)',
            marginBottom: 24,
          }}
        >
          <div className="brand-mark" />
          <Title level={4} className="brand-title" style={{ margin: 0 }}>
            AutoTestDesign
          </Title>
        </div>

        <div style={{ padding: '0 24px' }}>
          <Steps
            direction="vertical"
            current={currentStep}
            onChange={setCurrentStep}
            items={[
              { title: 'Input & Parse', description: '上传需求文件，智能字段解析' },
              { title: 'Risk Analysis', description: '影响 × 可能性矩阵评估' },
              { title: 'Generate & Evaluate', description: '黑盒/白盒生成 + Oracle 复核' },
              { title: 'Optimize & Export', description: '用例最小化优化与格式导出' },
            ]}
          />
        </div>
      </Sider>

      <Layout>
        <Header
          className="app-header"
          style={{
            padding: '0 40px',
            background: 'rgba(255, 255, 255, 0.8)',
            borderBottom: '1px solid var(--border)',
            display: 'flex',
            alignItems: 'center',
          }}
        >
          <Text style={{ fontWeight: 500 }}>AutoTest Pipeline</Text>
        </Header>

        <Content className="app-content" style={{ overflowY: 'auto' }}>
          {renderStepContent()}
        </Content>
      </Layout>
    </Layout>
  )
}

export default App
