import { useEffect } from 'react'
import { Button, Layout, Space, Tag, Typography } from 'antd'
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

  useEffect(() => {
    const syncHash = () => {
      const id = window.location.hash.replace('#/', '')
      const nextIndex = workflowRoutes.findIndex((route) => route.id === id)
      if (nextIndex >= 0) setCurrentStep(nextIndex)
    }
    syncHash()
    window.addEventListener('hashchange', syncHash)
    return () => window.removeEventListener('hashchange', syncHash)
  }, [setCurrentStep])

  const navigateToStep = (step: number) => {
    const boundedStep = Math.min(Math.max(step, 0), workflowRoutes.length - 1)
    setCurrentStep(boundedStep)
    window.history.replaceState(null, '', `#/${workflowRoutes[boundedStep].id}`)
  }

  const currentRoute = workflowRoutes[currentStep] ?? workflowRoutes[0]
  const highRiskCount = riskEntries.filter((entry) => entry.level === 'High').length
  const approvedCount = testCases.filter((testCase) => testCase.status === 'Approved').length
  const approvedCount = testCases.filter((testCase) => testCase.status === 'Approved').length
  const hasDataset = requirements.length > 0
  const sourceLabel = hasDataset
    ? sourceName || requirements[0]?.source || '已载入需求集'
    ? sourceName || requirements[0]?.source || '已载入需求集'
    : '等待上传需求文档'

  return (
    <Layout className="app-shell" hasSider>
      <Sider width={330} theme="light" className="app-sider">
      <Sider width={330} theme="light" className="app-sider">
        <div className="brand sider-brand">
          <div className="brand-mark">ATD</div>
          <div className="brand-mark">ATD</div>
          <div>
            <Title level={4} className="brand-title">
              AutoTestDesign
            <Title level={4} className="brand-title">
              AutoTestDesign
            </Title>
            <Text className="brand-subtitle">通用测试设计工作台</Text>
            <Text className="brand-subtitle">通用测试设计工作台</Text>
          </div>
        </div>

        <nav className="route-rail" aria-label="AutoTestDesign workflow">
          {workflowRoutes.map((route, index) => (
            <button
              key={route.id}
              type="button"
              className={`route-node ${index === currentStep ? 'route-node-active' : ''}`}
              aria-current={index === currentStep ? 'step' : undefined}
              onClick={() => navigateToStep(index)}
            >
              <span className="route-index">{String(index + 1).padStart(2, '0')}</span>
              <span className="route-copy">
                <strong>{route.short}</strong>
              </span>
              <span
                className={`route-status ${
                  index < currentStep
                    ? 'route-status-done'
                    : index === currentStep
                      ? 'route-status-running'
                      : 'route-status-pending'
                }`}
                aria-hidden="true"
              >
                {index < currentStep ? '✔' : ''}
              </span>
            </button>
          ))}
        </nav>

        <nav className="route-rail" aria-label="AutoTestDesign workflow">
          {workflowRoutes.map((route, index) => (
            <button
              key={route.id}
              type="button"
              className={`route-node ${index === currentStep ? 'route-node-active' : ''}`}
              aria-current={index === currentStep ? 'step' : undefined}
              onClick={() => navigateToStep(index)}
            >
              <span className="route-index">{String(index + 1).padStart(2, '0')}</span>
              <span className="route-copy">
                <strong>{route.short}</strong>
              </span>
              <span
                className={`route-status ${
                  index < currentStep
                    ? 'route-status-done'
                    : index === currentStep
                      ? 'route-status-running'
                      : 'route-status-pending'
                }`}
                aria-hidden="true"
              >
                {index < currentStep ? '✔' : ''}
              </span>
            </button>
          ))}
        </nav>
      </Sider>

      <Layout className="main-layout">
        <Header className="app-header app-header-bar">
          <div className="header-title-block">
            <Space size="small" wrap>
              <Text className="header-title">{sourceLabel}</Text>
              <Tag color={hasDataset ? 'processing' : 'default'}>
                {hasDataset ? '已载入' : '待输入'}
                {hasDataset ? '已载入' : '待输入'}
              </Tag>
              {highRiskCount > 0 && <Tag color="red">高风险 {highRiskCount}</Tag>}
              {approvedCount > 0 && <Tag color="green">通过 {approvedCount}</Tag>}
              {highRiskCount > 0 && <Tag color="red">高风险 {highRiskCount}</Tag>}
              {approvedCount > 0 && <Tag color="green">通过 {approvedCount}</Tag>}
            </Space>
          </div>
          <PipelineSummary />
        </Header>


        <Content className="app-content">
          <section className="stage-masthead">
            <div className="stage-copy">
              <Text className="section-title">{currentRoute.accent} · 阶段 {currentStep + 1}</Text>
              <Title level={2}>{currentRoute.title}</Title>
              <Paragraph>{currentRoute.description}</Paragraph>
              <div className="stage-review-row">
                <span>输入</span>
                <span>审查</span>
                <span>修订</span>
                <span>证据</span>
          <section className="stage-masthead">
            <div className="stage-copy">
              <Text className="section-title">{currentRoute.accent} · 阶段 {currentStep + 1}</Text>
              <Title level={2}>{currentRoute.title}</Title>
              <Paragraph>{currentRoute.description}</Paragraph>
              <div className="stage-review-row">
                <span>输入</span>
                <span>审查</span>
                <span>修订</span>
                <span>证据</span>
              </div>
            </div>
            <div className="evidence-rail-card" aria-label="Evidence rail">
            <div className="evidence-rail-card" aria-label="Evidence rail">
              <img src={heroImage} alt="" />
              <div className="rail-line" />
              <div className="rail-step rail-step-a">输入</div>
              <div className="rail-step rail-step-b">审查</div>
              <div className="rail-step rail-step-c">证据</div>
              <div className="rail-line" />
              <div className="rail-step rail-step-a">输入</div>
              <div className="rail-step rail-step-b">审查</div>
              <div className="rail-step rail-step-c">证据</div>
            </div>
          </section>

          <div className="stage-jumpbar">
            <Space wrap>
              <Button disabled={currentStep === 0} onClick={() => navigateToStep(currentStep - 1)}>
                上一阶段
              </Button>
              <Button
                type="primary"
                disabled={currentStep >= workflowRoutes.length - 1}
                onClick={() => navigateToStep(currentStep + 1)}
              >
                下一阶段
              </Button>
            </Space>
            <Text type="secondary">
              {revisions.length > 0
                ? `已有 ${revisions.length} 条设计者修订记录`
                : '所有人工修改会进入修订证据轨'}
            </Text>
          </div>

          <div className="stage-content" key={currentRoute.id}>
            {currentRoute.render()}
          </div>
          <StepFooter onNavigate={navigateToStep} />
          <StepFooter onNavigate={navigateToStep} />
        </Content>
      </Layout>
    </Layout>
  )
}

export default App
