import { useEffect, useMemo, useState } from 'react'
import { Button, Card, InputNumber, Select, Space, Table, Tag, Typography } from 'antd'
import { useAppStore } from '@/app/store/appStore'
import { getRiskData } from '@/modules/risk-analysis/api/riskApi'
import { RevisionPanel } from '@/shared/components/RevisionPanel'
import { DataStatusTag, WorkflowEmptyState } from '@/shared/components/WorkflowFeedback'
import type { RiskEntry, RiskLevel, TestPriority } from '@/shared/types'

const { Text } = Typography

function buildHeatmapMatrix(entries: RiskEntry[]) {
  const matrix = Array.from({ length: 5 }, () => Array<number>(5).fill(0))
  entries.forEach(({ impact, likelihood }) => {
    const row = Math.min(5, Math.max(1, likelihood)) - 1
    const col = Math.min(5, Math.max(1, impact)) - 1
    matrix[row][col] += 1
  })
  return matrix
}

function getCellBg(count: number, row: number, col: number) {
  const score = (row + 1) * (col + 1)
  if (count === 0) return score >= 15 ? 'rgba(220, 38, 38, 0.08)' : score >= 8 ? 'rgba(202, 138, 4, 0.10)' : 'rgba(15, 118, 110, 0.08)'
  if (score >= 15) return '#ef4444'
  if (score >= 8) return '#f59e0b'
  return '#2dd4bf'
}

function normalizeRisk(entry: RiskEntry): RiskEntry {
  const score = entry.score ?? entry.risk_score ?? entry.impact * entry.likelihood
  const level = entry.level ?? entry.risk_level ?? (score >= 15 ? 'High' : score >= 8 ? 'Medium' : 'Low')
  return { ...entry, score, level }
}

export function RiskAnalysisPage() {
  const [riskLive, setRiskLive] = useState<boolean>()
  const [cellFilter, setCellFilter] = useState<{ impact: number; likelihood: number } | null>(null)

  const requirements = useAppStore((s) => s.requirements)
  const riskEntries = useAppStore((s) => s.riskEntries)
  const setRiskEntries = useAppStore((s) => s.setRiskEntries)
  const updateRiskEntry = useAppStore((s) => s.updateRiskEntry)
  const pipelineActive = useAppStore((s) => s.pipelineActive)

  const reqIdsKey = requirements.map((requirement) => requirement.requirement_id).join(',')
  const hasRequirements = requirements.length > 0

  useEffect(() => {
    if (pipelineActive) return
    if (!reqIdsKey) {
      setRiskEntries([])
      return
    }
    getRiskData(requirements).then((result) => {
      setRiskEntries(result.data.map(normalizeRisk))
      setRiskLive(result.isLive)
    })
  }, [pipelineActive, requirements, reqIdsKey, setRiskEntries])

  const matrix = useMemo(() => buildHeatmapMatrix(riskEntries), [riskEntries])
  const displayedRisk = useMemo(() => {
    if (!cellFilter) return riskEntries
    return riskEntries.filter(
      (entry) => entry.impact === cellFilter.impact && entry.likelihood === cellFilter.likelihood,
    )
  }, [riskEntries, cellFilter])

  const highRiskCount = riskEntries.filter((entry) => entry.level === 'High').length
  const riskStatusLive = riskEntries.length > 0 ? true : riskLive

  return (
    <Space direction="vertical" size={24} className="full-width">
      {!hasRequirements ? (
        <WorkflowEmptyState
          title="等待结构化需求"
          description="风险评分必须基于真实需求。请先在输入阶段提交需求，再继续审查风险。"
        />
      ) : (
        <>
          <div className="workbench-grid workbench-grid-1">
            <Card title="风险评分">
              <Space direction="vertical" size={16} className="full-width">
                <DataStatusTag isLive={riskStatusLive} />
                <div className="metric-band">
                  <div>
                    <span>{riskEntries.length}</span>
                    <Text>风险项</Text>
                  </div>
                  <div>
                    <span>{highRiskCount}</span>
                    <Text>High</Text>
                  </div>
                  <div>
                    <span>{riskEntries.filter((entry) => entry.test_priority === 'P1').length}</span>
                    <Text>P1</Text>
                  </div>
                </div>
                <div className="heatmap">
                  {matrix.flatMap((row, rowIndex) =>
                    row.map((count, colIndex) => (
                      <button
                        key={`${rowIndex}-${colIndex}`}
                        type="button"
                        className="heatmap-cell heatmap-cell-btn"
                        style={{ background: getCellBg(count, rowIndex, colIndex) }}
                        onClick={() =>
                          setCellFilter(
                            cellFilter?.impact === colIndex + 1 && cellFilter?.likelihood === rowIndex + 1
                              ? null
                              : { impact: colIndex + 1, likelihood: rowIndex + 1 },
                          )
                        }
                      >
                        {count > 0 ? count : ''}
                      </button>
                    )),
                  )}
                </div>
              </Space>
            </Card>
          </div>

          <Card title="风险评分审查">
            <Table
              size="small"
              rowKey="requirement_id"
              pagination={{ pageSize: 8 }}
              scroll={{ x: 980 }}
              dataSource={displayedRisk}
              columns={[
                { title: '目标', dataIndex: 'requirement_id', width: 130 },
                {
                  title: '影响', dataIndex: 'impact', width: 100,
                  render: (value: number, record: RiskEntry) => (
                    <InputNumber size="small" min={1} max={5} value={value} style={{ width: '100%' }}
                      onChange={(v) => updateRiskEntry(record.requirement_id, { impact: v ?? value })}
                    />
                  ),
                },
                {
                  title: '可能性', dataIndex: 'likelihood', width: 100,
                  render: (value: number, record: RiskEntry) => (
                    <InputNumber size="small" min={1} max={5} value={value} style={{ width: '100%' }}
                      onChange={(v) => updateRiskEntry(record.requirement_id, { likelihood: v ?? value })}
                    />
                  ),
                },
                { title: '分数', dataIndex: 'score', width: 80 },
                {
                  title: '风险等级',
                  dataIndex: 'level',
                  width: 150,
                  render: (value: RiskLevel, record: RiskEntry) => (
                    <Select
                      size="small"
                      value={value}
                      style={{ width: '100%' }}
                      onChange={(level) => updateRiskEntry(record.requirement_id, { level }, undefined, true)}
                      options={[
                        { value: 'High', label: 'High' },
                        { value: 'Medium', label: 'Medium' },
                        { value: 'Low', label: 'Low' },
                      ]}
                    />
                  ),
                },
                {
                  title: '优先级',
                  dataIndex: 'test_priority',
                  width: 120,
                  render: (value: TestPriority | undefined, record: RiskEntry) => (
                    <Select
                      size="small"
                      value={value ?? 'P2'}
                      style={{ width: '100%' }}
                      onChange={(testPriority) =>
                        updateRiskEntry(record.requirement_id, { test_priority: testPriority }, undefined, true)
                      }
                      options={[
                        { value: 'P1', label: 'P1' },
                        { value: 'P2', label: 'P2' },
                        { value: 'P3', label: 'P3' },
                      ]}
                    />
                  ),
                },
                {
                  title: '评分理由',
                  dataIndex: 'reason',
                  ellipsis: true,
                  render: (value: string | undefined) => value || <Tag>待 RAG/Prompt 返回</Tag>,
                },
              ]}
            />
            {cellFilter && (
              <Text type="secondary" className="table-hint">
                当前筛选 Impact={cellFilter.impact}, Likelihood={cellFilter.likelihood}
                <Button type="link" size="small" onClick={() => setCellFilter(null)}>
                  清除筛选
                </Button>
              </Text>
            )}
          </Card>
        </>
      )}

      <RevisionPanel />
    </Space>
  )
}
