import { Layout, Steps, Typography } from 'antd'
import { Step1InputParse } from './components/Step1InputParse'
import { Step2RiskAnalysis } from './components/Step2RiskAnalysis'
import { Step3GenerateEvaluate } from './components/Step3GenerateEvaluate'
import { Step4OptimizeExport } from './components/Step4OptimizeExport'
import { useAppStore } from './store/appStore'

const { Header, Content, Sider } = Layout
const { Title, Text } = Typography

function App() {
  const currentStep = useAppStore((s) => s.currentStep)
  const setCurrentStep = useAppStore((s) => s.setCurrentStep)

  const steps = [
    { title: 'Input & Parse', description: '需求输入与结构化解析' },
    { title: 'Risk Analysis', description: '风险矩阵与覆盖项' },
    { title: 'Generate & Evaluate', description: '用例生成与人工复核' },
    { title: 'Optimize & Export', description: '套件优化与导出' },
  ]

  const content = [
    <Step1InputParse key="s1" />,
    <Step2RiskAnalysis key="s2" />,
    <Step3GenerateEvaluate key="s3" />,
    <Step4OptimizeExport key="s4" />,
  ][currentStep] ?? <Step1InputParse />

  return (
    <Layout className="app-shell" hasSider>
      <Sider width={280} theme="light" className="app-sider" style={{ borderRight: '1px solid var(--border)' }}>
        <div className="brand sider-brand">
          <div className="brand-mark" />
          <Title level={4} className="brand-title" style={{ margin: 0 }}>
            AutoTestDesign
          </Title>
        </div>
        <div className="sider-steps">
          <Steps direction="vertical" current={currentStep} onChange={setCurrentStep} items={steps} />
        </div>
      </Sider>

      <Layout>
        <Header className="app-header app-header-bar">
          <Text style={{ fontWeight: 500 }}>AutoTest Pipeline</Text>
        </Header>
        <Content className="app-content">{content}</Content>
      </Layout>
    </Layout>
  )
}

export default App
