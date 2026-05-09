import { useMemo, useState } from 'react'
import type { UploadFile } from 'antd'
import {
  Alert,
  Button,
  Card,
  Col,
  Layout,
  List,
  Menu,
  Progress,
  Row,
  Segmented,
  Space,
  Table,
  Tag,
  Typography,
  Upload,
} from 'antd'
import type { MenuProps } from 'antd'
import { useAppStore } from './store/appStore'

const { Header, Content, Footer } = Layout
const { Title, Text } = Typography

type ModuleKey =
  | 'overview'
  | 'phase1'
  | 'phase2'
  | 'phase3'

const menuItems: MenuProps['items'] = [
  { key: 'overview', label: '项目概览' },
  { key: 'phase1', label: '阶段 1: 需求与风险 (FR1/FR2)' },
  { key: 'phase2', label: '阶段 2: 测试生成 (FR3/FR4)' },
  { key: 'phase3', label: '阶段 3: 评估与优化 (FR5/FR7)' },
]

const ingestResultMock = [
  {
    requirement_id: 'REQ-001',
    feature: '用户登录',
    actor: '终端用户',
    precondition: '用户已注册',
    acceptance: '支持账号密码登录，3 次失败后触发验证码',
    risk_level: 'High',
  },
  {
    requirement_id: 'REQ-002',
    feature: '订单查询',
    actor: '终端用户',
    precondition: '用户已登录',
    acceptance: '按日期筛选并分页返回订单列表',
    risk_level: 'Medium',
  },
  {
    requirement_id: 'REQ-003',
    feature: '退款审批',
    actor: '管理员',
    precondition: '订单状态为已支付',
    acceptance: '审批后更新状态并发送通知',
    risk_level: 'High',
  },
]

const heatmapData = [
  [1, 3, 6, 7, 10],
  [2, 4, 8, 9, 11],
  [3, 5, 7, 12, 16],
  [4, 7, 10, 14, 19],
  [6, 9, 13, 18, 24],
]

const blackboxCasesMock = [
  { key: 'TC-001', technique: 'EP', risk: 'High', status: 'Ready', standard_ref: 'ISO29119-4.2' },
  { key: 'TC-002', technique: 'BVA', risk: 'Medium', status: 'Draft', standard_ref: 'ISO29119-4.3' },
  { key: 'TC-003', technique: 'DT', risk: 'High', status: 'Ready', standard_ref: 'ISTQB-CTFL-4.4' },
]

const oracleMock = [
  { testId: 'TC-001', llmVerdict: 'Pass', ruleVerdict: 'Pass', confidence: 0.95, review: false },
  { testId: 'TC-019', llmVerdict: 'Pass', ruleVerdict: 'Fail', confidence: 0.56, review: true },
  { testId: 'TC-032', llmVerdict: 'Fail', ruleVerdict: 'Fail', confidence: 0.87, review: false },
]

const fsmMermaidMock = `stateDiagram-v2
[*] --> Idle
Idle --> Parsing: ingest
Parsing --> Parsed: validate OK
Parsed --> RiskScored: score risk
RiskScored --> Designed: generate tests
Designed --> [*]`

const optimizeMock = {
  beforeCount: 320,
  afterCount: 121,
  riskPriorityMode: true,
}

function getRiskColor(value: number) {
  if (value <= 5) return '#86efac'
  if (value <= 12) return '#facc15'
  return '#f87171'
}

function FR1Panel() {
  const [fileList, setFileList] = useState<UploadFile[]>([])
  const [parsed, setParsed] = useState<typeof ingestResultMock>([])
  const [parsing, setParsing] = useState(false)
  const [errors, setErrors] = useState<string[]>([])

  const handleParse = () => {
    if (fileList.length === 0) {
      setErrors(['请先上传 CSV 或 TXT 文件后再执行解析。'])
      return
    }

    setParsing(true)
    setErrors([])
    window.setTimeout(() => {
      setParsed(ingestResultMock)
      setErrors(['REQ-002 缺少非功能约束字段，已在后台标记为待补充。'])
      setParsing(false)
    }, 600)
  }

  return (
    <Space direction="vertical" size={16} className="full-width">
      <Card title="FR1.0 输入上传">
        <Upload.Dragger
          multiple
          accept=".csv,.txt"
          beforeUpload={() => false}
          fileList={fileList}
          onChange={(info) => setFileList(info.fileList)}
          className="upload-zone"
        >
          <p className="upload-title">拖拽或点击上传需求文件</p>
          <p className="upload-hint">支持 CSV/TXT；上传后可执行 mock parse 流程</p>
        </Upload.Dragger>

        <Space className="top-gap">
          <Button type="primary" onClick={handleParse} loading={parsing}>
            执行解析
          </Button>
          <Button onClick={() => { setParsed([]); setErrors([]); setFileList([]) }}>重置</Button>
        </Space>
      </Card>

      <Card title="FR1.1 Parsed Result Panel">
        {errors.length > 0 && (
          <Alert
            className="bottom-gap"
            type="warning"
            showIcon
            message="字段校验提示"
            description={
              <ul className="error-list">
                {errors.map((error) => (
                  <li key={error}>{error}</li>
                ))}
              </ul>
            }
          />
        )}

        <Table
          rowKey="requirement_id"
          pagination={false}
          dataSource={parsed}
          locale={{ emptyText: '尚未解析，请上传文件并点击“执行解析”。' }}
          columns={[
            { title: 'Requirement ID', dataIndex: 'requirement_id' },
            { title: 'Feature', dataIndex: 'feature' },
            { title: 'Actor', dataIndex: 'actor' },
            { title: 'Precondition', dataIndex: 'precondition' },
            { title: 'Acceptance Criteria', dataIndex: 'acceptance' },
            {
              title: 'Risk',
              dataIndex: 'risk_level',
              render: (value: string) => (
                <Tag color={value === 'High' ? 'volcano' : 'gold'}>{value}</Tag>
              ),
            },
          ]}
        />
      </Card>
    </Space>
  )
}

function FR2Panel() {
  return (
    <Row gutter={[16, 16]}>
      <Col xs={24} lg={16}>
        <Card title="FR2 风险热力图（Mock Data Stream）">
          <div className="heatmap">
            {heatmapData.flatMap((row, rowIndex) =>
              row.map((value, colIndex) => (
                <div
                  key={`${rowIndex}-${colIndex}`}
                  className="heatmap-cell"
                  style={{ background: getRiskColor(value) }}
                >
                  {value}
                </div>
              )),
            )}
          </div>
          <div className="heatmap-legend">
            <span>Low (1-5)</span>
            <span>Medium (6-12)</span>
            <span>High (13+)</span>
          </div>
        </Card>
      </Col>
      <Col xs={24} lg={8}>
        <Card title="Risk Report Snapshot">
          <List
            dataSource={[
              '高风险需求：12 条',
              '中风险需求：18 条',
              '低风险需求：22 条',
              '最高风险象限：高影响 x 高可能',
            ]}
            renderItem={(item) => <List.Item>{item}</List.Item>}
          />
        </Card>
      </Col>
    </Row>
  )
}

function FR3Panel() {
  return (
    <Card title="FR3 黑盒用例工作台（AG Grid Shell）">
      <Space direction="vertical" size={12} className="full-width">
        <Space wrap>
          <Tag color="geekblue">Filter</Tag>
          <Tag color="geekblue">Sort</Tag>
          <Tag color="geekblue">Group</Tag>
          <Tag color="geekblue">Row Selection</Tag>
        </Space>
        <Table
          pagination={false}
          dataSource={blackboxCasesMock}
          columns={[
            { title: 'Test ID', dataIndex: 'key' },
            { title: 'Technique', dataIndex: 'technique' },
            { title: 'Risk', dataIndex: 'risk', render: (value) => <Tag>{value}</Tag> },
            { title: 'Status', dataIndex: 'status' },
            { title: 'Standard Ref', dataIndex: 'standard_ref' },
          ]}
        />
      </Space>
    </Card>
  )
}

function FR4Panel() {
  return (
    <Row gutter={[16, 16]}>
      <Col xs={24} lg={14}>
        <Card title="FR4 Mermaid 状态图面板">
          <pre className="mermaid-block">{fsmMermaidMock}</pre>
        </Card>
      </Col>
      <Col xs={24} lg={10}>
        <Card title="Test Sequence List">
          <List
            dataSource={[
              'Seq-1: Idle -> Parsing -> Parsed',
              'Seq-2: Parsed -> RiskScored -> Designed',
              'Seq-3: Designed -> Exported',
            ]}
            renderItem={(item) => <List.Item>{item}</List.Item>}
          />
        </Card>
      </Col>
    </Row>
  )
}

function FR5Panel() {
  return (
    <Card title="FR5 Oracle 评估（Mock Confidence Flow）">
      <Table
        pagination={false}
        dataSource={oracleMock}
        rowKey="testId"
        columns={[
          { title: 'Test ID', dataIndex: 'testId' },
          { title: 'LLM Verdict', dataIndex: 'llmVerdict' },
          { title: 'Rule Verdict', dataIndex: 'ruleVerdict' },
          {
            title: 'Confidence',
            dataIndex: 'confidence',
            render: (value: number) => (
              <Tag color={value >= 0.85 ? 'green' : value >= 0.7 ? 'gold' : 'volcano'}>
                {value.toFixed(2)}
              </Tag>
            ),
          },
          {
            title: 'Review',
            dataIndex: 'review',
            render: (value: boolean) => (value ? <Tag color="volcano">Manual Review</Tag> : <Tag color="green">Auto Pass</Tag>),
          },
        ]}
      />
    </Card>
  )
}

function FR7Panel() {
  const [riskPriority, setRiskPriority] = useState(optimizeMock.riskPriorityMode)
  const reduced = useMemo(
    () => Math.round(((optimizeMock.beforeCount - optimizeMock.afterCount) / optimizeMock.beforeCount) * 100),
    [],
  )

  return (
    <Space direction="vertical" size={16} className="full-width">
      <Card title="FR7 套件优化控制台">
        <Space wrap>
          <Text>优化模式：</Text>
          <Segmented
            value={riskPriority ? 'risk' : 'normal'}
            onChange={(value) => setRiskPriority(value === 'risk')}
            options={[
              { label: '风险优先', value: 'risk' },
              { label: '标准模式', value: 'normal' },
            ]}
          />
        </Space>
      </Card>

      <Card title="Before / After 对比">
        <Row gutter={[16, 16]}>
          <Col xs={24} md={12}>
            <div className="compare-card">
              <Text type="secondary">Before</Text>
              <Title level={3}>{optimizeMock.beforeCount}</Title>
            </div>
          </Col>
          <Col xs={24} md={12}>
            <div className="compare-card compare-card-green">
              <Text type="secondary">After</Text>
              <Title level={3}>{riskPriority ? optimizeMock.afterCount - 8 : optimizeMock.afterCount}</Title>
            </div>
          </Col>
        </Row>
        <Progress className="top-gap" percent={reduced} />
      </Card>
    </Space>
  )
}

function Phase1Panel() {
  return (
    <Space direction="vertical" size={24} className="full-width">
      <FR1Panel />
      <FR2Panel />
    </Space>
  )
}

function Phase2Panel() {
  return (
    <Space direction="vertical" size={24} className="full-width">
      <FR3Panel />
      <FR4Panel />
    </Space>
  )
}

function Phase3Panel() {
  return (
    <Space direction="vertical" size={24} className="full-width">
      <FR5Panel />
      <FR7Panel />
    </Space>
  )
}

function OverviewPanel() {
  return (
    <Card title="项目介绍：AutoTestDesign">
      <Typography.Paragraph>
        AutoTestDesign 是一个面向软件测试设计的智能化系统原型。系统以被测系统需求规格说明（AUTSRS）和标准测试知识库为输入，结合检索增强生成（RAG）、大语言模型（LLM）、测试设计算法与前端可视化能力，自动生成、评估、优化并导出测试用例。
      </Typography.Paragraph>
      <Title level={5} style={{ marginTop: 16, marginBottom: 12 }}>核心功能模块</Title>
      <List
        size="small"
        dataSource={[
          'FR1 需求输入与解析：支持文件导入及 LLM 智能字段抽取',
          'FR2 风险分析：基于影响与可能性的矩阵热力图评估',
          'FR3 黑盒测试设计：等价类 (EP)、边界值 (BVA) 及决策表 (DT) 用例生成',
          'FR4 白盒与状态机：系统状态流转分析与 FSM 可视化',
          'FR5 测试 Oracle：基于 LLM 置信度与规则判断的双层评估',
          'FR6 测试用例导出：支持多格式的标准测试集交付',
          'FR7 测试套件优化：风险优先的测试用例集最小化',
        ]}
        renderItem={(item) => <List.Item>{item}</List.Item>}
      />
    </Card>
  )
}

function App() {
  const activeModule = useAppStore((state) => state.activeModule)
  const setActiveModule = useAppStore((state) => state.setActiveModule)

  const handleMenuClick: MenuProps['onClick'] = ({ key }) => {
    setActiveModule(key as ModuleKey)
  }

  const renderModule = () => {
    switch (activeModule) {
      case 'overview':
        return <OverviewPanel />
      case 'phase1':
        return <Phase1Panel />
      case 'phase2':
        return <Phase2Panel />
      case 'phase3':
        return <Phase3Panel />
      default:
        return <OverviewPanel />
    }
  }

  return (
    <Layout className="app-shell">
      <Header className="app-header">
        <div className="brand">
          <div className="brand-mark" />

          <div>
            <Title level={4} className="brand-title">
              AutoTestDesign
            </Title>

          </div>
        </div>

        <Menu
          mode="horizontal"
          items={menuItems}
          selectedKeys={[activeModule]}
          onClick={handleMenuClick}
          className="app-menu"
        />
      </Header>

      <Content className="app-content">
        {renderModule()}
      </Content>

      <Footer className="app-footer">
        <Space size="large">
          <Text>AutoTestDesign Frontend</Text>
          <Text type="secondary">C - Frontend & UX Delivery</Text>
        </Space>
      </Footer>
    </Layout>
  )
}

export default App