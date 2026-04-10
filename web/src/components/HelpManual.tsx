import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { QuestionCircleOutlined } from '@ant-design/icons'
import { Drawer, Typography, Divider, List } from 'antd'

const { Title, Paragraph, Text } = Typography

export default function HelpManual() {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)

  const showDrawer = () => setOpen(true)
  const onClose = () => setOpen(false)

  return (
    <>
      <QuestionCircleOutlined
        style={{ fontSize: 18, cursor: 'pointer', opacity: 0.65 }}
        onClick={showDrawer}
      />
      <Drawer
        title={t('app.help')}
        placement="right"
        onClose={onClose}
        open={open}
        width={480}
      >
        <div style={{ padding: '0 8px' }}>
          <Title level={4}>LLM Wiki</Title>
          <Paragraph>
            一个基于 LLM 的智能 Wiki 系统，支持知识摄入、语义查询和知识图谱可视化。
          </Paragraph>

          <Divider>功能介绍</Divider>

          <List
            size="small"
            dataSource={[
              {
                title: t('nav.wikiBrowser'),
                description: '浏览和搜索所有 Wiki 页面，支持按类型筛选。',
              },
              {
                title: t('nav.ingest'),
                description: '上传源文件（Markdown、文本等），系统自动解析并提取知识。',
              },
              {
                title: t('nav.query'),
                description: '使用自然语言提问，系统从知识库中检索相关信息并生成答案。',
              },
              {
                title: t('nav.graph'),
                description: '可视化知识图谱，展示页面之间的链接关系和节点统计。',
              },
              {
                title: t('nav.healthCheck'),
                description: '检查 Wiki 健康状况，发现孤立页面、断裂链接等问题。',
              },
            ]}
            renderItem={(item) => (
              <List.Item style={{ border: 'none', padding: '8px 0' }}>
                <div>
                  <Text strong>{item.title}</Text>
                  <Paragraph style={{ margin: '4px 0 0', fontSize: 13 }}>
                    {item.description}
                  </Paragraph>
                </div>
              </List.Item>
            )}
          />

          <Divider>使用技巧</Divider>

          <List
            size="small"
            dataSource={[
              { text: '提问时尽量使用具体的问题，避免过于宽泛' },
              { text: '摄入支持 Markdown 格式的结构化文档效果最佳' },
              { text: '知识图谱中颜色表示不同的页面类型' },
              { text: '使用语义搜索（QMD）可以提升查询准确度' },
            ]}
            renderItem={(item) => (
              <List.Item style={{ border: 'none', padding: '4px 0' }}>
                <Text type="secondary">• {item.text}</Text>
              </List.Item>
            )}
          />

          <Divider style={{ margin: '24px 0 16px' }} />

          <Paragraph style={{ marginBottom: 0, fontSize: 12, color: '#999' }}>
            Version 0.2.0
          </Paragraph>
        </div>
      </Drawer>
    </>
  )
}
