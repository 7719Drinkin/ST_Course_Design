import { useEffect, useCallback } from 'react'
import { Button, Layout, Space, Tag, Typography } from 'antd'
import heroImage from '@/assets/hero.png'
import { PipelineSummary } from '@/app/components/PipelineSummary'
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
  const coverageItems = useAppStore((s) => s.coverageItems)
  const stagePolling = useAppStore((s) => s.stagePolling)
  const regenerateTriggered = useAppStore((s) => s.regenerateTriggered)
  const pendingRevisions = useAppStore((s) => s.pendingRevisions)
  const commitPendingRevisions = useAppStore((s) => s.commitPendingRevisions)

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

  const getStageDataStatus = useCallback((index: number): 'pending' | 'polling' | 'ready' | 'awaiting' => {
    switch (index) {
      case 0: return requirements.length > 0 ? 'ready' : stagePolling[0] ? 'polling' : 'pending'
      case 1: return riskEntries.length > 0 ? 'ready' : stagePolling[1] ? 'polling' : 'pending'
      case 2: return coverageItems.length > 0 ? 'ready' : stagePolling[2] ? 'polling' : 'pending'
      case 3: return testCases.length > 0 ? 'ready' : stagePolling[3] ? 'polling' : 'pending'
      case 4:
        if (testCases.length === 0) return 'pending'
        if (!regenerateTriggered) return 'awaiting'
        if (stagePolling[4]) return 'polling'
        return 'ready'
      case 5:
        if (testCases.some((testCase) => testCase.status === 'Approved')) return 'ready'
        return testCases.length > 0 ? 'awaiting' : 'pending'
      default: return 'pending'
    }
  }, [requirements, riskEntries, coverageItems, testCases, stagePolling, regenerateTriggered])

  // Update document title when polling
  useEffect(() => {
    const anyPolling = Object.values(stagePolling).some(Boolean)
    document.title = anyPolling ? '\u27F3 AutoTestDesign' : 'AutoTestDesign'
  }, [stagePolling])

  const currentRoute = workflowRoutes[currentStep] ?? workflowRoutes[0]
  const highRiskCount = riskEntries.filter((entry) => entry.level === 'High').length
  const approvedCount = testCases.filter((testCase) => testCase.status === 'Approved').length
  const hasDataset = requirements.length > 0
  const sourceLabel = hasDataset
    ? sourceName || requirements[0]?.source || '已载入需求集'
    : '等待上传需求文档'

  return (
    <Layout className="app-shell" hasSider>
      <Sider width={330} theme="light" className="app-sider">
        <div className="brand sider-brand">
          <div className="brand-mark">ATD</div>
          <div>
            <Title level={4} className="brand-title">
              AutoTestDesign
            </Title>
            <Text className="brand-subtitle">通用测试设计工作台</Text>
          </div>
        </div>

        <nav className="route-rail" aria-label="AutoTestDesign workflow">
          {workflowRoutes.map((route, index) => {
            const dataStatus = getStageDataStatus(index)
            return (
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
                    dataStatus === 'ready' ? 'route-status-done'
                      : dataStatus === 'polling' ? 'route-status-running'
                        : dataStatus === 'awaiting' ? 'route-status-awaiting'
                          : 'route-status-pending'
                  }`}
                  aria-hidden="true"
                >
                  {dataStatus === 'ready' ? '\u2714' : ''}
                </span>
              </button>
            )
          })}
        </nav>
      </Sider>

      <Layout className="main-layout">
        <Header className="app-header app-header-bar">
          <div className="header-title-block">
            <Space size="small" wrap>
              <Text className="header-title">{sourceLabel}</Text>
              <Tag color={hasDataset ? 'processing' : 'default'}>
                {hasDataset ? '已载入' : '待输入'}
              </Tag>
              {highRiskCount > 0 && <Tag color="red">高风险 {highRiskCount}</Tag>}
              {approvedCount > 0 && <Tag color="green">通过 {approvedCount}</Tag>}
              {pendingRevisions.length > 0 && (
                <Button type="primary" size="small" danger onClick={commitPendingRevisions}>
                  修订待提交 ({pendingRevisions.length})
                </Button>
              )}
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
              </div>
            </div>
            <div className="evidence-rail-card" aria-label="Evidence rail">
              <img src={heroImage} alt="" />
              <div className="rail-line" />
              <div className="rail-step rail-step-a">输入</div>
              <div className="rail-step rail-step-b">审查</div>
              <div className="rail-step rail-step-c">证据</div>
            </div>
          </section>

          <div className="stage-content" key={currentRoute.id}>
            {currentRoute.render()}
          </div>
        </Content>
      </Layout>
    </Layout>
  )
}

export default App
