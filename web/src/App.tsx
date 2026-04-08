import { useState } from 'react'
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom'
import { Layout, Menu, theme, Typography, ConfigProvider, type ConfigProviderProps } from 'antd'
import {
  DashboardOutlined,
  BookOutlined,
  ImportOutlined,
  SearchOutlined,
  SafetyCertificateOutlined,
  PlayCircleOutlined,
} from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import zhCN from 'antd/locale/zh_CN'
import enUS from 'antd/locale/en_US'
import Dashboard from './pages/Dashboard'
import WikiBrowser from './pages/WikiBrowser'
import IngestPage from './pages/IngestPage'
import IngestInteractivePage from './pages/IngestInteractivePage'
import QueryPage from './pages/QueryPage'
import LintPage from './pages/LintPage'
import LanguageSelector from './components/LanguageSelector'

const { Sider, Content, Header } = Layout
const { Title } = Typography

function AppContent() {
  const { t } = useTranslation()
  const [collapsed, setCollapsed] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  const { token } = theme.useToken()

  const menuItems = [
    { key: '/', icon: <DashboardOutlined />, label: t('nav.dashboard') },
    { key: '/wiki', icon: <BookOutlined />, label: t('nav.wikiBrowser') },
    { key: '/ingest', icon: <ImportOutlined />, label: t('nav.ingest') },
    { key: '/ingest-interactive', icon: <PlayCircleOutlined />, label: t('nav.ingestInteractive') },
    { key: '/query', icon: <SearchOutlined />, label: t('nav.query') },
    { key: '/lint', icon: <SafetyCertificateOutlined />, label: t('nav.healthCheck') },
  ]

  const selectedKey = menuItems
    .filter(i => location.pathname.startsWith(i.key))
    .sort((a, b) => b.key.length - a.key.length)[0]?.key || '/'

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        width={240}
        style={{ background: token.colorBgContainer, borderRight: `1px solid ${token.colorBorderSecondary}` }}
      >
        <div style={{
          height: 56,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          borderBottom: `1px solid ${token.colorBorderSecondary}`,
          background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        }}>
          <Title
            level={5}
            style={{
              margin: 0,
              whiteSpace: 'nowrap',
              color: '#fff',
              fontWeight: 600,
            }}
          >
            {collapsed ? t('app.shortTitle') : t('app.title')}
          </Title>
        </div>
        <Menu
          mode="inline"
          selectedKeys={[selectedKey]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          style={{ borderInlineEnd: 'none' }}
        />
      </Sider>
      <Layout style={{ background: token.colorBgLayout }}>
        <Header style={{
          background: token.colorBgContainer,
          padding: '0 24px',
          borderBottom: `1px solid ${token.colorBorderSecondary}`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}>
          <Title level={4} style={{ margin: 0, fontWeight: 600 }}>
            {menuItems.find(i => i.key === selectedKey)?.label || t('app.title')}
          </Title>
          <LanguageSelector />
        </Header>
        <Content style={{ margin: 20 }}>
          <div style={{
            padding: 24,
            background: token.colorBgContainer,
            borderRadius: token.borderRadiusLG,
            minHeight: 'calc(100vh - 136px)',
            boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
          }}>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/wiki" element={<WikiBrowser />} />
              <Route path="/wiki/:pageName" element={<WikiBrowser />} />
              <Route path="/ingest" element={<IngestPage />} />
              <Route path="/ingest-interactive" element={<IngestInteractivePage />} />
              <Route path="/query" element={<QueryPage />} />
              <Route path="/lint" element={<LintPage />} />
            </Routes>
          </div>
        </Content>
      </Layout>
    </Layout>
  )
}

export default function App() {
  const { i18n } = useTranslation()

  const config: ConfigProviderProps['theme'] = {
    algorithm: theme.defaultAlgorithm,
    token: {
      colorPrimary: i18n.language === 'zh' ? '#1677ff' : '#1890ff',
      borderRadius: 10,
      colorBgContainer: '#ffffff',
      colorBgLayout: '#f5f7fa',
    },
    components: {
      Layout: {
        headerBg: '#ffffff',
        siderBg: '#ffffff',
      },
      Card: {
        colorBgContainer: '#ffffff',
        borderRadiusLG: 12,
      },
      Menu: {
        itemBg: 'transparent',
        itemSelectedBg: '#e6f4ff',
        itemSelectedColor: '#1677ff',
      },
      Button: {
        borderRadius: 8,
        controlHeight: 40,
      },
      Input: {
        borderRadius: 8,
        controlHeight: 40,
      },
    },
  }

  return (
    <ConfigProvider theme={config} locale={i18n.language === 'zh' ? zhCN : enUS}>
      <AppContent />
    </ConfigProvider>
  )
}
