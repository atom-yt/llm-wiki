import { useEffect, useState } from 'react'
import {
  Card, Upload, Button, List, Tag, Typography, Space, Spin, message, Result, Divider,
} from 'antd'
import { InboxOutlined, PlayCircleOutlined, FileTextOutlined } from '@ant-design/icons'
import {
  fetchRawSources, uploadRawSource, ingestSource, type IngestResponse,
} from '../services/api'

const { Dragger } = Upload
const { Text, Title } = Typography

export default function IngestPage() {
  const [sources, setSources] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [ingesting, setIngesting] = useState<string | null>(null)
  const [result, setResult] = useState<IngestResponse | null>(null)

  const loadSources = () => {
    setLoading(true)
    fetchRawSources()
      .then(setSources)
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(() => { loadSources() }, [])

  const handleUpload = async (file: File) => {
    try {
      await uploadRawSource(file)
      message.success(`Uploaded: ${file.name}`)
      loadSources()
    } catch {
      message.error('Upload failed')
    }
    return false // prevent antd default upload
  }

  const handleIngest = async (sourceFile: string) => {
    setIngesting(sourceFile)
    setResult(null)
    try {
      const res = await ingestSource(sourceFile)
      setResult(res)
      message.success('Ingest completed')
    } catch (err: any) {
      message.error(err?.response?.data?.detail || 'Ingest failed')
    } finally {
      setIngesting(null)
    }
  }

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      {/* Upload area */}
      <Card title="Upload Source File">
        <Dragger
          accept=".md,.txt,.yaml,.yml,.json"
          showUploadList={false}
          beforeUpload={handleUpload}
          multiple={false}
        >
            <p className="ant-upload-drag-icon"><InboxOutlined /></p>
          <p className="ant-upload-text">Click or drag a source file to upload</p>
          <p className="ant-upload-hint">
            Supports Markdown, text, YAML, JSON files. Files are saved to raw/ directory.
          </p>
        </Dragger>
      </Card>

      {/* Source files list */}
      <Card title="Source Files">
        {loading ? (
          <Spin />
        ) : sources.length === 0 ? (
          <Text type="secondary">No source files yet. Upload one above.</Text>
        ) : (
          <List
            dataSource={sources}
            renderItem={item => (
              <List.Item
                actions={[
                  <Button
                    type="primary"
                    size="small"
                    icon={<PlayCircleOutlined />}
                    loading={ingesting === item}
                    onClick={() => handleIngest(item)}
                    disabled={ingesting !== null}
                  >
                    Ingest
                  </Button>,
                ]}
              >
                <List.Item.Meta
                  avatar={<FileTextOutlined style={{ fontSize: 20 }} />}
                  title={item}
                />
              </List.Item>
            )}
          />
        )}
      </Card>

      {/* Ingest result */}
      {result && (
        <Card title="Ingest Result">
          <Result status="success" title="Source ingested successfully" />

          {result.key_points.length > 0 && (
            <>
              <Title level={5}>Key Points Extracted</Title>
              <List
                size="small"
                dataSource={result.key_points}
                renderItem={item => <List.Item>{item}</List.Item>}
              />
            </>
          )}

          <Divider />

          {result.created.length > 0 && (
            <div style={{ marginBottom: 12 }}>
              <Text strong>Created: </Text>
              {result.created.map(p => (
                <Tag color="green" key={p}>{p}</Tag>
              ))}
            </div>
          )}

          {result.updated.length > 0 && (
            <div>
              <Text strong>Updated: </Text>
              {result.updated.map(p => (
                <Tag color="blue" key={p}>{p}</Tag>
              ))}
            </div>
          )}
        </Card>
      )}
    </Space>
  )
}
