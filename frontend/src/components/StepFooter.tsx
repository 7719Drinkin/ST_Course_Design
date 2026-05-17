import { Button, Space } from 'antd'
import { useAppStore } from '../store/appStore'

const STEP_LABELS = ['需求解析', '风险分析', '生成复核', '优化导出']

export function StepFooter() {
  const currentStep = useAppStore((s) => s.currentStep)
  const setCurrentStep = useAppStore((s) => s.setCurrentStep)

  return (
    <div className="step-footer">
      <Space>
        <Button disabled={currentStep <= 0} onClick={() => setCurrentStep(currentStep - 1)}>
          上一步
        </Button>
        <Button
          type="primary"
          disabled={currentStep >= 3}
          onClick={() => setCurrentStep(currentStep + 1)}
        >
          下一步：{STEP_LABELS[Math.min(currentStep + 1, 3)]}
        </Button>
      </Space>
      <span className="step-footer-hint">Step {currentStep + 1} / 4 · {STEP_LABELS[currentStep]}</span>
    </div>
  )
}
