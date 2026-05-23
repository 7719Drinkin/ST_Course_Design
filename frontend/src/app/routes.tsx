import { ExportPage } from '@/modules/export/pages/ExportPage'
import { RequirementsPage } from '@/modules/requirements/pages/RequirementsPage'
import { RiskAnalysisPage } from '@/modules/risk-analysis/pages/RiskAnalysisPage'
import { TestDesignPage } from '@/modules/test-design/pages/TestDesignPage'

export const workflowRoutes = [
  {
    id: 'requirements',
    title: 'Input & Parse',
    description: '需求输入与结构化解析',
    short: '解析',
    accent: 'Ingest',
    render: () => <RequirementsPage />,
  },
  {
    id: 'risk-analysis',
    title: 'Risk Analysis',
    description: '风险矩阵与覆盖项',
    short: '风险',
    accent: 'Prioritize',
    render: () => <RiskAnalysisPage />,
  },
  {
    id: 'test-design',
    title: 'Generate & Evaluate',
    description: '用例生成与人工复核',
    short: '复核',
    accent: 'Review',
    render: () => <TestDesignPage />,
  },
  {
    id: 'export',
    title: 'Optimize & Export',
    description: '套件优化与导出',
    short: '导出',
    accent: 'Release',
    render: () => <ExportPage />,
  },
] as const
