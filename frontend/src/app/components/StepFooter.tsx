import { Button, Space } from 'antd'
import { workflowRoutes } from '@/app/routes'
import { useAppStore } from '@/app/store/appStore'

export function StepFooter({ onNavigate }: { onNavigate: (step: number) => void }) {
  const currentStep = useAppStore((s) => s.currentStep)
  const currentRoute = workflowRoutes[currentStep] ?? workflowRoutes[0]
  const nextRoute = workflowRoutes[Math.min(currentStep + 1, workflowRoutes.length - 1)]

  return (
    <div className="step-footer">
      <Space wrap>
        <Button disabled={currentStep <= 0} onClick={() => onNavigate(currentStep - 1)}>
          上一阶段
        </Button>
        <Button
          type="primary"
          disabled={currentStep >= workflowRoutes.length - 1}
          onClick={() => onNavigate(currentStep + 1)}
        >
          下一阶段：{nextRoute.short}
        </Button>
      </Space>
      <span className="step-footer-hint">
        阶段 {currentStep + 1} / {workflowRoutes.length} · {currentRoute.title}
      </span>
    </div>
  )
}
