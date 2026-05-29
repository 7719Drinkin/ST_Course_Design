import { useEffect, useMemo, useState } from 'react'
import { Button, Card, Descriptions, List, Select, Space, Table, Tag, Typography, message } from 'antd'
import { useAppStore } from '@/app/store/appStore'
import { getAnalysisResults, regenerateFromRevision } from '@/modules/test-design/api/evidenceApi'
import { isBackendRevisionSupported } from '@/modules/test-design/api/revisionsApi'
import { RevisionPanel } from '@/shared/components/RevisionPanel'
import { DataStatusTag, WorkflowEmptyState } from '@/shared/components/WorkflowFeedback'
import type { AnalysisResult, PromptEvidence, RevisionLog, TestCase } from '@/shared/types'

const { Paragraph, Text } = Typography

export function EvidencePage() {
  const [selectedRevisionId, setSelectedRevisionId] = useState<string>()
  const [regenerateLive, setRegenerateLive] = useState<boolean>()
  const [analysisLive, setAnalysisLive] = useState<boolean>()

  const promptEvidence = useAppStore((s) => s.promptEvidence)
  const setPromptEvidence = useAppStore((s) => s.setPromptEvidence)
  const requirements = useAppStore((s) => s.requirements)
  const coverageItems = useAppStore((s) => s.coverageItems)
  const strategies = useAppStore((s) => s.strategies)
  const riskEntries = useAppStore((s) => s.riskEntries)
  const testCases = useAppStore((s) => s.testCases)
  const setTestCases = useAppStore((s) => s.setTestCases)
  const revisions = useAppStore((s) => s.revisions)
  const regenerateResult = useAppStore((s) => s.regenerateResult)
  const setRegenerateResult = useAppStore((s) => s.setRegenerateResult)
  const analysisResults = useAppStore((s) => s.analysisResults)
  const setAnalysisResults = useAppStore((s) => s.setAnalysisResults)

  const backendRevisions = revisions.filter(isBackendRevisionSupported)
  const latestRevision = backendRevisions.at(-1)
  const entityLabels: Record<RevisionLog['entity_type'], string> = {
    requirement: '需求',
    parsed_requirement: '结构化需求',
    risk_result: '风险',
    risk: '风险',
    coverage: '覆盖项',
    coverage_item: '覆盖项',
    strategy: '策略',
    test_case: '测试用例',
    fsm: '状态路径',
    analysis: '分析结果',
  }

  const analysisStatusLabels: Record<string, string> = {
    covered: '已覆盖',
    missing: '缺失',
    improved: '已改进',
    needs_review: '待审查',
  }

  const revisionOptions = [...backendRevisions].reverse().map((revision) => ({
    value: revision.id,
    label: `${revision.id} · ${entityLabels[revision.entity_type]} · ${revision.entity_id}`,
  }))

  useEffect(() => {
    if (requirements.length === 0) {
      setAnalysisResults([])
      return
    }
    getAnalysisResults().then((result) => {
      setAnalysisResults(result.data)
      setAnalysisLive(result.isLive)
    })
  }, [requirements.length, setAnalysisResults])

  const improvementStats = useMemo(() => {
    const statusCounts = analysisResults.reduce<Record<string, number>>((acc, item) => {
      acc[item.status] = (acc[item.status] ?? 0) + 1
      return acc
    }, {})
    return {
      missing: statusCounts.missing ?? 0,
      improved: statusCounts.improved ?? 0,
      needsReview: statusCounts.needs_review ?? 0,
    }
  }, [analysisResults])

  const handleRegenerate = async () => {
    const revisionId = selectedRevisionId ?? latestRevision?.id
    if (!revisionId) return
    try {
      const result = await regenerateFromRevision(revisionId, {
        requirements,
        coverage_items: coverageItems,
        strategies,
        risk_results: riskEntries,
        test_cases: testCases,
      })
      setRegenerateResult(result.data)
      setTestCases(mergeRegeneratedTestCases(testCases, result.data))
      if (result.data.prompt_evidence?.length) {
        setPromptEvidence(mergePromptEvidence(promptEvidence, result.data.prompt_evidence))
      }
      setRegenerateLive(result.isLive)
    } catch {
      setRegenerateLive(false)
      message.error('LLM 再生成失败，请检查后端 LLM 配置或 Prompt 输出。')
    }
  }

  if (requirements.length === 0 && testCases.length === 0) {
    return (
      <Space direction="vertical" size={24} className="full-width">
        <WorkflowEmptyState
          title="等待可分析的测试设计结果"
          description="Prompt 证据、差量再生成和结果分析必须建立在真实需求、覆盖项和测试用例之上。"
        />
      </Space>
    )
  }

  return (
    <Space direction="vertical" size={24} className="full-width">
      <div className="workbench-grid workbench-grid-3">
        <Card title="生成依据">
          <Space direction="vertical" size={12} className="full-width">
            <div className="metric-band">
              <div>
                <span>{promptEvidence.length}</span>
                <Text>依据记录</Text>
              </div>
              <div>
                <span>{promptEvidence.reduce((sum, item) => sum + (item.source_context_ids?.length ?? 0), 0)}</span>
                <Text>引用材料</Text>
              </div>
              <div>
                <span>{promptEvidence.filter((item) => item.output_summary).length}</span>
                <Text>已有摘要</Text>
              </div>
            </div>
            <Paragraph>
              这里汇总生成过程使用的依据、人工修订记录和修改后的影响范围。
            </Paragraph>
          </Space>
        </Card>

        <Card title="差量更新">
          <Space direction="vertical" size={12} className="full-width">
            <DataStatusTag isLive={regenerateLive} />
            <Select
              placeholder="选择修订记录"
              value={selectedRevisionId ?? latestRevision?.id}
              onChange={setSelectedRevisionId}
              options={revisionOptions}
              className="full-width"
            />
            <Button
              type="primary"
              disabled={revisionOptions.length === 0}
              onClick={handleRegenerate}
            >
              根据 Revision 再生成
            </Button>
          </Space>
        </Card>

        <Card title="结果分析">
          <Space direction="vertical" size={12} className="full-width">
            <DataStatusTag isLive={analysisLive} />
            <div className="metric-band metric-band-tight">
              <div>
                <span>{improvementStats.missing}</span>
                <Text>缺失</Text>
              </div>
              <div>
                <span>{improvementStats.improved}</span>
                <Text>已改进</Text>
              </div>
              <div>
                <span>{improvementStats.needsReview}</span>
                <Text>待审查</Text>
              </div>
            </div>
          </Space>
        </Card>
      </div>

      <Card title="生成依据明细">
        <Table
          size="small"
          rowKey={(record: PromptEvidence) => `${record.prompt_template_id}-${record.model_name}`}
          pagination={{ pageSize: 6 }}
          scroll={{ x: 980 }}
          dataSource={promptEvidence}
          columns={[
            {
              title: '引用材料',
              dataIndex: 'source_context_ids',
              width: 160,
              render: (value?: string[]) => <Tag>{value?.length ?? 0} 条</Tag>,
            },
            {
              title: '生成摘要',
              dataIndex: 'output_summary',
              ellipsis: true,
              render: (value: string | undefined) => value || <Text type="secondary">等待生成</Text>,
            },
          ]}
        />
      </Card>

      <div className="workbench-grid workbench-grid-2">
        <Card title="差量更新结果">
          {regenerateResult ? (
            <Descriptions size="small" column={2} bordered>
              <Descriptions.Item label="新增">{Object.keys(regenerateResult.created).length}</Descriptions.Item>
              <Descriptions.Item label="更新">{Object.keys(regenerateResult.updated).length}</Descriptions.Item>
              <Descriptions.Item label="未变化">{Object.keys(regenerateResult.unchanged).length}</Descriptions.Item>
              <Descriptions.Item label="已过期">{Object.keys(regenerateResult.deprecated).length}</Descriptions.Item>
            </Descriptions>
          ) : (
            <Text type="secondary">选择一条修订记录后，可以重新计算受影响的结果。</Text>
          )}
        </Card>

        <Card title="修订记录">
          {revisions.length === 0 ? (
            <Text type="secondary">暂无人工修订。设计者修改覆盖项、策略或用例后会生成 REV-*。</Text>
          ) : (
            <List
              size="small"
              dataSource={[...revisions].reverse().slice(0, 6)}
              renderItem={(revision: RevisionLog) => (
                <List.Item>
                  <Space direction="vertical" size={2}>
                    <Text strong>{revision.id}</Text>
                    <Text type="secondary">
                      {entityLabels[revision.entity_type]} · {revision.entity_id} · {revision.field}
                    </Text>
                  </Space>
                </List.Item>
              )}
            />
          )}
        </Card>
      </div>

      <Card title="追溯分析">
        <Table
          size="small"
          rowKey={(record: AnalysisResult) =>
            `${record.requirement_id}-${record.coverage_item_id}-${record.test_id}`
          }
          pagination={{ pageSize: 8 }}
          scroll={{ x: 1000 }}
          dataSource={analysisResults}
          columns={[
            { title: '需求', dataIndex: 'requirement_id', width: 140 },
            { title: '覆盖项', dataIndex: 'coverage_item_id', width: 140 },
            { title: '测试用例', dataIndex: 'test_id', width: 140 },
            {
              title: '状态',
              dataIndex: 'status',
              width: 140,
              render: (value: string) => <Tag>{analysisStatusLabels[value] ?? value}</Tag>,
            },
            { title: '缺口', dataIndex: 'gap', ellipsis: true },
            { title: '改进建议', dataIndex: 'improvement', ellipsis: true },
          ]}
        />
      </Card>

      <RevisionPanel />
    </Space>
  )
}

function mergeRegeneratedTestCases(current: TestCase[], result: {
  created: Record<string, unknown>
  updated: Record<string, unknown>
  deprecated: Record<string, unknown>
}) {
  const incoming = [
    ...testCasesFromGroup(result.created),
    ...testCasesFromGroup(result.updated),
    ...testCasesFromGroup(result.deprecated),
  ]
  if (incoming.length === 0) return current

  const byId = new Map(current.map((item) => [item.test_id, item]))
  incoming.forEach((item) => {
    if (item.test_id) byId.set(item.test_id, item)
  })
  return [...byId.values()]
}

function testCasesFromGroup(group: Record<string, unknown> | undefined): TestCase[] {
  const value = group?.test_cases
  return Array.isArray(value) ? value.filter(isTestCase) : []
}

function isTestCase(value: unknown): value is TestCase {
  return Boolean(value && typeof value === 'object' && 'test_id' in value)
}

function mergePromptEvidence(current: PromptEvidence[], incoming: PromptEvidence[]) {
  const byId = new Map(current.map((item) => [item.evidence_id ?? `${item.prompt_template_id}-${item.model_name}`, item]))
  incoming.forEach((item) => {
    const key = item.evidence_id ?? `${item.prompt_template_id}-${item.model_name}`
    byId.set(key, item)
  })
  return [...byId.values()]
}
