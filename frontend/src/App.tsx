import { Layout, Progress, Space, Steps, Tag, Typography } from 'antd'
import { StepFooter } from './components/StepFooter'
import { Step1InputParse } from './components/Step1InputParse'
import { Step2RiskAnalysis } from './components/Step2RiskAnalysis'
import { Step3GenerateEvaluate } from './components/Step3GenerateEvaluate'
import { Step4OptimizeExport } from './components/Step4OptimizeExport'
import { PipelineSummary } from './components/PipelineSummary'
import { useAppStore } from './store/appStore'
import heroImage from './assets/hero.png'

const { Header, Content, Sider } = Layout
const { Title, Text, Paragraph } = Typography

const steps = [
  {
    title: 'Input & Parse',
    description: '需求输入与结构化解析',
    short: '解析',
    accent: 'Ingest',
  },
  {
    title: 'Risk Analysis',
    description: '风险矩阵与覆盖项',
    short: '风险',
    accent: 'Prioritize',
  },
  {
    title: 'Generate & Evaluate',
    description: '用例生成与人工复核',
    short: '复核',
    accent: 'Review',
  },
  {
    title: 'Optimize & Export',
    description: '套件优化与导出',
    short: '导出',
    accent: 'Release',
  },
]

function App() {
  const currentStep = useAppStore((s) => s.currentStep)
  const setCurrentStep = useAppStore((s) => s.setCurrentStep)
  const requirements = useAppStore((s) => s.requirements)
  const sourceName = useAppStore((s) => s.sourceName)
  const testCases = useAppStore((s) => s.testCases)
  const riskEntries = useAppStore((s) => s.riskEntries)
  const revisions = useAppStore((s) => s.revisions)

  const content = [
    <Step1InputParse key="s1" />,
    <Step2RiskAnalysis key="s2" />,
    <Step3GenerateEvaluate key="s3" />,
    <Step4OptimizeExport key="s4" />,
  ][currentStep] ?? <Step1InputParse />

  const currentMeta = steps[currentStep] ?? steps[0]
  const progressPercent = Math.round(((currentStep + 1) / steps.length) * 100)
  const highRiskCount = riskEntries.filter((entry) => entry.level === 'High').length
  const hasDataset = requirements.length > 0
  const sourceLabel = hasDataset
    ? sourceName || requirements[0]?.source || '已上传需求集'
    : '等待上传需求文档'

  return (
    <Layout className="app-shell" hasSider>
      <Sider width={308} theme="light" className="app-sider">
        <div className="brand sider-brand">
          <div className="brand-mark" aria-hidden="true">
            AT
          </div>
          <div>
            <Title level={4} className="brand-title" style={{ margin: 0 }}>
              AutoTestDesign
            </Title>
            <Text className="brand-subtitle">需求驱动质量工作台</Text>
          </div>
        </div>
        <div className="pipeline-track">
          <div className="pipeline-track-head">
            <Text className="section-title">Pipeline Progress</Text>
            <Text strong>{progressPercent}%</Text>
          </div>
          <Progress
            percent={progressPercent}
            showInfo={false}
            strokeColor={{ '0%': '#1f6feb', '100%': '#0f766e' }}
          />
        </div>
        <div className="sider-steps">
          <Steps
            direction="vertical"
            current={currentStep}
            onChange={setCurrentStep}
            items={steps.map(({ title, description, short }, index) => ({
              title,
              description: (
                <span>
                  <span className="step-short">{short}</span>
                  {description}
                </span>
              ),
              status: index === currentStep ? 'process' : index < currentStep ? 'finish' : 'wait',
            }))}
          />
        </div>
      </Sider>

      <Layout className="main-layout">
        <Header className="app-header app-header-bar">
          <div className="header-title-block">
            <Text className="header-kicker">AutoTest Pipeline</Text>
            <Space size="small" wrap>
              <Text className="header-title">{sourceLabel}</Text>
              <Tag color={hasDataset ? 'processing' : 'default'}>
                {hasDataset ? '已载入' : '未开始检测'}
              </Tag>
            </Space>
          </div>
          <PipelineSummary />
        </Header>
        <Content className="app-content">
          <section className="command-hero">
            <div className="command-copy">
              <Text className="section-title">{currentMeta.accent} · Step {currentStep + 1}</Text>
              <Title level={2}>{hasDataset ? currentMeta.title : '上传需求文档后开始检测'}</Title>
              <Paragraph>
                {hasDataset
                  ? `${currentMeta.description}，保持需求、风险、覆盖项、用例与导出包在同一条可审计链路中。`
                  : '当前没有载入任何需求数据。请粘贴需求文本或上传 CSV / TXT / JSON 文件，系统会在解析完成后动态展示项目源、风险、覆盖项和测试用例。'}
              </Paragraph>
              <div className="hero-stat-grid" aria-label="Pipeline statistics">
                <div className="hero-stat">
                  <span>{requirements.length}</span>
                  <Text>Requirements</Text>
                </div>
                <div className="hero-stat">
                  <span>{testCases.length}</span>
                  <Text>Test Cases</Text>
                </div>
                <div className="hero-stat">
                  <span>{highRiskCount}</span>
                  <Text>High Risk</Text>
                </div>
                <div className="hero-stat">
                  <span>{revisions.length}</span>
                  <Text>Revisions</Text>
                </div>
              </div>
            </div>
            <div className="hero-visual" aria-hidden="true">
              <div className="hero-scanline" />
              <img src={heroImage} alt="" />
              <div className="hero-node hero-node-a" />
              <div className="hero-node hero-node-b" />
            </div>
          </section>
          <div className="stage-content" key={currentStep}>
            {content}
          </div>
          <StepFooter />
        </Content>
      </Layout>
    </Layout>
  )
}

export default App
