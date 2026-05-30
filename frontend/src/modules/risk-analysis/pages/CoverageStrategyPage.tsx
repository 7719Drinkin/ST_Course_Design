import { useEffect, useMemo, useState } from 'react'
import { Button, Card, Input, Select, Space, Table, Tag, Typography } from 'antd'
import { TECHNIQUE_OPTIONS, useAppStore } from '@/app/store/appStore'
import { getCoverageGoals } from '@/modules/risk-analysis/api/coverageApi'
import { getCoverageItems } from '@/modules/risk-analysis/api/strategyApi'
import { toAnalyzedRequirements } from '@/modules/risk-analysis/api/riskApi'
import { RevisionPanel } from '@/shared/components/RevisionPanel'
import { DataStatusTag, WorkflowEmptyState } from '@/shared/components/WorkflowFeedback'
import type { CoverageItem, CoverageStatus, Technique } from '@/shared/types'

const { Paragraph, Text } = Typography

function normalizeCoverageItem(item: CoverageItem): CoverageItem {
  const techniques: Technique[] = item.techniques?.length
    ? item.techniques
    : item.technique
      ? [item.technique]
      : ['EP']
  return {
    ...item,
    techniques,
    technique: item.technique ?? techniques[0],
    status: item.status ?? 'ai_generated',
  }
}

export function CoverageStrategyPage() {
  const [coverageLive, setCoverageLive] = useState<boolean>()
  const [strategyLive, setStrategyLive] = useState<boolean>()

  const requirements = useAppStore((s) => s.requirements)
  const riskEntries = useAppStore((s) => s.riskEntries)
  const coverageItems = useAppStore((s) => s.coverageItems)
  const setCoverageItems = useAppStore((s) => s.setCoverageItems)
  const updateCoverageItem = useAppStore((s) => s.updateCoverageItem)
  const addCoverageItem = useAppStore((s) => s.addCoverageItem)
  const coverageGoals = useAppStore((s) => s.coverageGoals)
  const setCoverageGoals = useAppStore((s) => s.setCoverageGoals)
  const pipelineActive = useAppStore((s) => s.pipelineActive)

  const reqIdsKey = requirements.map((requirement) => requirement.requirement_id).join(',')
  const riskKey = riskEntries.map((entry) => `${entry.requirement_id}:${entry.risk_score ?? entry.score}`).join(',')
  const goalsKey = coverageGoals.map((item) => item.coverage_goal_id).join(',')
  const hasRequirements = requirements.length > 0
  const analyzedRequirements = useMemo(() => toAnalyzedRequirements(requirements), [requirements])

  useEffect(() => {
    if (pipelineActive) return
    if (!reqIdsKey) {
      queueMicrotask(() => {
        setCoverageGoals([])
        setCoverageItems([])
      })
      return
    }
    getCoverageGoals(analyzedRequirements, riskEntries).then((result) => {
      setCoverageGoals(result.data)
      setCoverageLive(result.isLive)
    })
  }, [pipelineActive, analyzedRequirements, reqIdsKey, riskEntries, riskKey, setCoverageItems, setCoverageGoals])

  useEffect(() => {
    if (pipelineActive) return
    if (!goalsKey) {
      queueMicrotask(() => setCoverageItems([]))
      return
    }
    getCoverageItems(coverageGoals, analyzedRequirements, riskEntries).then((result) => {
      setCoverageItems(result.data.map(normalizeCoverageItem))
      setStrategyLive(result.isLive)
    })
  }, [pipelineActive, coverageGoals, goalsKey, analyzedRequirements, riskEntries, setCoverageItems])

  const techniqueCounts = useMemo(() => {
    const counts: Record<Technique, number> = { EP: 0, BVA: 0, DT: 0, FSM: 0 }
    coverageItems.forEach((item) => {
      item.techniques.forEach((technique) => {
        counts[technique] += 1
      })
    })
    return counts
  }, [coverageItems])

  const highRiskIds = new Set(
    riskEntries.filter((entry) => entry.level === 'High').map((entry) => entry.requirement_id),
  )

  const handleAddCoverage = () => {
    const baseRequirementId = requirements[0]?.requirement_id
    if (!baseRequirementId) return
    const index = coverageItems.length + 1
    addCoverageItem({
      coverage_item_id: `COV-AUT-${String(index).padStart(3, '0')}`,
      requirement_id: baseRequirementId,
      description: '设计者新增覆盖项',
      technique: 'EP',
      techniques: ['EP'],
      strategy: '由设计者在覆盖审查中补充',
      strategy_rationale: '补充 AI 未识别但对 AUT 行为重要的覆盖点',
      status: 'human_added',
      source: 'designer',
      designer_added: true,
    })
  }

  return (
    <Space direction="vertical" size={24} className="full-width">
      {!hasRequirements ? (
        <WorkflowEmptyState
          title="等待需求与风险数据"
          description="覆盖项和覆盖策略必须基于已解析的 AUT 需求生成。请先完成输入解析和风险评分。"
        />
      ) : (
        <>
          <div className="workbench-grid workbench-grid-2">
            <Card title="覆盖项识别">
              <Space direction="vertical" size={16} className="full-width">
                <DataStatusTag isLive={coverageLive} />
                <div className="metric-band">
                  <div>
                    <span>{coverageGoals.length}</span>
                    <Text>覆盖目标</Text>
                  </div>
                  <div>
                    <span>{coverageItems.filter((item) => item.status === 'human_added').length}</span>
                    <Text>人工新增</Text>
                  </div>
                  <div>
                    <span>{coverageItems.filter((item) => highRiskIds.has(item.requirement_id)).length}</span>
                    <Text>高风险来源</Text>
                  </div>
                </div>
                <Paragraph>
                  设计者必须能新增、修订、拒绝覆盖项。每次修改都会进入 Revision 证据轨。
                </Paragraph>
              </Space>
            </Card>

            <Card title="覆盖策略">
              <Space direction="vertical" size={16} className="full-width">
                <DataStatusTag isLive={strategyLive} />
                <div className="technique-strip">
                  {TECHNIQUE_OPTIONS.map((technique) => (
                    <span key={technique}>
                      <strong>{technique}</strong>
                      {techniqueCounts[technique]}
                    </span>
                  ))}
                </div>
                <Paragraph>
                  EP、BVA、DT 的选择由后端生成建议，前端负责让设计者审查和修改。
                </Paragraph>
              </Space>
            </Card>
          </div>

          <Card
            title="覆盖项审查"
            extra={
              <Space wrap>
                <Button onClick={handleAddCoverage}>新增覆盖项</Button>
              </Space>
            }
          >
            <Table
              size="small"
              rowKey="coverage_item_id"
              pagination={{ pageSize: 7 }}
              scroll={{ x: 1120 }}
              dataSource={coverageItems}
              columns={[
                {
                  title: '覆盖编号',
                  dataIndex: 'coverage_item_id',
                  width: 150,
                  render: (value: string, record: CoverageItem) => (
                    <Space size={4}>
                      <Text strong>{value}</Text>
                      {record.designer_added && <Tag color="blue">人工</Tag>}
                    </Space>
                  ),
                },
                { title: '来源需求', dataIndex: 'requirement_id', width: 130 },
                {
                  title: '覆盖内容',
                  dataIndex: 'description',
                  width: 280,
                  render: (value: string, record: CoverageItem) => (
                    <Input
                      size="small"
                      value={value}
                      onChange={(event) =>
                        updateCoverageItem(record.coverage_item_id, {
                          description: event.target.value,
                          status: record.status === 'ai_generated' ? 'human_revised' : record.status,
                        })
                      }
                    />
                  ),
                },
                {
                  title: '方法',
                  dataIndex: 'techniques',
                  width: 190,
                  render: (value: Technique[], record: CoverageItem) => (
                    <Select
                      size="small"
                      mode="multiple"
                      value={value}
                      style={{ width: '100%' }}
                      onChange={(techniques) =>
                        updateCoverageItem(record.coverage_item_id, {
                          techniques,
                          technique: techniques[0],
                          status: 'human_revised',
                        }, undefined, true)
                      }
                      options={TECHNIQUE_OPTIONS.map((technique) => ({
                        value: technique,
                        label: technique,
                      }))}
                    />
                  ),
                },
                {
                  title: '状态',
                  dataIndex: 'status',
                  width: 150,
                  render: (value: CoverageStatus, record: CoverageItem) => (
                    <Select
                      size="small"
                      value={value}
                      style={{ width: '100%' }}
                      onChange={(status) => updateCoverageItem(record.coverage_item_id, { status }, undefined, true)}
                      options={[
                        { value: 'ai_generated', label: '系统生成' },
                        { value: 'human_revised', label: '人工修订' },
                        { value: 'human_added', label: '人工新增' },
                        { value: 'rejected', label: '已拒绝' },
                      ]}
                    />
                  ),
                },
                {
                  title: '策略理由',
                  dataIndex: 'strategy_rationale',
                  ellipsis: true,
                  render: (value: string | undefined, record: CoverageItem) => (
                    <Input
                      size="small"
                      value={value ?? ''}
                      onChange={(event) =>
                        updateCoverageItem(record.coverage_item_id, {
                          strategy_rationale: event.target.value,
                        })
                      }
                    />
                  ),
                },
              ]}
            />
          </Card>

          <Card title="覆盖策略审查">
            <Table
              size="small"
              rowKey="coverage_item_id"
              pagination={{ pageSize: 6 }}
              scroll={{ x: 980 }}
              dataSource={coverageItems}
              columns={[
                { title: '覆盖项', dataIndex: 'coverage_item_id', width: 160 },
                {
                  title: '方法',
                  dataIndex: 'technique',
                  width: 120,
                  render: (value: Technique, record: CoverageItem) => (
                    <Select
                      size="small"
                      value={value}
                      style={{ width: '100%' }}
                      onChange={(technique) =>
                        updateCoverageItem(record.coverage_item_id, {
                          technique,
                          techniques: [technique],
                          status: 'human_revised',
                        }, undefined, true)
                      }
                      options={TECHNIQUE_OPTIONS.map((technique) => ({
                        value: technique,
                        label: technique,
                      }))}
                    />
                  ),
                },
                { title: '技术理由', dataIndex: 'technique_reason', width: 220, ellipsis: true },
                {
                  title: '选择理由',
                  dataIndex: 'strategy_rationale',
                  ellipsis: true,
                  render: (value: string, record: CoverageItem) => (
                    <Input
                      size="small"
                      value={value ?? ''}
                      onChange={(event) =>
                        updateCoverageItem(record.coverage_item_id, {
                          strategy_rationale: event.target.value,
                        })
                      }
                    />
                  ),
                },
              ]}
            />
          </Card>
        </>
      )}

      <RevisionPanel />
    </Space>
  )
}
