import { Layout, Progress, Space, Steps, Tag, Typography } from 'antd'
import heroImage from '@/assets/hero.png'
import { PipelineSummary } from '@/app/components/PipelineSummary'
import { StepFooter } from '@/app/components/StepFooter'
import { workflowRoutes } from '@/app/routes'
import { useAppStore } from '@/app/store/appStore'

const { Header, Content, Sider } = Layout
const { Title, Text, Paragraph } = Typography

function App() {
  const currentStep = useAppStore((s) => s.currentStep)
  const setCurrentStep = useAppStore((s) => s.setCurrentStep)
  const requirements = useAppStore((s) => s.requirements)
  const sourceName = useAppStore((s) => s.sourceName)
  const testCases = useAppStore((s) => s.testCases)
  const riskEntries = useAppStore((s) => s.riskEntries)
  const revisions = useAppStore((s) => s.revisions)

  const currentRoute = workflowRoutes[currentStep] ?? workflowRoutes[0]
  const progressPercent = Math.round(((currentStep + 1) / workflowRoutes.length) * 100)
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
            items={workflowRoutes.map(({ title, description, short }, index) => ({
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
              <Text className="section-title">{currentRoute.accent} · Step {currentStep + 1}</Text>
              <Title level={2}>{hasDataset ? currentRoute.title : '上传需求文档后开始检测'}</Title>
              <Paragraph>
                {hasDataset
                  ? `${currentRoute.description}，保持需求、风险、覆盖项、用例与导出包在同一条可审计链路中。`
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
            {currentRoute.render()}
          </div>
          <StepFooter />
        </Content>
      </Layout>
    </Layout>
  )
}

export default App
