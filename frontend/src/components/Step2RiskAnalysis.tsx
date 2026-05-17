import { useEffect, useMemo, useState } from 'react'
import { Button, Card, Col, Input, List, Row, Select, Space, Table, Tag, Typography } from 'antd'
import { useAppStore, TECHNIQUE_OPTIONS } from '../store/appStore'
import { getCoverageItems, getRiskData } from '../services/api'
import type { CoverageItem, RiskLevel, Technique } from '../types'
import { DataStatusTag } from './shared'
import { RevisionPanel } from './RevisionPanel'
import { ImprovementSummary } from './ImprovementSummary'

const { Title, Text } = Typography

function buildHeatmapMatrix(
  entries: { impact: number; likelihood: number }[],
  filter?: { impact: number; likelihood: number } | null,
) {
  const matrix = Array.from({ length: 5 }, () => Array<number>(5).fill(0))
  entries.forEach(({ impact, likelihood }) => {
    const r = Math.min(5, Math.max(1, likelihood)) - 1
    const c = Math.min(5, Math.max(1, impact)) - 1
    if (!filter || (filter.impact === impact && filter.likelihood === likelihood)) {
      matrix[r][c]++
    }
  })
  return matrix
}

function getCellBg(count: number, row: number, col: number) {
  const score = (row + 1) * (col + 1)
  if (count === 0) return score >= 15 ? 'rgba(248,113,113,0.12)' : score >= 8 ? 'rgba(250,204,21,0.12)' : 'rgba(134,239,172,0.12)'
  if (score >= 15) return '#f87171'
  if (score >= 8) return '#facc15'
  return '#86efac'
}

export function Step2RiskAnalysis() {
  const [cellFilter, setCellFilter] = useState<{ impact: number; likelihood: number } | null>(null)
  const [riskLive, setRiskLive] = useState<boolean>()
  const [riskPending, setRiskPending] = useState<string>()

  const requirements = useAppStore((s) => s.requirements)
  const riskEntries = useAppStore((s) => s.riskEntries)
  const setRiskEntries = useAppStore((s) => s.setRiskEntries)
  const updateRiskLevel = useAppStore((s) => s.updateRiskLevel)
  const coverageItems = useAppStore((s) => s.coverageItems)
  const setCoverageItems = useAppStore((s) => s.setCoverageItems)
  const updateCoverageItem = useAppStore((s) => s.updateCoverageItem)
  const addCoverageItem = useAppStore((s) => s.addCoverageItem)
  const setCurrentStep = useAppStore((s) => s.setCurrentStep)

  const reqIdsKey = requirements.map((r) => r.requirement_id).join(',')

  useEffect(() => {
    const ids = reqIdsKey ? reqIdsKey.split(',') : undefined
    getRiskData(ids).then((r) => {
      setRiskEntries(r.data)
      setRiskLive(r.isLive)
      setRiskPending(r.pendingFrom)
    })
    getCoverageItems(ids).then((r) => setCoverageItems(r.data))
  }, [reqIdsKey, setRiskEntries, setCoverageItems])

  const matrix = useMemo(() => buildHeatmapMatrix(riskEntries, cellFilter), [riskEntries, cellFilter])

  const displayedRisk = useMemo(() => {
    if (!cellFilter) return riskEntries
    return riskEntries.filter(
      (e) => e.impact === cellFilter.impact && e.likelihood === cellFilter.likelihood,
    )
  }, [riskEntries, cellFilter])

  const highCount = riskEntries.filter((e) => e.level === 'High').length
  const medCount = riskEntries.filter((e) => e.level === 'Medium').length
  const lowCount = riskEntries.filter((e) => e.level === 'Low').length

  const handleAddCoverage = () => {
    const baseReq = requirements[0]?.requirement_id ?? 'REQ-AUT-008'
    const n = coverageItems.length + 1
    const item: CoverageItem = {
      coverage_item_id: `COV-AUT-DESIGN-${String(n).padStart(3, '0')}`,
      requirement_id: baseReq,
      description: 'Designer-added coverage item',
      techniques: ['EP'],
      strategy_rationale: 'Added during interactive review',
      designer_added: true,
    }
    addCoverageItem(item)
  }

  return (
    <Space direction="vertical" size={24} className="full-width">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span>
          <Title level={4} style={{ margin: 0, display: 'inline' }}>风险矩阵 (FR2.0)</Title>
          <DataStatusTag isLive={riskLive} pendingFrom={riskPending} />
        </span>
        <Button type="primary" onClick={() => setCurrentStep(2)}>下一步: 生成与复核</Button>
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={14}>
          <Card title="Impact × Likelihood 热力图（点击单元格筛选）">
            <div className="heatmap">
              {matrix.flatMap((row, rIdx) =>
                row.map((count, cIdx) => (
                  <button
                    key={`${rIdx}-${cIdx}`}
                    type="button"
                    className="heatmap-cell heatmap-cell-btn"
                    style={{ background: getCellBg(count, rIdx, cIdx) }}
                    onClick={() =>
                      setCellFilter(
                        cellFilter?.impact === cIdx + 1 && cellFilter?.likelihood === rIdx + 1
                          ? null
                          : { impact: cIdx + 1, likelihood: rIdx + 1 },
                      )
                    }
                  >
                    {count > 0 ? count : ''}
                  </button>
                )),
              )}
            </div>
            {cellFilter && (
              <Text type="secondary" style={{ fontSize: 12, marginTop: 8, display: 'block' }}>
                筛选：Impact={cellFilter.impact}, Likelihood={cellFilter.likelihood}
                <Button type="link" size="small" onClick={() => setCellFilter(null)}>清除</Button>
              </Text>
            )}
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card title="Risk Snapshot">
            <List
              size="small"
              dataSource={[
                `高风险：${highCount}`,
                `中风险：${medCount}`,
                `低风险：${lowCount}`,
              ]}
              renderItem={(item) => <List.Item>{item}</List.Item>}
            />
            <Table
              size="small"
              pagination={{ pageSize: 6 }}
              style={{ marginTop: 12 }}
              rowKey="requirement_id"
              dataSource={displayedRisk}
              columns={[
                { title: 'ID', dataIndex: 'requirement_id', ellipsis: true, width: 110 },
                { title: 'Score', dataIndex: 'score', width: 56 },
                {
                  title: 'I×L',
                  width: 64,
                  render: (_, r) => `${r.impact}×${r.likelihood}`,
                },
                {
                  title: 'Priority',
                  dataIndex: 'level',
                  width: 110,
                  render: (v: RiskLevel, record) => (
                    <Select
                      size="small"
                      value={v}
                      style={{ width: 96 }}
                      onChange={(level) => updateRiskLevel(record.requirement_id, level)}
                      options={[
                        { value: 'High', label: 'High' },
                        { value: 'Medium', label: 'Medium' },
                        { value: 'Low', label: 'Low' },
                      ]}
                    />
                  ),
                },
              ]}
            />
          </Card>
        </Col>
      </Row>

      <Card
        title="Coverage Items · 覆盖项识别与策略 (Mainly)"
        extra={
          <Button size="small" onClick={handleAddCoverage}>
            新增覆盖项
          </Button>
        }
      >
        <Table
          size="small"
          rowKey="coverage_item_id"
          pagination={{ pageSize: 6 }}
          dataSource={coverageItems}
          columns={[
            {
              title: 'Coverage ID',
              dataIndex: 'coverage_item_id',
              width: 150,
              render: (v: string, record) => (
                <Space size={4}>
                  {v}
                  {record.designer_added && <Tag color="blue">新增</Tag>}
                </Space>
              ),
            },
            { title: 'Requirement', dataIndex: 'requirement_id', width: 120 },
            {
              title: 'Description',
              dataIndex: 'description',
              render: (v, record) => (
                <Input
                  size="small"
                  value={v}
                  onChange={(e) =>
                    updateCoverageItem(record.coverage_item_id, { description: e.target.value })
                  }
                />
              ),
            },
            {
              title: 'Techniques',
              dataIndex: 'techniques',
              width: 160,
              render: (t: Technique[], record) => (
                <Select
                  size="small"
                  mode="multiple"
                  value={t}
                  style={{ width: '100%' }}
                  onChange={(techniques) =>
                    updateCoverageItem(record.coverage_item_id, { techniques })
                  }
                  options={TECHNIQUE_OPTIONS.map((x) => ({ value: x, label: x }))}
                />
              ),
            },
            {
              title: 'Strategy',
              dataIndex: 'strategy_rationale',
              ellipsis: true,
              render: (v, record) => (
                <Input
                  size="small"
                  value={v ?? ''}
                  onChange={(e) =>
                    updateCoverageItem(record.coverage_item_id, {
                      strategy_rationale: e.target.value,
                    })
                  }
                />
              ),
            },
          ]}
        />
      </Card>

      <ImprovementSummary />
      <RevisionPanel />
    </Space>
  )
}
