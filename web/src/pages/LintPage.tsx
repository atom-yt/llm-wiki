import { useState } from 'react'
import {
  Card, Button, Checkbox, Space, Spin, List, Tag, Typography, Empty, Result, Divider,
} from 'antd'
import {
  SafetyCertificateOutlined, BugOutlined, RobotOutlined, ToolOutlined,
} from '@ant-design/icons'
import { lintWiki, type LintResponse, type LintIssue } from '../services/api'

const { Text, Title } = Typography

function IssueList({ issues, title, icon }: { issues: LintIssue[]; title: string; icon: React.ReactNode }) {
  if (issues.length === 0) {
    return (
      <Card size="small" title={<Space>{icon}{title}</Space>} style={{ marginBottom: 16 }}>
        <Text type="success">No issues found</Text>
      </Card>
    )
  }

  return (
    <Card size="small" title={<Space>{icon}{title} ({issues.length})</Space>} style={{ marginBottom: 16 }}>
      <List
        size="small"
        dataSource={issues}
        renderItem={issue => (
          <List.Item>
            <Space direction="vertical" size={2} style={{ width: '100%' }}>
              <Space>
                <Tag color={issue.level === 'warn' ? 'orange' : 'blue'}>
                  {issue.level.toUpperCase()}
                </Tag>
                <Text>{issue.message}</Text>
              </Space>
              {issue.pages.length > 0 && (
                <div style={{ paddingLeft: 8 }}>
                  {issue.pages.map(p => (
                    <Tag key={p} style={{ fontSize: 11 }}>{p}</Tag>
                  ))}
                </div>
              )}
            </Space>
          </List.Item>
        )}
      />
    </Card>
  )
}

export default function LintPage() {
  const [fix, setFix] = useState(false)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<LintResponse | null>(null)
  const [error, setError] = useState('')

  const handleLint = async () => {
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const res = await lintWiki(fix)
      setResult(res)
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Lint failed. Make sure the backend is running and LLM is configured.')
    } finally {
      setLoading(false)
    }
  }

  const totalIssues = result
    ? result.structural_issues.length + result.llm_issues.length
    : 0

  const fixCount = result?.fixes
    ? (result.fixes.created?.length || 0) + (result.fixes.updated?.length || 0)
    : 0

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Card title="Wiki Health Check">
        <Space>
          <Button
            type="primary"
            icon={<SafetyCertificateOutlined />}
            loading={loading}
            onClick={handleLint}
          >
            Run Health Check
          </Button>
          <Checkbox checked={fix} onChange={e => setFix(e.target.checked)} disabled={loading}>
            <Space>
              <ToolOutlined />
              Auto-fix issues
            </Space>
          </Checkbox>
        </Space>
        <div style={{ marginTop: 8 }}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            Checks for orphan pages, broken links, thin pages, contradictions, and missing references.
            {fix ? ' Auto-fix will ask the LLM to generate corrections.' : ''}
          </Text>
        </div>
      </Card>

      {loading && (
        <Card>
          <Spin tip="Running health check... LLM analysis may take a moment.">
            <div style={{ padding: 40 }} />
          </Spin>
        </Card>
      )}

      {error && (
        <Card>
          <Text type="danger">{error}</Text>
        </Card>
      )}

      {result && (
        <>
          {totalIssues === 0 ? (
            <Result
              status="success"
              title="Wiki is healthy"
              subTitle="No structural or content issues found."
            />
          ) : (
            <Result
              status="warning"
              title={`Found ${totalIssues} issue${totalIssues > 1 ? 's' : ''}`}
              subTitle={fixCount > 0 ? `Applied ${fixCount} fixes` : undefined}
            />
          )}

          <IssueList
            issues={result.structural_issues}
            title="Structural Issues"
            icon={<BugOutlined />}
          />

          <IssueList
            issues={result.llm_issues}
            title="LLM Analysis"
            icon={<RobotOutlined />}
          />

          {fixCount > 0 && (
            <Card title="Applied Fixes" size="small">
              {result.fixes.created && result.fixes.created.length > 0 && (
                <div style={{ marginBottom: 8 }}>
                  <Text strong>Created: </Text>
                  {result.fixes.created.map(p => (
                    <Tag color="green" key={p}>{p}</Tag>
                  ))}
                </div>
              )}
              {result.fixes.updated && result.fixes.updated.length > 0 && (
                <div>
                  <Text strong>Updated: </Text>
                  {result.fixes.updated.map(p => (
                    <Tag color="blue" key={p}>{p}</Tag>
                  ))}
                </div>
              )}
            </Card>
          )}
        </>
      )}

      {!loading && !result && !error && (
        <Empty description="Click the button above to check wiki health" style={{ marginTop: 40 }} />
      )}
    </Space>
  )
}
