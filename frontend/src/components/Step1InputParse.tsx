import { useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Collapse,
  Input,
  Space,
  Spin,
  Table,
  Tag,
  Typography,
  Upload,
} from 'antd'
import type { UploadFile } from 'antd'
import { useAppStore } from '../store/appStore'
import { ingestAndParse, loadAut15Sample } from '../services/api'
import type { DisplayRequirement } from '../types'
import { DataStatusTag } from './shared'
import { RevisionPanel } from './RevisionPanel'
import { ImprovementSummary } from './ImprovementSummary'

const { TextArea } = Input
const { Text } = Typography

export function Step1InputParse() {
  const [fileList, setFileList] = useState<UploadFile[]>([])
  const [pasteText, setPasteText] = useState('')
  const [loading, setLoading] = useState(false)
  const [isLive, setIsLive] = useState<boolean | undefined>()
  const [pendingFrom, setPendingFrom] = useState<string>()

  const requirements = useAppStore((s) => s.requirements)
  const setRequirements = useAppStore((s) => s.setRequirements)
  const updateRequirement = useAppStore((s) => s.updateRequirement)
  const setCurrentStep = useAppStore((s) => s.setCurrentStep)

  const runIngest = async (content: string) => {
    setLoading(true)
    const result = await ingestAndParse(content)
    setRequirements(result.data)
    setIsLive(result.isLive)
    setPendingFrom(result.pendingFrom)
    setLoading(false)
  }

  const handleParse = async () => {
    let content = pasteText.trim()
    if (!content && fileList[0]?.originFileObj) {
      content = await fileList[0].originFileObj.text()
    }
    await runIngest(content)
  }

  const handleLoadSample = async () => {
    setLoading(true)
    const result = await loadAut15Sample()
    setRequirements(result.data)
    setIsLive(result.isLive)
    setPendingFrom(result.pendingFrom)
    setLoading(false)
  }

  const promptPanel = (record: DisplayRequirement) => {
    if (!record.prompt_template_id && !record.source_context_ids?.length) return null
    return (
      <Collapse
        size="small"
        ghost
        items={[
          {
            key: 'prompt',
            label: 'Prompt 透明度',
            children: (
              <Space direction="vertical" size={4} style={{ fontSize: 12 }}>
                <Text type="secondary">template: {record.prompt_template_id || '—'}</Text>
                <Text type="secondary">model: {record.model_name || '—'}</Text>
                <Text type="secondary">schema: {record.output_schema_version || '—'}</Text>
                <Text type="secondary">
                  context: {(record.source_context_ids ?? []).join(', ') || '—'}
                </Text>
                <Text type="secondary">
                  retrieved: {(record.retrieved_context_ids ?? []).join(', ') || '—'}
                </Text>
              </Space>
            ),
          },
        ]}
      />
    )
  }

  const missingCount = requirements.filter((r) => r.missing_fields.length > 0).length

  return (
    <Space direction="vertical" size={24} className="full-width">
      <Card title="需求输入 (FR1.0)">
        <Space direction="vertical" size={16} className="full-width">
          <div>
            <Text type="secondary">直接粘贴需求文本</Text>
            <TextArea
              rows={4}
              placeholder="粘贴 AUT SRS 需求描述，例如借书流程..."
              value={pasteText}
              onChange={(e) => setPasteText(e.target.value)}
              className="top-gap"
            />
          </div>
          <Upload.Dragger
            multiple={false}
            accept=".csv,.txt,.json"
            beforeUpload={() => false}
            fileList={fileList}
            onChange={(info) => setFileList(info.fileList)}
            className="upload-zone"
          >
            <p className="upload-title">或上传 CSV / TXT / JSON</p>
          </Upload.Dragger>
          <Space wrap>
            <Button type="primary" onClick={handleParse} loading={loading}>
              执行解析
            </Button>
            <Button onClick={handleLoadSample} loading={loading}>
              加载 AUT 15 条样本
            </Button>
            <Button
              onClick={() => {
                setPasteText('')
                setFileList([])
                setRequirements([])
              }}
            >
              重置
            </Button>
          </Space>
        </Space>
      </Card>

      {requirements.length > 0 && (
        <Card
          title={
            <span>
              解析结果 · Designer Review (FR1.1)
              <DataStatusTag isLive={isLive} pendingFrom={pendingFrom} />
            </span>
          }
          extra={
            <Button type="primary" onClick={() => setCurrentStep(1)}>
              下一步: 风险评估
            </Button>
          }
        >
          <Spin spinning={loading}>
            {missingCount > 0 && (
              <Alert
                className="bottom-gap"
                type="warning"
                showIcon
                message={`${missingCount} 条需求存在缺失字段，可在下表直接修订。`}
              />
            )}
            <Table
              rowKey="requirement_id"
              size="small"
              pagination={{ pageSize: 8 }}
              dataSource={requirements}
              columns={[
                { title: 'ID', dataIndex: 'requirement_id', width: 120 },
                {
                  title: 'Input Fields',
                  dataIndex: 'input_fields',
                  width: 140,
                  render: (v: string[], record) => (
                    <Input
                      size="small"
                      value={v.join(', ')}
                      onChange={(e) =>
                        updateRequirement(record.requirement_id, {
                          input_fields: e.target.value.split(',').map((s) => s.trim()).filter(Boolean),
                        })
                      }
                    />
                  ),
                },
                {
                  title: 'Data Ranges',
                  dataIndex: 'data_ranges',
                  width: 140,
                  ellipsis: true,
                  render: (v: string[]) => v.join('; ') || '—',
                },
                {
                  title: 'Expected Action',
                  dataIndex: 'expected_action',
                  render: (v, record) => (
                    <Input
                      size="small"
                      value={v}
                      onChange={(e) =>
                        updateRequirement(record.requirement_id, {
                          expected_action: e.target.value,
                        })
                      }
                    />
                  ),
                },
                {
                  title: 'Conditions',
                  dataIndex: 'conditions',
                  render: (v: string[], record) => (
                    <Input
                      size="small"
                      value={v.join(' · ')}
                      onChange={(e) =>
                        updateRequirement(record.requirement_id, {
                          conditions: e.target.value.split('·').map((s) => s.trim()).filter(Boolean),
                        })
                      }
                    />
                  ),
                },
                {
                  title: 'Confidence',
                  dataIndex: 'confidence',
                  width: 90,
                  render: (v: number) => (
                    <Tag color={v >= 0.85 ? 'green' : v >= 0.7 ? 'gold' : 'volcano'}>
                      {v.toFixed(2)}
                    </Tag>
                  ),
                },
                {
                  title: 'Prompt',
                  width: 110,
                  render: (_, record) => promptPanel(record),
                },
                {
                  title: 'Confirmed',
                  width: 100,
                  render: (_, record) => (
                    <Button
                      size="small"
                      type={record.designer_confirmed ? 'primary' : 'default'}
                      onClick={() =>
                        updateRequirement(record.requirement_id, {
                          designer_confirmed: !record.designer_confirmed,
                          missing_fields: record.designer_confirmed ? record.missing_fields : [],
                        })
                      }
                    >
                      {record.designer_confirmed ? '已确认' : '确认'}
                    </Button>
                  ),
                },
              ]}
            />
          </Spin>
        </Card>
      )}

      <ImprovementSummary />
      <RevisionPanel />
    </Space>
  )
}
