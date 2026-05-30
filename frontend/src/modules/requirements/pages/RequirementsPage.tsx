import { useMemo, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Descriptions,
  Input,
  Space,
  Spin,
  Table,
  Tag,
  Typography,
  Upload,
} from 'antd'
import type { UploadFile } from 'antd'
import { useAppStore } from '@/app/store/appStore'
import {
  ingestFile,
  ingestText,
  isAllowedFileType,
  parseRequirements,
} from '@/modules/requirements/api/requirementsApi'
import { RevisionPanel } from '@/shared/components/RevisionPanel'
import { WorkflowEmptyState } from '@/shared/components/WorkflowFeedback'
import { startPollRisk, stopAllPolling } from '@/shared/api/pipelinePoller'
import type { DisplayRequirement } from '@/shared/types'

const { TextArea } = Input
const { Paragraph, Text } = Typography

export function RequirementsPage() {
  const [fileList, setFileList] = useState<UploadFile[]>([])
  const [pasteText, setPasteText] = useState('')
  const [loading, setLoading] = useState(false)
  const [inputError, setInputError] = useState<string>()
  const [successMessage, setSuccessMessage] = useState<string>()

  const requirements = useAppStore((s) => s.requirements)
  const setRequirements = useAppStore((s) => s.setRequirements)
  const setSourceName = useAppStore((s) => s.setSourceName)
  const updateRequirement = useAppStore((s) => s.updateRequirement)
  const setRiskEntries = useAppStore((s) => s.setRiskEntries)
  const setCoverageItems = useAppStore((s) => s.setCoverageItems)
  const setStrategies = useAppStore((s) => s.setStrategies)
  const setTestCases = useAppStore((s) => s.setTestCases)
  const setOracleResults = useAppStore((s) => s.setOracleResults)
  const setFsm = useAppStore((s) => s.setFsm)
  const setOptimizeResult = useAppStore((s) => s.setOptimizeResult)
  const setPromptEvidence = useAppStore((s) => s.setPromptEvidence)
  const setAnalysisResults = useAppStore((s) => s.setAnalysisResults)
  const setHighlightedRequirementId = useAppStore((s) => s.setHighlightedRequirementId)
  const setStagePolling = useAppStore((s) => s.setStagePolling)
  const resetStagePolling = useAppStore((s) => s.resetStagePolling)
  const clearPendingRevisions = useAppStore((s) => s.clearPendingRevisions)

  const selectedFile = fileList[0]?.originFileObj as File | undefined
  const hasInput = Boolean(selectedFile || pasteText.trim())

  const fieldCompleteness = useMemo(() => {
    if (requirements.length === 0) return 0
    const complete = requirements.filter((item) => item.missing_fields.length === 0).length
    return Math.round((complete / requirements.length) * 100)
  }, [requirements])

  const handleIngest = async () => {
    setLoading(true)
    setInputError(undefined)
    setSuccessMessage(undefined)
    // Mark stage 0 as polling (spinning in sidebar)
    useAppStore.getState().setStagePolling(0, true)

    try {
      let parseInput = ''
      let sourceLabel = ''
      if (selectedFile) {
        if (!isAllowedFileType(selectedFile.name)) {
          setInputError('不支持的文件类型，仅允许 .txt .md .pdf .docx')
          return
        }
        const fileExt = selectedFile.name.slice(selectedFile.name.lastIndexOf('.')).toLowerCase()
        await ingestFile(selectedFile)
        setSourceName(selectedFile.name)
        sourceLabel = selectedFile.name
        parseInput = fileExt === '.txt' || fileExt === '.md' ? await selectedFile.text() : ''
      } else {
        const content = pasteText.trim()
        if (!content) {
          setInputError('请先粘贴需求文本，或上传文件后再提交。')
          return
        }
        await ingestText(content)
        sourceLabel = '文本输入'
        parseInput = content
        setSourceName(sourceLabel)
      }
      const parsed = await parseRequirements(parseInput, sourceLabel)
      setRequirements(parsed)
      setStagePolling(0, false) // stage 0 → ready
      setSuccessMessage(
        parsed.length > 0
          ? `已提交并解析 ${parsed.length} 条需求。`
          : '输入已提交，后端当前未返回结构化需求。',
      )
      // Kick off cascading background polling
      if (parsed.length > 0) {
        startPollRisk()
      }
    } catch {
      setInputError('提交失败，请检查服务是否可用，或稍后重试。')
    } finally {
      setLoading(false)
    }
  }

  const handleReset = () => {
    stopAllPolling()
    setPasteText('')
    setFileList([])
    setSourceName(null)
    setRequirements([])
    setRiskEntries([])
    setCoverageItems([])
    setStrategies([])
    setTestCases([])
    setOracleResults([])
    setFsm(null)
    setOptimizeResult(null)
    setPromptEvidence([])
    setAnalysisResults([])
    setHighlightedRequirementId(null)
    setInputError(undefined)
    setSuccessMessage(undefined)
    resetStagePolling()
    clearPendingRevisions()
  }

  return (
    <Space direction="vertical" size={24} className="full-width">
      <div className="workbench-grid workbench-grid-2">
        <Card title="输入控制台" className="workflow-card">
          <Space direction="vertical" size={18} className="full-width">
            <div className="info-panel">
              <Text className="section-title">输入内容</Text>
              <Descriptions size="small" column={1}>
                <Descriptions.Item label="文本内容">可直接粘贴需求描述</Descriptions.Item>
                <Descriptions.Item label="上传文件">支持 TXT、MD、PDF、DOCX</Descriptions.Item>
              </Descriptions>
            </div>

            <div>
              <Text strong>直接输入</Text>
              <TextArea
                rows={8}
                placeholder="粘贴待测系统的需求文本。系统会自动整理为可审查的结构化内容。"
                value={pasteText}
                onChange={(event) => {
                  setPasteText(event.target.value)
                  setInputError(undefined)
                }}
                className="top-gap"
              />
            </div>

            <Upload.Dragger
              multiple={false}
              accept=".txt,.md,.pdf,.docx"
              beforeUpload={(file) => {
                if (!isAllowedFileType(file.name)) {
                  setInputError('不支持的文件类型，仅允许 .txt .md .pdf .docx')
                  return Upload.LIST_IGNORE
                }
                setInputError(undefined)
                return false
              }}
              fileList={fileList}
              onChange={(info) => {
                setFileList(info.fileList.slice(-1))
                setSuccessMessage(undefined)
              }}
              className="upload-zone"
            >
              <p className="upload-title">拖入或选择需求文档</p>
              <p className="upload-hint">TXT / MD / PDF / DOCX</p>
            </Upload.Dragger>

            {inputError && <Alert type="warning" showIcon title={inputError} />}
            {successMessage && <Alert type="success" showIcon title={successMessage} />}

            <Space wrap>
              <Button type="primary" onClick={handleIngest} loading={loading} disabled={!hasInput}>
                提交并解析
              </Button>
              <Button onClick={handleReset}>清空工作台</Button>
            </Space>
          </Space>
        </Card>

        <Card title="解析目标" className="workflow-card">
          <Space direction="vertical" size={18} className="full-width">
            <div className="metric-band">
              <div>
                <span>{requirements.length}</span>
                <Text>需求条目</Text>
              </div>
              <div>
                <span>{fieldCompleteness}%</span>
                <Text>字段完整度</Text>
              </div>
              <div>
                <span>{requirements.filter((item) => item.designer_confirmed).length}</span>
                <Text>已确认</Text>
              </div>
            </div>
            <div className="info-panel info-panel-muted">
              <Text className="section-title">审查重点</Text>
              <Paragraph>
                系统会整理输入字段、数据范围、业务条件、期望行为和置信度。设计者可在下表直接修订并确认。
              </Paragraph>
            </div>
            <div className="stage-ladder">
              <span>需求归一化</span>
              <span>结构化解析</span>
              <span>设计者确认</span>
              <span>风险评分准备</span>
            </div>
          </Space>
        </Card>
      </div>

      {requirements.length === 0 ? (
        <WorkflowEmptyState
          title="尚未载入需求"
          description="提交真实需求后，表格会展示可审查的结构化内容、置信度和待补充信息。"
          action={
            <Button type="primary" disabled={!hasInput} onClick={handleIngest} loading={loading}>
              提交并解析
            </Button>
          }
        />
      ) : (
        <Card title="结构化解析结果 · 人工审查">
          <Spin spinning={loading}>
            <Table
              rowKey="requirement_id"
              size="small"
              pagination={{ pageSize: 8 }}
              scroll={{ x: 1200 }}
              dataSource={requirements}
              columns={[
                { title: '需求编号', dataIndex: 'requirement_id', width: 130 },
                {
                  title: '原始需求',
                  dataIndex: 'raw_requirement',
                  width: 260,
                  ellipsis: true,
                },
                {
                  title: '输入字段',
                  dataIndex: 'input_fields',
                  width: 180,
                  render: (value: string[], record: DisplayRequirement) => (
                    <Input
                      size="small"
                      value={value.join(', ')}
                      onChange={(event) =>
                        updateRequirement(record.requirement_id, {
                          input_fields: event.target.value
                            .split(',')
                            .map((item) => item.trim())
                            .filter(Boolean),
                        })
                      }
                    />
                  ),
                },
                {
                  title: '数据范围',
                  dataIndex: 'data_ranges',
                  width: 180,
                  render: (value: string[]) => value.join('; ') || '—',
                },
                {
                  title: '业务条件',
                  dataIndex: 'conditions',
                  width: 220,
                  render: (value: string[], record: DisplayRequirement) => (
                    <Input
                      size="small"
                      value={value.join(' · ')}
                      onChange={(event) =>
                        updateRequirement(record.requirement_id, {
                          conditions: event.target.value
                            .split('·')
                            .map((item) => item.trim())
                            .filter(Boolean),
                        })
                      }
                    />
                  ),
                },
                {
                  title: '期望行为',
                  dataIndex: 'expected_action',
                  width: 220,
                  render: (value: string, record: DisplayRequirement) => (
                    <Input
                      size="small"
                      value={value}
                      onChange={(event) =>
                        updateRequirement(record.requirement_id, {
                          expected_action: event.target.value,
                        })
                      }
                    />
                  ),
                },
                {
                  title: '置信度',
                  dataIndex: 'confidence',
                  width: 110,
                  render: (value: number) => (
                    <Tag color={value >= 0.85 ? 'green' : value >= 0.7 ? 'gold' : 'volcano'}>
                      {value.toFixed(2)}
                    </Tag>
                  ),
                },
                {
                  title: '待补充',
                  dataIndex: 'missing_fields',
                  width: 160,
                  render: (value: string[]) =>
                    value.length > 0 ? value.map((item) => <Tag key={item}>{item}</Tag>) : <Tag color="green">None</Tag>,
                },
                {
                  title: '审查',
                  width: 120,
                  render: (_, record: DisplayRequirement) => (
                    <Button
                      size="small"
                      type={record.designer_confirmed ? 'primary' : 'default'}
                      onClick={() =>
                        updateRequirement(record.requirement_id, {
                          designer_confirmed: !record.designer_confirmed,
                          missing_fields: record.designer_confirmed ? record.missing_fields : [],
                        }, undefined, true)
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

      <RevisionPanel />
    </Space>
  )
}
