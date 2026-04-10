import { useState, useEffect } from 'react'
import {
  Card, Input, Button, Checkbox, Space, Spin, Tag, Typography, Empty, Divider, message,
} from 'antd'
import {
  SendOutlined, SaveOutlined, ReloadOutlined,
} from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { queryWikiStream, qmdStatus as fetchQmdStatus, qmdIndex } from '../services/api'
import type { QMDStatusResponse } from '../services/api'
import MarkdownViewer from '../components/MarkdownViewer'

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

  // QMD 状态
  const [qmdStatus, setQmdStatus] = useState<QMDStatusResponse | null>(null)
  const [indexing, setIndexing] = useState(false)

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

  // 加载 QMD 状态
  useEffect(() => {
    fetchQmdStatus().then(setQmdStatus).catch(() => setQmdStatus(null))
  }, [])

  const handleRebuildIndex = async () => {
    setIndexing(true)
    try {
      const res = await qmdIndex(true)
      if (res.indexed > 0) {
        message.success(res.message)
      // 重新加载状态
      fetchQmdStatus().then(setQmdStatus)
      setQmdStatus(prev => prev ? {
        ...prev,
        indexed_pages: prev.indexed_pages + res.indexed,
      } : null)
      } else {
        message.info(res.message)
      }
    } catch (err: any) {
      message.error(err?.message || t('qmd.rebuildFailed'))
    } finally {
      setIndexing(false)
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

        {/* QMD / 搜索模式状态 */}
        {qmdStatus && (
          <div style={{
            marginTop: 12,
            padding: '8px 12px',
            background: '#f5f7fa',
            borderRadius: '6px',
            fontSize: '12px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}>
            <Space size="small">
              <Text type="secondary">
                {t('qmd.status')}:{' '}
                {qmdStatus.search_mode === 'QMD Semantic' && (
                  <Tag color="green" style={{ margin: 0 }}>{t('qmd.qmdAvailable')}</Tag>
                )}
                {qmdStatus.search_mode === 'SimpleEmbedder (TF-IDF)' && (
                  <Tag color="blue" style={{ margin: 0 }}>TF-IDF Embedding</Tag>
                )}
                {qmdStatus.search_mode === 'BM25 Keyword' && (
                  <Tag color="default" style={{ margin: 0 }}>BM25 Keyword</Tag>
                )}
              </Text>
              <Text type="secondary" style={{ fontSize: '11px' }}>
                {qmdStatus.indexed_pages} / {qmdStatus.total_pages} {t('qmd.indexedPages')}
              </Text>
            </Space>
            <Button
              type="text"
              size="small"
              icon={<ReloadOutlined />}
              loading={indexing}
              onClick={handleRebuildIndex}
            >
              {t('qmd.rebuildIndex')}
            </Button>
          </div>
        )}
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
