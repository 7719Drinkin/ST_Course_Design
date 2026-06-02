import { useEffect, useState } from 'react'
import { Alert, Input, Modal, Select, Space, Typography } from 'antd'
import type { TestCase, TestCaseStatus } from '@/shared/types'

const { Text } = Typography
const { TextArea } = Input

type Props = {
  open: boolean
  testCase: TestCase | null
  onCancel: () => void
  onSave: (next: TestCase, reason: string) => void
}

const STATUS_OPTIONS: { value: TestCaseStatus; label: string }[] = [
  { value: 'Draft', label: '草稿' },
  { value: 'Approved', label: '通过' },
  { value: 'Rejected', label: '驳回' },
]

function linesToText(value: string[] | undefined) {
  return (value ?? []).join('\n')
}

function textToLines(value: string) {
  return value
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean)
}

function formatJson(value: Record<string, unknown> | undefined) {
  return JSON.stringify(value ?? {}, null, 2)
}

export function TestCaseEditorModal({ open, testCase, onCancel, onSave }: Props) {
  const [title, setTitle] = useState('')
  const [preconditions, setPreconditions] = useState('')
  const [inputData, setInputData] = useState('{}')
  const [testSteps, setTestSteps] = useState('')
  const [expectedResult, setExpectedResult] = useState('')
  const [status, setStatus] = useState<TestCaseStatus>('Draft')
  const [reason, setReason] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    if (!testCase) return
    setTitle(testCase.title ?? '')
    setPreconditions(linesToText(testCase.preconditions))
    setInputData(formatJson(testCase.input_data))
    setTestSteps(linesToText(testCase.test_steps))
    setExpectedResult(testCase.expected_result ?? '')
    setStatus(testCase.status ?? 'Draft')
    setReason('设计者修订完整测试用例，并要求重新审查 Oracle。')
    setError('')
  }, [testCase])

  const handleSave = () => {
    if (!testCase) return
    let parsedInput: Record<string, unknown>
    try {
      const parsed = JSON.parse(inputData || '{}') as unknown
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
        throw new Error('input_data must be a JSON object')
      }
      parsedInput = parsed as Record<string, unknown>
    } catch {
      setError('input_data 必须是合法 JSON object。')
      return
    }

    const trimmedReason = reason.trim()
    if (!trimmedReason) {
      setError('请填写修订理由。')
      return
    }

    onSave(
      {
        ...testCase,
        title: title.trim(),
        preconditions: textToLines(preconditions),
        input_data: parsedInput,
        test_steps: textToLines(testSteps),
        expected_result: expectedResult.trim(),
        status,
      },
      trimmedReason,
    )
  }

  return (
    <Modal
      title="编辑完整测试用例"
      open={open}
      width={820}
      okText="保存修订"
      cancelText="取消"
      onOk={handleSave}
      onCancel={onCancel}
      destroyOnHidden
    >
      {testCase && (
        <Space direction="vertical" size={14} className="full-width">
          <Space wrap>
            <Text code>{testCase.test_id}</Text>
            <Text type="secondary">{testCase.requirement_id}</Text>
            <Text type="secondary">{testCase.coverage_item_id}</Text>
            <Text type="secondary">{testCase.technique}</Text>
          </Space>
          {error && <Alert type="error" showIcon message={error} />}
          <label>
            <Text strong>标题</Text>
            <Input value={title} onChange={(e) => setTitle(e.target.value)} />
          </label>
          <label>
            <Text strong>前置条件</Text>
            <TextArea rows={3} value={preconditions} onChange={(e) => setPreconditions(e.target.value)} />
          </label>
          <label>
            <Text strong>输入数据 JSON</Text>
            <TextArea
              rows={8}
              value={inputData}
              onChange={(e) => setInputData(e.target.value)}
              style={{ fontFamily: 'ui-monospace, SFMono-Regular, Consolas, monospace' }}
            />
          </label>
          <label>
            <Text strong>测试步骤</Text>
            <TextArea rows={5} value={testSteps} onChange={(e) => setTestSteps(e.target.value)} />
          </label>
          <label>
            <Text strong>期望结果</Text>
            <TextArea rows={4} value={expectedResult} onChange={(e) => setExpectedResult(e.target.value)} />
          </label>
          <label>
            <Text strong>状态</Text>
            <Select className="full-width" value={status} options={STATUS_OPTIONS} onChange={setStatus} />
          </label>
          <label>
            <Text strong>修订理由</Text>
            <TextArea rows={3} value={reason} onChange={(e) => setReason(e.target.value)} />
          </label>
        </Space>
      )}
    </Modal>
  )
}
