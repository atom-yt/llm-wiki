import { useState } from 'react'
import {
  Card, Input, Button, Checkbox, Space, Spin, Tag, Typography, Empty, Divider,
} from 'antd'
import { SendOutlined, SaveOutlined } from '@ant-design/icons'
import { queryWiki, type QueryResponse } from '../services/api'
import MarkdownViewer from '../components/MarkdownViewer'
import { useNavigate } from 'react-router-dom'

const { TextArea } = Input
const { Text } = Typography

export default function QueryPage() {
  const navigate = useNavigate()
  const [question, setQuestion] = useState('')
  const [save, setSave] = useState(false)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<QueryResponse | null>(null)
  const [error, setError] = useState('')

  const handleQuery = async () => {
    if (!question.trim()) return
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const res = await queryWiki(question.trim(), save)
      setResult(res)
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Query failed. Make sure the backend is running and LLM is configured.')
    } finally {
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
      <Card title="Ask a Question">
        <TextArea
          rows={3}
          placeholder="e.g. How do I upgrade the K8s cluster from 1.27 to 1.28?"
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
            Query
          </Button>
          <Checkbox checked={save} onChange={e => setSave(e.target.checked)} disabled={loading}>
            <Space>
              <SaveOutlined />
              Save answer as wiki page
            </Space>
          </Checkbox>
        </div>
        <Text type="secondary" style={{ display: 'block', marginTop: 8, fontSize: 12 }}>
          Press Ctrl+Enter / Cmd+Enter to submit
        </Text>
      </Card>

      {loading && (
        <Card>
          <Spin tip="Querying LLM... This may take a moment.">
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
        <Card title="Answer">
          {result.selected_pages.length > 0 && (
            <>
              <Text type="secondary">Referenced pages: </Text>
              {result.selected_pages.map(p => (
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
            content={result.answer}
            onLinkClick={name => navigate(`/wiki/${name}`)}
          />

          {result.archived_as && (
            <>
              <Divider />
              <Text type="success">
                Archived as: <Tag color="green">{result.archived_as}</Tag>
              </Text>
            </>
          )}
        </Card>
      )}

      {!loading && !result && !error && (
        <Empty description="Ask a question about your knowledge base" style={{ marginTop: 40 }} />
      )}
    </Space>
  )
}
