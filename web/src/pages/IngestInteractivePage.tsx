import { useState, useEffect } from 'react'
import {
  Card, Steps, Button, List, Tag, Space, Typography, Spin,
  Alert, Modal, Input, Select, Divider, message, Result
} from 'antd'
import {
  InboxOutlined, PlayCircleOutlined, FileTextOutlined,
  CheckCircleOutlined, CloseCircleOutlined, ReloadOutlined
} from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import {
  fetchRawSources, ingestStart, ingestPropose, ingestApply
} from '../services/api'
import type { KeyPointsResponse, PageProposal, ApplyRequest } from '../services/api'

const { Text, Title, Paragraph } = Typography

type IngestStage = 'idle' | 'extracting' | 'reviewing' | 'proposing' | 'approving' | 'applying' | 'completed'

interface IngestSession {
  stage: IngestStage
  sessionId: string | null
  sourceFile: string | null
  keyPoints: string[]
  approvedPoints: Set<string>
  userFeedback: string
  proposals: PageProposal[]
  approvedPages: Set<string>
  rejectedPages: Set<string>
  pageStrategies: Record<string, string>
  result: ApplyRequest | null
  error: string | null
}

export default function IngestInteractivePage() {
  const { t } = useTranslation()
  const [sources, setSources] = useState<string[]>([])
  const [loading, setLoading] = useState(false)

  const [session, setSession] = useState<IngestSession>({
    stage: 'idle',
    sessionId: null,
    sourceFile: null,
    keyPoints: [],
    approvedPoints: new Set(),
    userFeedback: '',
    proposals: [],
    approvedPages: new Set(),
    rejectedPages: new Set(),
    pageStrategies: {},
    result: null,
    error: null,
  })

  const [showDiffModal, setShowDiffModal] = useState(false)
  const [currentDiff, setCurrentDiff] = useState('')

  useEffect(() => {
    fetchRawSources().then(setSources)
  }, [])

  const resetSession = () => {
    setSession({
      stage: 'idle',
      sessionId: null,
      sourceFile: null,
      keyPoints: [],
      approvedPoints: new Set(),
      userFeedback: '',
      proposals: [],
      approvedPages: new Set(),
      rejectedPages: new Set(),
      pageStrategies: {},
      result: null,
      error: null,
    })
  }

  const handleStart = async (sourceFile: string) => {
    resetSession()
    setSession(prev => ({ ...prev, sourceFile, stage: 'extracting' as const }))

    try {
      const res = await ingestStart(sourceFile)
      setSession(prev => ({
        ...prev,
        stage: 'reviewing' as const,
        sessionId: res.session_id,
        keyPoints: res.key_points,
        approvedPoints: new Set(res.key_points),
      }))
    } catch (err: any) {
      message.error(err?.response?.data?.detail || t('ingest.failedToStart'))
      setSession(prev => ({ ...prev, stage: 'idle' as const, error: err.message }))
    }
  }

  const handleReviewNext = () => {
    setSession(prev => ({ ...prev, stage: 'proposing' as const }))
  }

  const handleReviewSubmit = async () => {
    setSession(prev => ({ ...prev, stage: 'proposing' as const }))

    try {
      const res = await ingestPropose(
        session.sessionId!,
        Array.from(session.approvedPoints),
        session.userFeedback
      )

      setSession(prev => ({
        ...prev,
        proposals: res.proposals,
        approvedPages: new Set(
          res.proposals
            .filter((p: PageProposal) => p.action !== 'delete')
            .map((p: PageProposal) => p.filename)
        ),
        pageStrategies: Object.fromEntries(
          res.proposals.map((p: PageProposal) => [p.filename, p.strategy])
        ),
      }))
    } catch (err: any) {
      message.error(err?.response?.data?.detail || t('ingest.failedToPropose'))
    }
  }

  const togglePoint = (point: string) => {
    setSession(prev => {
      const newApproved = new Set(prev.approvedPoints)
      if (newApproved.has(point)) {
        newApproved.delete(point)
      } else {
        newApproved.add(point)
      }
      return { ...prev, approvedPoints: newApproved }
    })
  }

  const togglePage = (filename: string) => {
    setSession(prev => {
      const newApproved = new Set(prev.approvedPages)
      const newRejected = new Set(prev.rejectedPages)

      if (newApproved.has(filename)) {
        newApproved.delete(filename)
        newRejected.delete(filename)
      } else {
        newApproved.add(filename)
        newRejected.delete(filename)
      }

      return { ...prev, approvedPages: newApproved, rejectedPages: newRejected }
    })
  }

  const setStrategy = (filename: string, strategy: string) => {
    setSession(prev => ({
      ...prev,
      pageStrategies: { ...prev.pageStrategies, [filename]: strategy }
    }))
  }

  const handleApply = async () => {
    setSession(prev => ({ ...prev, stage: 'applying' as const }))

    try {
      const req: ApplyRequest = {
        session_id: session.sessionId!,
        approved_pages: Array.from(session.approvedPages),
        rejected_pages: Array.from(session.rejectedPages),
        strategies: session.pageStrategies,
      }

      const res = await ingestApply(req)

      message.success(t('ingest.applySuccess'))

      setSession({
        stage: 'completed' as const,
        result: res,
        sessionId: null,
        sourceFile: null,
        keyPoints: [],
        approvedPoints: new Set(),
        proposals: [],
        approvedPages: new Set(),
        rejectedPages: new Set(),
        pageStrategies: {},
        error: null,
      })
    } catch (err: any) {
      message.error(err?.response?.data?.detail || t('ingest.failedToApply'))
      setSession(prev => ({ ...prev, stage: 'proposing' as const, error: err.message }))
    }
  }

  const handleShowDiff = (proposal: PageProposal) => {
    setCurrentDiff(proposal.diff || t('ingest.noDiff'))
    setShowDiffModal(true)
  }

  const getStageIcon = (stage: IngestStage) => {
    switch (stage) {
      case 'extracting':
      case 'proposing':
        return <Spin size="small" />
      case 'applying':
        return <Spin size="small" />
      case 'completed':
        return <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 24 }} />
      case 'idle':
        return <InboxOutlined style={{ fontSize: 24 }} />
      default:
        return <FileTextOutlined style={{ fontSize: 24 }} />
    }
  }

  return (
    <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      <Title level={2}>{t('ingest.interactiveTitle')}</Title>
      <Paragraph type="secondary">
        {t('ingest.interactiveDescription')}
      </Paragraph>

      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        {/* Stage indicator */}
        <Card>
          <Steps
            current={[
              'idle', 'extracting', 'reviewing', 'proposing', 'approving', 'applying', 'completed'
            ].indexOf(session.stage)}
            items={[
              { title: t('ingest.selectFile'), icon: <InboxOutlined /> },
              { title: t('ingest.reviewPoints'), icon: <FileTextOutlined /> },
              { title: t('ingest.proposePages'), icon: <PlayCircleOutlined /> },
              { title: t('ingest.approvePages'), icon: <CheckCircleOutlined /> },
              { title: t('ingest.applyChanges'), icon: <CheckCircleOutlined /> },
            ]}
          />
        </Card>

        {/* Stage 1: Select File */}
        {session.stage === 'idle' && (
          <Card title={t('ingest.selectSourceFile')} extra={getStageIcon('idle')}>
            <List
              dataSource={sources}
              renderItem={item => (
                <List.Item
                  actions={[
                    <Button
                      type="primary"
                      icon={<PlayCircleOutlined />}
                      onClick={() => handleStart(item)}
                    >
                      {t('ingest.start')}
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
          </Card>
        )}

        {/* Stage 2: Review Key Points */}
        {session.stage === 'reviewing' && (
          <Card title={t('ingest.reviewKeyPoints')} extra={getStageIcon('reviewing')}>
            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
              {session.keyPoints.map(point => (
                <div
                  key={point}
                  onClick={() => togglePoint(point)}
                  style={{
                    padding: '12px',
                    border: '1px solid #d9d9d9',
                    borderRadius: '6px',
                    marginBottom: '8px',
                    cursor: 'pointer',
                    background: session.approvedPoints.has(point) ? '#e6f7ff' : 'transparent',
                  }}
                >
                  <Space>
                    {session.approvedPoints.has(point) ? (
                      <CheckCircleOutlined style={{ color: '#52c41a' }} />
                    ) : (
                      <div style={{ width: '16px' }} />
                    )}
                    <Text>{point}</Text>
                  </Space>
                </div>
              ))}
            </Space>

            <Space style={{ marginTop: '16px' }}>
              <Input.TextArea
                placeholder={t('ingest.feedbackPlaceholder')}
                value={session.userFeedback}
                onChange={e => setSession(prev => ({ ...prev, userFeedback: e.target.value }))}
                rows={3}
                allowClear
              />
            </Space>

            <Space style={{ marginTop: '16px' }}>
              <Button onClick={resetSession}>{t('ingest.cancel')}</Button>
              <Button type="primary" onClick={handleReviewNext}>
                {t('ingest.next')} ({session.approvedPoints.size})
              </Button>
            </Space>
          </Card>
        )}

        {/* Stage 3: Review Proposals */}
        {session.stage === 'proposing' && (
          <Card title={t('ingest.reviewPageProposals')} extra={getStageIcon('proposing')}>
            {session.proposals.length === 0 ? (
              <Spin />
            ) : (
              <List
                dataSource={session.proposals}
                renderItem={item => (
                  <List.Item
                    actions={[
                      <Button
                        size="small"
                        icon={<CloseCircleOutlined />}
                        danger={session.approvedPages.has(item.filename)}
                        onClick={() => togglePage(item.filename)}
                      >
                        {session.approvedPages.has(item.filename) ? t('ingest.reject') : t('ingest.approve')}
                      </Button>,
                      item.diff && (
                        <Button
                          size="small"
                          onClick={() => handleShowDiff(item)}
                        >
                          {t('ingest.viewDiff')}
                        </Button>
                      ),
                    ]}
                    style={{
                      background: session.approvedPages.has(item.filename) ? '#fff1f0' : 'transparent',
                      padding: '12px',
                      borderRadius: '6px',
                      marginBottom: '8px',
                    }}
                  >
                    <List.Item.Meta
                      title={
                        <Space>
                          <Tag color={item.action === 'create' ? 'green' : 'blue'}>
                            {item.action === 'create' ? t('ingest.create') : t('ingest.update')}
                          </Tag>
                          <strong>{item.filename}</strong>
                        </Space>
                      }
                      description={
                        <Paragraph
                          ellipsis={{ rows: 2 }}
                          style={{ marginBottom: 0 }}
                        >
                          {item.content_preview}
                        </Paragraph>
                      }
                    />
                  </List.Item>
                )}
              />
            )}

            <Space style={{ marginTop: '16px' }}>
              <Button onClick={resetSession}>{t('ingest.cancel')}</Button>
              <Button type="primary" onClick={handleApply}>
                {t('ingest.apply')} ({session.approvedPages.size})
              </Button>
            </Space>
          </Card>
        )}

        {/* Stage 4: Applying */}
        {session.stage === 'applying' && (
          <Card title={t('ingest.applyingChanges')} extra={getStageIcon('applying')}>
            <div style={{ textAlign: 'center', padding: '40px 0' }}>
              <Spin size="large" tip={t('ingest.applyingTip')} />
            </div>
          </Card>
        )}

        {/* Stage 5: Completed */}
        {session.stage === 'completed' && session.result && (
          <Card title={t('ingest.completed')} extra={getStageIcon('completed')}>
            <Result
              status="success"
              title={t('ingest.changesApplied')}
              subTitle={t('ingest.reviewResult')}
              extra={[
                <Button type="primary" onClick={resetSession} icon={<ReloadOutlined />}>
                  {t('ingest.newIngest')}
                </Button>,
              ]}
            >
              <Space direction="vertical" style={{ width: '100%' }}>
                {session.result.created.length > 0 && (
                  <div style={{ width: '100%' }}>
                    <Text strong>{t('ingest.createdPages')}:</Text>
                    <div style={{ marginTop: '8px' }}>
                      {session.result.created.map(p => (
                        <Tag key={p} color="green" style={{ marginBottom: '4px' }}>
                          {p}
                        </Tag>
                      ))}
                    </div>
                  </div>
                )}

                {session.result.updated.length > 0 && (
                  <div style={{ width: '100%' }}>
                    <Text strong>{t('ingest.updatedPages')}:</Text>
                    <div style={{ marginTop: '8px' }}>
                      {session.result.updated.map(p => (
                        <Tag key={p} color="blue" style={{ marginBottom: '4px' }}>
                          {p}
                        </Tag>
                      ))}
                    </div>
                  </div>
                )}
              </Space>
            </Result>
          </Card>
        )}

        {/* Error display */}
        {session.error && (
          <Alert
            message={t('ingest.error')}
            description={session.error}
            type="error"
            showIcon
            closable
            onClose={() => setSession(prev => ({ ...prev, error: null }))}
          />
        )}
      </Space>

      {/* Diff Modal */}
      <Modal
        title={t('ingest.pageDiff')}
        open={showDiffModal}
        onCancel={() => setShowDiffModal(false)}
        footer={[
          <Button onClick={() => setShowDiffModal(false)}>{t('common.close')}</Button>,
        ]}
        width={800}
      >
        <pre style={{
          padding: '12px',
          background: '#f5f5f5',
          borderRadius: '4px',
          maxHeight: '500px',
          overflow: 'auto',
        }}>{currentDiff}</pre>
      </Modal>
    </div>
  )
}
