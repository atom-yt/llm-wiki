import { useState, useEffect, useRef } from 'react'
import {
  Card, Upload, Button, List, Tag, Typography, Space, Spin, message, Result, Divider, Progress, Alert
} from 'antd'
import { InboxOutlined, PlayCircleOutlined, ThunderboltOutlined, CheckCircleOutlined, FileTextOutlined, LoadingOutlined, ClockCircleOutlined } from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import {
  fetchRawSources, uploadRawSource, ingestSourceStream, type IngestResponse, type IngestProgressUpdate
} from '../services/api'

const { Dragger } = Upload
const { Text, Title, Paragraph } = Typography

type IngestStage = 'idle' | 'ingesting' | 'completed' | 'error'

interface StepItem {
  id: string
  label: string
  status: 'pending' | 'active' | 'completed'
  progress?: number
}

interface IngestState {
  stage: IngestStage
  ingestingFile: string | null
  result: IngestResponse | null
  error: string | null
  progress: number
  currentStep: string
  keyPoints: string[]
  created: string[]
  updated: string[]
}

const INGEST_STEPS = [
  { id: 'analyzing-file', label: '正在分析文件', progressRange: [0, 10] },
  { id: 'extracting-points', label: '正在提取关键点', progressRange: [10, 20] },
  { id: 'analyzing', label: 'LLM 正在分析', progressRange: [20, 50] },
  { id: 'writing-pages', label: '正在写入页面', progressRange: [50, 80] },
  { id: 'updating-index', label: '正在更新索引', progressRange: [80, 90] },
  { id: 'logging', label: '正在记录日志', progressRange: [90, 95] },
  { id: 'completed', label: '完成', progressRange: [95, 100] },
]

export default function IngestPage() {
  const { t } = useTranslation()
  const [sources, setSources] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const abortControllerRef = useRef<AbortController | null>(null)

  const [state, setState] = useState<IngestState>({
    stage: 'idle',
    ingestingFile: null,
    result: null,
    error: null,
    progress: 0,
    currentStep: '',
    keyPoints: [],
    created: [],
    updated: [],
  })

  const getSteps = (): StepItem[] => {
    if (state.stage !== 'ingesting') {
      return []
    }
    return INGEST_STEPS.map(step => {
      const [min, max] = step.progressRange || [0, 100]
      const isCompleted = state.progress >= max
      const isActive = state.progress >= min && state.progress < max
      return {
        ...step,
        status: isCompleted ? 'completed' : isActive ? 'active' : 'pending',
        progress: isActive ? ((state.progress - min) / (max - min) * 100) : undefined,
      }
    })
  }

  const loadSources = () => {
    setLoading(true)
    fetchRawSources().then(setSources).catch(() => {}).finally(() => setLoading(false))
  }

  useEffect(() => { loadSources() }, [])

  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort()
      }
    }
  }, [])

  const handleUpload = async (file: File) => {
    try {
      await uploadRawSource(file)
      message.success(`${t('ingest.uploaded')}: ${file.name}`)
      loadSources()
    } catch {
      message.error(t('ingest.uploadFailed'))
    }
    return false
  }

  const handleIngest = async (sourceFile: string) => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
    abortControllerRef.current = new AbortController()
    setState({
      stage: 'ingesting',
      ingestingFile: sourceFile,
      result: null,
      error: null,
      progress: 0,
      currentStep: '',
      keyPoints: [],
      created: [],
      updated: [],
    })

    try {
      await ingestSourceStream(sourceFile, {
        onProgress: (update: IngestProgressUpdate) => {
          setState(prev => ({
            ...prev,
            progress: update.progress,
            currentStep: update.message,
            keyPoints: update.key_points || prev.keyPoints,
            created: update.created || prev.created,
            updated: update.updated || prev.updated,
          }))
        },
        onDone: (result: IngestResponse) => {
          setState({
            stage: 'completed',
            ingestingFile: null,
            result: result,
            error: null,
            progress: 100,
            currentStep: t('ingest.completed'),
            keyPoints: result.key_points,
            created: result.created,
            updated: result.updated,
          })
          message.success(t('ingest.ingestSuccess'))
        },
        onError: (error: string) => {
          setState({
            stage: 'error',
            ingestingFile: null,
            result: null,
            error: error,
            progress: 0,
            currentStep: '',
            keyPoints: [],
            created: [],
            updated: [],
          })
          message.error(error)
        },
      })
    } catch (err: any) {
      if (err.name === 'AbortError') {
        return
      }
      const errorMsg = err?.message || t('ingest.ingestFailed')
      setState({
        stage: 'error',
        ingestingFile: null,
        result: null,
        error: errorMsg,
        progress: 0,
        currentStep: '',
        keyPoints: [],
        created: [],
        updated: [],
      })
      message.error(errorMsg)
    } finally {
      abortControllerRef.current = null
    }
  }

  const handleCancel = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
    setState({
      stage: 'idle',
      ingestingFile: null,
      result: null,
      error: null,
      progress: 0,
      currentStep: '',
      keyPoints: [],
      created: [],
      updated: [],
    })
  }

  const handleNewIngest = () => {
    setState({
      stage: 'idle',
      ingestingFile: null,
      result: null,
      error: null,
      progress: 0,
      currentStep: '',
      keyPoints: [],
      created: [],
      updated: [],
    })
  }

  const steps = getSteps()

  return (
    <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      <Title level={2}>{t('ingest.title')}</Title>
      <Paragraph type="secondary">
        {t('ingest.description')}
      </Paragraph>

      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        {/* Upload area */}
        <Card>
          <Dragger
            accept=".md,.txt,.yaml,.yml,.json"
            showUploadList={false}
            beforeUpload={handleUpload}
            multiple={false}
            disabled={state.stage === 'ingesting'}
          >
            <p className="ant-upload-drag-icon"><InboxOutlined style={{ fontSize: 48, color: '#1677ff' }} /></p>
            <p className="ant-upload-text">{t('ingest.uploadText')}</p>
            <p className="ant-upload-hint">{t('ingest.uploadHint')}</p>
          </Dragger>
        </Card>

        {/* Progress indicator with steps */}
        {state.stage === 'ingesting' && (
          <Card>
            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
              <Space>
                <Spin size="large" />
                <Text strong style={{ fontSize: 16 }}>
                  {state.currentStep}
                </Text>
                {state.ingestingFile && (
                  <Text type="secondary"> - {state.ingestingFile}</Text>
                )}
              </Space>

              {/* Overall progress */}
              <Progress
                percent={state.progress}
                status="active"
                strokeColor={{
                  '0%': '#108ee9',
                  '50%': '#1677ff',
                  '100%': '#52c41a',
                }}
              />

              {/* Steps list */}
              <div style={{ marginTop: 24 }}>
                {steps.map((step, index) => (
                  <div
                    key={step.id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      marginTop: index > 0 ? '16px' : 0,
                      opacity: step.status === 'pending' ? 0.4 : 1,
                      transition: 'all 0.3s',
                    }}
                  >
                    <div style={{ width: 20, height: 20, borderRadius: '50%', background: step.status === 'completed' ? '#52c41a' : step.status === 'active' ? '#1677ff' : '#d9d9d9', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      {step.status === 'completed' ? (
                        <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 12 }} />
                      ) : step.status === 'active' ? (
                        step.id === 'analyzing' ? (
                          <ClockCircleOutlined style={{ color: '#1677ff', fontSize: 12 }} />
                        ) : (
                          <LoadingOutlined style={{ color: '#1677ff', fontSize: 12 }} spin />
                        )
                      ) : null}
                    </div>
                    <Text style={{ fontSize: 14, marginLeft: 12 }}>
                      {step.label}
                    </Text>
                    {step.status === 'active' && step.progress !== undefined && (
                      <Progress
                        percent={step.progress}
                        size="small"
                        showInfo={false}
                        strokeColor="#1677ff"
                        style={{ marginLeft: 16, flex: 1, maxWidth: 120 }}
                      />
                    )}
                  </div>
                ))}
              </div>

              {/* Key points preview */}
              {state.keyPoints.length > 0 && (
                <div style={{ marginTop: 16 }}>
                  <Text type="secondary" strong>
                    {t('ingest.keyPointsExtracted')} ({state.keyPoints.length})
                  </Text>
                  <div style={{ maxHeight: 120, overflowY: 'auto', padding: '8px 12px', background: '#fafafa', borderRadius: 8 }}>
                    {state.keyPoints.slice(0, 5).map((point, i) => (
                      <div key={i} style={{ marginBottom: 4 }}>
                        <Text style={{ fontSize: 12 }}>
                          <CheckCircleOutlined style={{ color: '#52c41a', marginRight: 6, fontSize: 10 }} />
                          {point}
                        </Text>
                      </div>
                    ))}
                    {state.keyPoints.length > 5 && (
                      <Text type="secondary" style={{ fontSize: 12 }}>+{state.keyPoints.length - 5} more</Text>
                    )}
                  </div>
                </div>
              )}

              {/* Pages preview */}
              {(state.created.length > 0 || state.updated.length > 0) && (
                <div style={{ marginTop: 12 }}>
                  <Space size="small">
                    {state.created.length > 0 && (
                      <div>
                        <Tag color="green" style={{ marginRight: 8 }}>
                          +{state.created.length}
                        </Tag>
                        <Text type="secondary">{t('ingest.created')}</Text>
                      </div>
                    )}
                    {state.updated.length > 0 && (
                      <div>
                        <Tag color="blue" style={{ marginRight: 8 }}>
                          ~{state.updated.length}
                        </Tag>
                        <Text type="secondary">{t('ingest.updated')}</Text>
                      </div>
                    )}
                  </Space>
                </div>
              )}

              <Button danger onClick={handleCancel} style={{ marginTop: 16 }}>
                {t('common.cancel')}
              </Button>
            </Space>
          </Card>
        )}

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
                      icon={<PlayCircleOutlined />}
                      loading={state.stage === 'ingesting' && state.ingestingFile === item}
                      onClick={() => handleIngest(item)}
                      disabled={state.stage === 'ingesting'}
                    >
                      {t('ingest.ingest')}
                    </Button>,
                  ]}
                >
                  <List.Item.Meta
                    avatar={<FileTextOutlined style={{ fontSize: 24, color: '#1677ff' }} />}
                    title={item}
                  />
                </List.Item>
              )}
            />
          )}
        </Card>

        {/* Result */}
        {state.stage === 'completed' && state.result && (
          <Card>
            <Result
              status="success"
              title={t('ingest.ingestSuccess')}
              subTitle={`${t('ingest.pagesAffected')}: ${state.result.created.length + state.result.updated.length}`}
              extra={[
                <Button key="new" type="primary" icon={<ThunderboltOutlined />} onClick={handleNewIngest}>
                  {t('ingest.newIngest')}
                </Button>,
              ]}
            >
              <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                {state.keyPoints.length > 0 && (
                  <>
                    <Title level={5}>{t('ingest.keyPointsExtracted')}</Title>
                    <List
                      size="small"
                      dataSource={state.keyPoints}
                      renderItem={item => (
                        <List.Item>
                          <CheckCircleOutlined style={{ color: '#52c41a', marginRight: 8 }} />
                          {item}
                        </List.Item>
                      )}
                    />
                  </>
                )}

                <Divider />

                {state.created.length > 0 && (
                  <div>
                    <Text strong>{t('ingest.created')}: </Text>
                    {state.created.map(p => (
                      <Tag key={p} color="green" style={{ marginBottom: 4 }}>{p}</Tag>
                    ))}
                  </div>
                )}

                {state.updated.length > 0 && (
                  <div>
                    <Text strong>{t('ingest.updated')}: </Text>
                    {state.updated.map(p => (
                      <Tag key={p} color="blue" style={{ marginBottom: 4 }}>{p}</Tag>
                    ))}
                  </div>
                )}

                <Alert
                  message={
                    <Text>
                      {t('ingest.pagesAffected')}: {state.result.created.length + state.result.updated.length}
                    </Text>
                  }
                  type="success"
                  showIcon
                />
              </Space>
            </Result>
          </Card>
        )}

        {/* Error */}
        {state.stage === 'error' && (
          <Card>
            <Result
              status="error"
              title={t('ingest.error')}
              subTitle={state.error}
              extra={[
                <Button onClick={handleNewIngest}>{t('ingest.retry')}</Button>
              ]}
            />
          </Card>
        )}
      </Space>
    </div>
  )
}
