import { useEffect, useState } from 'react'
import { Alert, Button, Card, Col, List, Progress, Row, Segmented, Space, Spin, Typography, message } from 'antd'
import { useAppStore } from '../store/appStore'
import { exportApproved, getOptimizeResult } from '../services/api'
import type { OptimizeMode } from '../types'
import { DataStatusTag } from './shared'
import { RevisionPanel } from './RevisionPanel'

const { Title, Text } = Typography

export function Step4OptimizeExport() {
  const [mode, setMode] = useState<OptimizeMode>('risk_priority')
  const [optLive, setOptLive] = useState<boolean>()
  const [optPending, setOptPending] = useState<string>()
  const [exporting, setExporting] = useState(false)

  const testCases = useAppStore((s) => s.testCases)
  const revisions = useAppStore((s) => s.revisions)
  const optimizeResult = useAppStore((s) => s.optimizeResult)
  const setOptimizeResult = useAppStore((s) => s.setOptimizeResult)

  const approved = testCases.filter((t) => t.status === 'Approved')
  const approvedIdsKey = approved.map((t) => t.test_id).join(',')
  const allIdsKey = testCases.map((t) => t.test_id).join(',')

  useEffect(() => {
    const ids = approvedIdsKey ? approvedIdsKey.split(',') : allIdsKey ? allIdsKey.split(',') : []
    getOptimizeResult(mode, ids).then((r) => {
      setOptimizeResult(r.data)
      setOptLive(r.isLive)
      setOptPending(r.pendingFrom)
    })
  }, [mode, approvedIdsKey, allIdsKey, setOptimizeResult])

  const handleExport = async (format: 'json' | 'csv' | 'xlsx') => {
    if (approved.length === 0) {
      message.warning('请先于 Step 3 批准至少一条测试用例')
      return
    }
    setExporting(true)
    try {
      const blob = await exportApproved(format, approved, revisions)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `autotest_export.${format === 'xlsx' ? 'csv' : format}`
      a.click()
      URL.revokeObjectURL(url)
      message.success(`已导出 ${approved.length} 条 Approved 用例`)
    } catch {
      message.error('导出失败，请确认后端已启动 (port 8000)')
    }
    setExporting(false)
  }

  const opt = optimizeResult

  return (
    <Space direction="vertical" size={24} className="full-width">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
        <span>
          <Title level={4} style={{ margin: 0, display: 'inline' }}>优化与导出 (FR6/7)</Title>
          <DataStatusTag isLive={optLive} pendingFrom={optPending} />
        </span>
        <Space>
          <Button loading={exporting} onClick={() => handleExport('csv')}>导出 Approved CSV</Button>
          <Button loading={exporting} onClick={() => handleExport('json')}>导出 Approved JSON</Button>
        </Space>
      </div>

      <Alert
        type="info"
        showIcon
        message={`将导出 ${approved.length} 条已批准用例（共 ${testCases.length} 条），并附带 ${revisions.length} 条修订记录。`}
      />

      <Card title="套件优化 (FR7.0)">
        <Space direction="vertical" size={16} className="full-width">
          <Segmented
            value={mode}
            onChange={(v) => setMode(v as OptimizeMode)}
            options={[
              { label: '风险优先', value: 'risk_priority' },
              { label: '标准模式', value: 'normal' },
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
            <Progress className="top-gap" percent={opt?.reduction_rate ?? 0} strokeColor="#0f766e" />
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

      <RevisionPanel />
    </Space>
  )
}
