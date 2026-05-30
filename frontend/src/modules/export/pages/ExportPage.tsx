import { useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  List,
  Modal,
  Progress,
  Row,
  Segmented,
  Space,
  Spin,
  Typography,
  message,
} from 'antd'
import { useAppStore } from '@/app/store/appStore'
import { exportApproved, mapRevisionsForExport } from '@/modules/export/api/exportApi'
import { getOptimizeResult } from '@/modules/export/api/optimizationApi'
import { ImprovementSummary } from '@/shared/components/ImprovementSummary'
import { RevisionPanel } from '@/shared/components/RevisionPanel'
import { DataStatusTag, WorkflowEmptyState } from '@/shared/components/WorkflowFeedback'
import type { OptimizeMode } from '@/shared/types'

const { Title, Text } = Typography

export function ExportPage() {
  const [mode, setMode] = useState<OptimizeMode>('risk_priority')
  const [optLive, setOptLive] = useState<boolean>()
  const [exporting, setExporting] = useState(false)
  const [previewOpen, setPreviewOpen] = useState(false)

  const testCases = useAppStore((s) => s.testCases)
  const revisions = useAppStore((s) => s.revisions)
  const riskEntries = useAppStore((s) => s.riskEntries)
  const coverageItems = useAppStore((s) => s.coverageItems)
  const requirements = useAppStore((s) => s.requirements)
  const strategies = useAppStore((s) => s.strategies)
  const promptEvidence = useAppStore((s) => s.promptEvidence)
  const analysisResults = useAppStore((s) => s.analysisResults)
  const optimizeResult = useAppStore((s) => s.optimizeResult)
  const setOptimizeResult = useAppStore((s) => s.setOptimizeResult)

  const approved = useMemo(() => testCases.filter((t) => t.status === 'Approved'), [testCases])
  const selectedForOptimize = useMemo(
    () => (approved.length > 0 ? approved : testCases),
    [approved, testCases],
  )
  const approvedIdsKey = approved.map((t) => t.test_id).join(',')
  const allIdsKey = testCases.map((t) => t.test_id).join(',')
  const hasTestCases = testCases.length > 0

  useEffect(() => {
    if (!approvedIdsKey && !allIdsKey) {
      setOptimizeResult(null)
      return
    }
    getOptimizeResult(mode, selectedForOptimize, coverageItems, riskEntries).then((r) => {
      setOptimizeResult(r.data)
      setOptLive(r.isLive)
    })
  }, [mode, approvedIdsKey, allIdsKey, selectedForOptimize, coverageItems, riskEntries, setOptimizeResult])

  const previewPayload = useMemo(
    () => ({
      test_cases: approved,
      risk_scores: riskEntries,
      coverage_items: coverageItems,
      revisions: mapRevisionsForExport(revisions),
    }),
    [approved, riskEntries, coverageItems, revisions],
  )

  const handleExport = async (format: 'json' | 'csv' | 'xlsx') => {
    if (approved.length === 0) {
      message.warning('请先批准至少一条测试用例')
      return
    }
    setExporting(true)
    try {
      const blob = await exportApproved(format, {
        requirements,
        riskEntries,
        coverageItems,
        strategies,
        testCases: approved,
        revisions,
        optimizeResult,
        promptEvidence,
        analysisResults,
      })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `autotest_export.${format}`
      a.click()
      URL.revokeObjectURL(url)
      message.success(`已导出 ${approved.length} 条已通过用例、风险分和覆盖项`)
    } catch {
      message.error('导出失败，请稍后重试或检查服务状态。')
    }
    setExporting(false)
  }

  const opt = optimizeResult
  const reductionPercent = opt
    ? Math.max(0, Math.round(((opt.before_count - opt.after_count) / Math.max(1, opt.before_count)) * 100))
    : 0

  return (
    <Space direction="vertical" size={24} className="full-width">
      <div className="stage-toolbar stage-toolbar-wrap">
        <span>
          <Title level={4} style={{ margin: 0, display: 'inline' }}>优化与导出</Title>
          {hasTestCases && <DataStatusTag isLive={optLive} />}
        </span>
        <Space wrap>
          <Button disabled={!hasTestCases} onClick={() => setPreviewOpen(true)}>导出预览</Button>
          <Button disabled={approved.length === 0} loading={exporting} onClick={() => handleExport('csv')}>
            导出已通过 CSV
          </Button>
          <Button disabled={approved.length === 0} loading={exporting} onClick={() => handleExport('json')}>
            导出已通过 JSON
          </Button>
        </Space>
      </div>

      {!hasTestCases ? (
        <WorkflowEmptyState
          title="暂无可优化的测试套件"
          description="请先完成需求解析并生成测试用例。导出包会基于真实 Approved 用例、风险分、覆盖项和修订记录动态生成。"
        />
      ) : (
        <>
          <Alert
            type="info"
            showIcon
            title={`将导出 ${approved.length} 条已批准用例、${riskEntries.length} 条风险分、${coverageItems.length} 个覆盖项，并附带 ${revisions.length} 条修订记录。`}
          />

          <Card title="套件优化">
            <Space direction="vertical" size={16} className="full-width">
              <Segmented
                value={mode}
                onChange={(v) => setMode(v as OptimizeMode)}
                options={[
                  { label: '风险优先', value: 'risk_priority' },
                  { label: '集合覆盖', value: 'set_cover' },
                ]}
              />
              <Spin spinning={!opt}>
                <Row gutter={16}>
                  <Col xs={12}>
                    <div className="compare-card">
                      <Text type="secondary">优化前</Text>
                      <Title level={3}>{opt?.before_count ?? '—'}</Title>
                    </div>
                  </Col>
                  <Col xs={12}>
                    <div className="compare-card compare-card-green">
                      <Text type="secondary">优化后</Text>
                      <Title level={3}>{opt?.after_count ?? '—'}</Title>
                    </div>
                  </Col>
                </Row>
                <Progress className="top-gap" percent={opt?.reduction_rate ?? reductionPercent} strokeColor="#0f766e" />
                {opt?.removed_test_ids && opt.removed_test_ids.length > 0 && (
                  <List
                    size="small"
                    header="剔除的用例 ID"
                    dataSource={opt.removed_test_ids}
                    renderItem={(id) => <List.Item>{id}</List.Item>}
                    style={{ marginTop: 12 }}
                  />
                )}
              </Spin>
            </Space>
          </Card>
        </>
      )}

      <ImprovementSummary />
      <RevisionPanel />

      <Modal
        title="导出包预览"
        open={previewOpen}
        onCancel={() => setPreviewOpen(false)}
        footer={[
          <Button key="close" onClick={() => setPreviewOpen(false)}>关闭</Button>,
          <Button key="json" type="primary" loading={exporting} onClick={() => handleExport('json')}>
            确认导出 JSON
          </Button>,
        ]}
        width={720}
      >
        <Descriptions size="small" column={2} bordered>
            <Descriptions.Item label="已通过用例">{approved.length}</Descriptions.Item>
          <Descriptions.Item label="风险分">{riskEntries.length}</Descriptions.Item>
          <Descriptions.Item label="覆盖项">{coverageItems.length}</Descriptions.Item>
          <Descriptions.Item label="修订记录">{revisions.length}</Descriptions.Item>
        </Descriptions>
        <pre className="export-preview-json">
          {JSON.stringify(previewPayload, null, 2).slice(0, 4000)}
          {JSON.stringify(previewPayload).length > 4000 ? '\n…' : ''}
        </pre>
      </Modal>
    </Space>
  )
}
