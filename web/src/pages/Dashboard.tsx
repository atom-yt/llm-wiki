import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Row, Col, Card, Statistic, List, Tag, Spin, Empty } from 'antd'
import {
  FileTextOutlined,
  BookOutlined,
  BulbOutlined,
  ToolOutlined,
  WarningOutlined,
} from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import { fetchPages, fetchLog, type PageInfo } from '../services/api'

export default function Dashboard() {
  const { t } = useTranslation()
  const [pages, setPages] = useState<PageInfo[]>([])
  const [logContent, setLogContent] = useState('')
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    Promise.all([fetchPages(), fetchLog()])
      .then(([p, l]) => { setPages(p); setLogContent(l) })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <Spin size="large" style={{ display: 'block', marginTop: 80, textAlign: 'center' }} />

  const counts = {
    sources: pages.filter(p => p.name.startsWith('source-')).length,
    entities: pages.filter(p => p.name.startsWith('entity-')).length,
    concepts: pages.filter(p => p.name.startsWith('concept-')).length,
    procedures: pages.filter(p => p.name.startsWith('procedure-')).length,
    incidents: pages.filter(p => p.name.startsWith('incident-')).length,
    queries: pages.filter(p => p.name.startsWith('query-')).length,
  }

  // Extract recent log entries (last 8 ## headings)
  const logEntries = logContent
    .split(/^## /m)
    .filter(Boolean)
    .slice(-8)
    .reverse()
    .map(block => {
      const firstLine = block.split('\n')[0]
      return firstLine.trim()
    })

  const tagColor = (type: string) => {
    if (type.includes('ingest')) return 'blue'
    if (type.includes('query')) return 'green'
    if (type.includes('lint')) return 'orange'
    return 'default'
  }

  return (
    <>
      <Row gutter={[16, 16]}>
        <Col xs={12} sm={8} md={4}>
          <Card hoverable onClick={() => navigate('/wiki')}>
            <Statistic title={t('dashboard.totalPages')} value={pages.length} prefix={<BookOutlined />} />
          </Card>
        </Col>
        <Col xs={12} sm={8} md={4}>
          <Card hoverable onClick={() => navigate('/wiki')}>
            <Statistic title={t('dashboard.sources')} value={counts.sources} prefix={<FileTextOutlined />} />
          </Card>
        </Col>
        <Col xs={12} sm={8} md={4}>
          <Card hoverable onClick={() => navigate('/wiki')}>
            <Statistic title={t('dashboard.entities')} value={counts.entities} prefix={<ToolOutlined />} />
          </Card>
        </Col>
        <Col xs={12} sm={8} md={4}>
          <Card hoverable onClick={() => navigate('/wiki')}>
            <Statistic title={t('dashboard.concepts')} value={counts.concepts} prefix={<BulbOutlined />} />
          </Card>
        </Col>
        <Col xs={12} sm={8} md={4}>
          <Card hoverable onClick={() => navigate('/wiki')}>
            <Statistic title={t('dashboard.procedures')} value={counts.procedures} prefix={<WarningOutlined />} />
          </Card>
        </Col>
        <Col xs={12} sm={8} md={4}>
          <Card hoverable onClick={() => navigate('/wiki')}>
            <Statistic title={t('dashboard.queries')} value={counts.queries} prefix={<FileTextOutlined />} />
          </Card>
        </Col>
      </Row>

      <Card title={t('dashboard.recentActivity')} style={{ marginTop: 16 }}>
        {logEntries.length === 0 ? (
          <Empty description={t('dashboard.noActivity')} />
        ) : (
          <List
            size="small"
            dataSource={logEntries}
            renderItem={(item) => {
              const actionMatch = item.match(/\]\s*(\w+)/)
              const action = actionMatch ? actionMatch[1] : ''
              return (
                <List.Item>
                  <Tag color={tagColor(action)}>{action || t('dashboard.log')}</Tag>
                  {item}
                </List.Item>
              )
            }}
          />
        )}
      </Card>
    </>
  )
}
