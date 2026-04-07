import { useEffect, useState, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Layout, Menu, Input, Spin, Empty, Typography, theme } from 'antd'
import {
  FileTextOutlined,
  ApartmentOutlined,
  BulbOutlined,
  ToolOutlined,
  WarningOutlined,
  SearchOutlined,
} from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import { fetchPages, fetchPage, type PageInfo } from '../services/api'
import MarkdownViewer from '../components/MarkdownViewer'

const { Sider, Content } = Layout
const { Search } = Input

export default function WikiBrowser() {
  const { t } = useTranslation()
  const { pageName } = useParams<{ pageName?: string }>()
  const navigate = useNavigate()
  const { token } = theme.useToken()

  const TYPE_CONFIG: Record<string, { label: string; prefix: string; icon: React.ReactNode }> = {
    sources: { label: t('wikiBrowser.sources'), prefix: 'source-', icon: <FileTextOutlined /> },
    entities: { label: t('wikiBrowser.entities'), prefix: 'entity-', icon: <ApartmentOutlined /> },
    concepts: { label: t('wikiBrowser.concepts'), prefix: 'concept-', icon: <BulbOutlined /> },
    procedures: { label: t('wikiBrowser.procedures'), prefix: 'procedure-', icon: <ToolOutlined /> },
    incidents: { label: t('wikiBrowser.incidents'), prefix: 'incident-', icon: <WarningOutlined /> },
    queries: { label: t('wikiBrowser.queries'), prefix: 'query-', icon: <SearchOutlined /> },
  }

  const [pages, setPages] = useState<PageInfo[]>([])
  const [content, setContent] = useState('')
  const [loading, setLoading] = useState(true)
  const [contentLoading, setContentLoading] = useState(false)
  const [search, setSearch] = useState('')

  useEffect(() => {
    fetchPages()
      .then(setPages)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!pageName) {
      setContent('')
      return
    }
    setContentLoading(true)
    fetchPage(pageName)
      .then(p => setContent(p.content))
      .catch(() => setContent('> Page not found.'))
      .finally(() => setContentLoading(false))
  }, [pageName])

  const grouped = useMemo(() => {
    const lowerSearch = search.toLowerCase()
    const filtered = pages.filter(
      p => p.name.toLowerCase().includes(lowerSearch) || p.title.toLowerCase().includes(lowerSearch),
    )
    const groups: Record<string, PageInfo[]> = {}
    const other: PageInfo[] = []

    for (const page of filtered) {
      let matched = false
      for (const [key, cfg] of Object.entries(TYPE_CONFIG)) {
        if (page.name.startsWith(cfg.prefix)) {
          if (!groups[key]) groups[key] = []
          groups[key].push(page)
          matched = true
          break
        }
      }
      if (!matched) other.push(page)
    }
    return { groups, other }
  }, [pages, search])

  const menuItems = useMemo(() => {
    const items: any[] = []
    for (const [key, cfg] of Object.entries(TYPE_CONFIG)) {
      const group = grouped.groups[key]
      if (!group?.length) continue
      items.push({
        key,
        icon: cfg.icon,
        label: `${cfg.label} (${group.length})`,
        children: group.map(p => ({
          key: p.name,
          label: p.title || p.name,
        })),
      })
    }
    if (grouped.other.length) {
      items.push({
        key: '_other',
        icon: <FileTextOutlined />,
        label: `${t('wikiBrowser.other')} (${grouped.other.length})`,
        children: grouped.other.map(p => ({
          key: p.name,
          label: p.title || p.name,
        })),
      })
    }
    return items
  }, [grouped])

  const handleSelect = ({ key }: { key: string }) => {
    navigate(`/wiki/${key}`)
  }

  const handleLinkClick = (name: string) => {
    navigate(`/wiki/${name}`)
  }

  if (loading) {
    return <Spin size="large" style={{ display: 'block', marginTop: 80, textAlign: 'center' }} />
  }

  return (
    <Layout style={{ background: 'transparent', minHeight: 'calc(100vh - 200px)' }}>
      <Sider
        width={280}
        style={{
          background: token.colorBgContainer,
          borderRight: `1px solid ${token.colorBorderSecondary}`,
          borderRadius: `${token.borderRadiusLG}px 0 0 ${token.borderRadiusLG}px`,
          overflow: 'auto',
          maxHeight: 'calc(100vh - 200px)',
        }}
      >
        <div style={{ padding: '12px 12px 0' }}>
          <Search
            placeholder={t('wikiBrowser.filterPages')}
            allowClear
            size="small"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
        {menuItems.length === 0 ? (
          <Empty
            description={t('wikiBrowser.noWikiPages')}
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            style={{ marginTop: 40 }}
          />
        ) : (
          <Menu
            mode="inline"
            selectedKeys={pageName ? [pageName] : []}
            defaultOpenKeys={Object.keys(TYPE_CONFIG)}
            items={menuItems}
            onClick={handleSelect}
            style={{ borderInlineEnd: 'none', fontSize: 13 }}
          />
        )}
      </Sider>
      <Content style={{ padding: '0 24px', minWidth: 0 }}>
        {pageName ? (
          contentLoading ? (
            <Spin style={{ display: 'block', marginTop: 40, textAlign: 'center' }} />
          ) : (
            <>
              <Typography.Text type="secondary" style={{ fontSize: 12, marginBottom: 8, display: 'block' }}>
                {pageName}.md
              </Typography.Text>
              <MarkdownViewer content={content} onLinkClick={handleLinkClick} />
            </>
          )
        ) : (
          <Empty
            description={t('wikiBrowser.selectPage')}
            style={{ marginTop: 80 }}
          />
        )}
      </Content>
    </Layout>
  )
}
