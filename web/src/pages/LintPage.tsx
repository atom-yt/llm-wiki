import { useState } from 'react'
import {
  Card, Button, Checkbox, Space, Spin, List, Tag, Typography, Empty, Result,
} from 'antd'
import {
  SafetyCertificateOutlined, BugOutlined, RobotOutlined, ToolOutlined,
} from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import { lintWiki, type LintResponse, type LintIssue } from '../services/api'

const { Text } = Typography

function IssueList({ issues, title, icon }: { issues: LintIssue[]; title: string; icon: React.ReactNode }) {
  const { t } = useTranslation()

  if (issues.length === 0) {
    return (
      <Card size="small" title={<Space>{icon}{title}</Space>} style={{ marginBottom: 16 }}>
        <Text type="success">{t('lint.noIssuesFound')}</Text>
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
  const { t } = useTranslation()
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
      setError(err?.response?.data?.detail || t('lint.lintFailed'))
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
      <Card title={t('lint.wikiHealthCheck')}>
        <Space>
          <Button
            type="primary"
            icon={<SafetyCertificateOutlined />}
            loading={loading}
            onClick={handleLint}
          >
            {t('lint.runHealthCheck')}
          </Button>
          <Checkbox checked={fix} onChange={e => setFix(e.target.checked)} disabled={loading}>
            <Space>
              <ToolOutlined />
              {t('lint.autoFixIssues')}
            </Space>
          </Checkbox>
        </Space>
        <div style={{ marginTop: 8 }}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {t('lint.checkHint')}
            {fix ? ` ${t('lint.autoFixHint')}` : ''}
          </Text>
        </div>
      </Card>

      {loading && (
        <Card>
          <Spin tip={t('lint.runningCheck')}>
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
              title={t('lint.wikiHealthy')}
              subTitle={t('lint.wikiHealthySub')}
            />
          ) : (
            <Result
              status="warning"
              title={t('lint.foundIssues', { count: totalIssues })}
              subTitle={fixCount > 0 ? t('lint.appliedFixes', { count: fixCount }) : undefined}
            />
          )}

          <IssueList
            issues={result.structural_issues}
            title={t('lint.structuralIssues')}
            icon={<BugOutlined />}
          />

          <IssueList
            issues={result.llm_issues}
            title={t('lint.llmAnalysis')}
            icon={<RobotOutlined />}
          />

          {fixCount > 0 && (
            <Card title={t('lint.appliedFixesTitle')} size="small">
              {result.fixes.created && result.fixes.created.length > 0 && (
                <div style={{ marginBottom: 8 }}>
                  <Text strong>{t('ingest.created')}: </Text>
                  {result.fixes.created.map(p => (
                    <Tag color="green" key={p}>{p}</Tag>
                  ))}
                </div>
              )}
              {result.fixes.updated && result.fixes.updated.length > 0 && (
                <div>
                  <Text strong>{t('ingest.updated')}: </Text>
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
        <Empty description={t('lint.clickToCheck')} style={{ marginTop: 40 }} />
      )}
    </Space>
  )
}
