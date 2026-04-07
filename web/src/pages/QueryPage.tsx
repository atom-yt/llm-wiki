import { useState } from 'react'
import {
  Card, Input, Button, Checkbox, Space, Spin, Tag, Typography, Empty, Divider,
} from 'antd'
import { SendOutlined, SaveOutlined } from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import { queryWikiStream } from '../services/api'
import MarkdownViewer from '../components/MarkdownViewer'
import { useNavigate } from 'react-router-dom'

const { TextArea } = Input
const { Text } = Typography

export default function QueryPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [question, setQuestion] = useState('')
  const [save, setSave] = useState(false)
  const [loading, setLoading] = useState(false)
  const [streamingStarted, setStreamingStarted] = useState(false)
  const [selectedPages, setSelectedPages] = useState<string[]>([])
  const [answer, setAnswer] = useState('')
  const [archivedAs, setArchivedAs] = useState<string | null>(null)
  const [error, setError] = useState('')

  const handleQuery = async () => {
    if (!question.trim()) return
    setLoading(true)
    setStreamingStarted(false)
    setError('')
    setSelectedPages([])
    setAnswer('')
    setArchivedAs(null)

    try {
      await queryWikiStream(question.trim(), save, {
        onSelectedPages: (pages) => {
          setSelectedPages(pages)
          setStreamingStarted(true)
        },
        onChunk: (chunk) => {
          setAnswer(prev => prev + chunk)
        },
        onDone: (archivedAs) => {
          if (archivedAs) {
            setArchivedAs(archivedAs)
          }
          // Only set loading to false when done
          setLoading(false)
        },
        onError: (error) => {
          setError(error)
          setLoading(false)
        },
      })
    } catch (err: any) {
      setError(err?.message || t('query.queryFailed'))
      setLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      handleQuery()
    }
  }

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Card title={t('query.askQuestion')}>
        <TextArea
          rows={3}
          placeholder={t('query.placeholder')}
          value={question}
          onChange={e => setQuestion(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={loading}
        />
        <div style={{ marginTop: 12, display: 'flex', alignItems: 'center', gap: 16 }}>
          <Button
            type="primary"
            icon={<SendOutlined />}
            loading={loading}
            onClick={handleQuery}
            disabled={!question.trim()}
          >
            {t('query.query')}
          </Button>
          <Checkbox checked={save} onChange={e => setSave(e.target.checked)} disabled={loading}>
            <Space>
              <SaveOutlined />
              {t('query.saveAnswer')}
            </Space>
          </Checkbox>
        </div>
        <Text type="secondary" style={{ display: 'block', marginTop: 8, fontSize: 12 }}>
          {t('query.submitHint')}
        </Text>
      </Card>

      {loading && !streamingStarted && (
        <Card>
          <Spin tip={t('query.querying')}>
            <div style={{ padding: 40 }} />
          </Spin>
        </Card>
      )}

      {error && (
        <Card>
          <Text type="danger">{error}</Text>
        </Card>
      )}

      {(streamingStarted || selectedPages.length > 0) && (
        <Card title={t('query.answer')} style={{ minHeight: 200 }}>
          {selectedPages.length > 0 && (
            <>
              <Text type="secondary">{t('query.referencedPages')}: </Text>
              {selectedPages.map(p => (
                <Tag
                  key={p}
                  color="blue"
                  style={{ cursor: 'pointer' }}
                  onClick={() => navigate(`/wiki/${p.replace('.md', '')}`)}
                >
                  {p}
                </Tag>
              ))}
              <Divider />
            </>
          )}

          <MarkdownViewer
            content={answer}
            onLinkClick={name => navigate(`/wiki/${name}`)}
          />

          {archivedAs && (
            <>
              <Divider />
              <Text type="success">
                {t('query.archivedAs')}: <Tag color="green">{archivedAs}</Tag>
              </Text>
            </>
          )}

          {loading && <Spin size="small" style={{ marginTop: 16 }} />}
        </Card>
      )}

      {!loading && !answer && !error && selectedPages.length === 0 && (
        <Empty description={t('query.askQuestionHint')} style={{ marginTop: 40 }} />
      )}
    </Space>
  )
}
