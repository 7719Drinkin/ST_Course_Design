import { ExportPage } from '@/modules/export/pages/ExportPage'
import { RequirementsPage } from '@/modules/requirements/pages/RequirementsPage'
import { CoverageStrategyPage } from '@/modules/risk-analysis/pages/CoverageStrategyPage'
import { RiskAnalysisPage } from '@/modules/risk-analysis/pages/RiskAnalysisPage'
import { EvidencePage } from '@/modules/test-design/pages/EvidencePage'
import { TestDesignPage } from '@/modules/test-design/pages/TestDesignPage'

export const workflowRoutes = [
  {
    id: 'intake-parse',
    title: '输入与结构化解析',
    description: '直接输入或需求文档(TXT, MarkDown, PDF, DOCX)，完成需求整理和结构化解析。',
    short: '输入',
    accent: '输入',
    render: () => <RequirementsPage />,
  },
  {
    id: 'concept-risk',
    title: '概念识别与风险评分',
    description: '识别业务对象、操作、状态和约束，并对需求或覆盖项计算风险优先级。',
    short: '风险',
    accent: '评估',
    render: () => <RiskAnalysisPage />,
  },
  {
    id: 'coverage-strategy',
    title: '覆盖项与覆盖策略',
    description: '生成覆盖项，并为每个覆盖项选择合适的测试设计方法。',
    short: '覆盖',
    accent: '设计',
    render: () => <CoverageStrategyPage />,
  },
  {
    id: 'case-lab',
    title: '测试用例与状态路径',
    description: '生成可追溯测试用例，复核状态路径覆盖和期望结果。',
    short: '用例',
    accent: '生成',
    render: () => <TestDesignPage />,
  },
  {
    id: 'evidence-improve',
    title: '生成依据与差量改进',
    description: '审查生成依据、人工修订记录、差量更新和结果分析。',
    short: '证据',
    accent: '改进',
    render: () => <EvidencePage />,
  },
  {
    id: 'optimize-export',
    title: '测试套件优化与导出',
    description: '按覆盖保持和风险优先目标优化测试套件，并导出完整证据包。',
    short: '导出',
    accent: '发布',
    render: () => <ExportPage />,
  },
] as const

export type WorkflowRoute = (typeof workflowRoutes)[number]
