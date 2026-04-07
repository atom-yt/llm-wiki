import { useEffect, useState } from 'react'
import {
  Card, Upload, Button, List, Tag, Typography, Space, Spin, message, Result, Divider,
} from 'antd'
import { InboxOutlined, PlayCircleOutlined, FileTextOutlined } from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import {
  fetchRawSources, uploadRawSource, ingestSource, type IngestResponse,
} from '../services/api'

const { Dragger } = Upload
const { Text, Title } = Typography

export default function IngestPage() {
  const { t } = useTranslation()
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
      message.success(`${t('ingest.uploaded')}: ${file.name}`)
      loadSources()
    } catch {
      message.error(t('ingest.uploadFailed'))
    }
    return false // prevent antd default upload
  }

  const handleIngest = async (sourceFile: string) => {
    setIngesting(sourceFile)
    setResult(null)
    try {
      const res = await ingestSource(sourceFile)
      setResult(res)
      message.success(t('ingest.ingestSuccess'))
    } catch (err: any) {
      message.error(err?.response?.data?.detail || t('ingest.ingestFailed'))
    } finally {
      setIngesting(null)
    }
  }

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      {/* Upload area */}
      <Card title={t('ingest.uploadSourceFile')}>
        <Dragger
          accept=".md,.txt,.yaml,.yml,.json"
          showUploadList={false}
          beforeUpload={handleUpload}
          multiple={false}
        >
            <p className="ant-upload-drag-icon"><InboxOutlined /></p>
          <p className="ant-upload-text">{t('ingest.uploadText')}</p>
          <p className="ant-upload-hint">
            {t('ingest.uploadHint')}
          </p>
        </Dragger>
      </Card>

      {/* Source files list */}
      <Card title={t('ingest.sourceFiles')}>
        {loading ? (
          <Spin />
        ) : sources.length === 0 ? (
          <Text type="secondary">{t('ingest.noSourceFiles')}</Text>
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
                    {t('ingest.ingest')}
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
        <Card title={t('ingest.ingestResult')}>
          <Result status="success" title={t('ingest.ingestSuccess')} />

          {result.key_points.length > 0 && (
            <>
              <Title level={5}>{t('ingest.keyPointsExtracted')}</Title>
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
              <Text strong>{t('ingest.created')}: </Text>
              {result.created.map(p => (
                <Tag color="green" key={p}>{p}</Tag>
              ))}
            </div>
          )}

          {result.updated.length > 0 && (
            <div>
              <Text strong>{t('ingest.updated')}: </Text>
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
