import { useState } from 'react'
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom'
import { Layout, Menu, theme, Typography } from 'antd'
import {
  DashboardOutlined,
  BookOutlined,
  ImportOutlined,
  SearchOutlined,
  SafetyCertificateOutlined,
} from '@ant-design/icons'
import Dashboard from './pages/Dashboard'
import WikiBrowser from './pages/WikiBrowser'
import IngestPage from './pages/IngestPage'
import QueryPage from './pages/QueryPage'
import LintPage from './pages/LintPage'

const { Sider, Content, Header } = Layout
const { Title } = Typography

const menuItems = [
  { key: '/', icon: <DashboardOutlined />, label: 'Dashboard' },
  { key: '/wiki', icon: <BookOutlined />, label: 'Wiki Browser' },
  { key: '/ingest', icon: <ImportOutlined />, label: 'Ingest' },
  { key: '/query', icon: <SearchOutlined />, label: 'Query' },
  { key: '/lint', icon: <SafetyCertificateOutlined />, label: 'Health Check' },
]

function App() {
  const [collapsed, setCollapsed] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  const { token } = theme.useToken()

  const selectedKey = menuItems
    .filter(i => location.pathname.startsWith(i.key))
    .sort((a, b) => b.key.length - a.key.length)[0]?.key || '/'

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        style={{ background: token.colorBgContainer }}
      >
        <div style={{
          height: 48,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          borderBottom: `1px solid ${token.colorBorderSecondary}`,
        }}>
          <Title level={5} style={{ margin: 0, whiteSpace: 'nowrap' }}>
            {collapsed ? 'LW' : 'LLM Wiki'}
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
      <Layout>
        <Header style={{
          background: token.colorBgContainer,
          padding: '0 24px',
          borderBottom: `1px solid ${token.colorBorderSecondary}`,
          display: 'flex',
          alignItems: 'center',
        }}>
          <Title level={4} style={{ margin: 0 }}>
            {menuItems.find(i => i.key === selectedKey)?.label || 'LLM Wiki'}
          </Title>
        </Header>
        <Content style={{ margin: 16 }}>
          <div style={{
            padding: 24,
            background: token.colorBgContainer,
            borderRadius: token.borderRadiusLG,
            minHeight: 'calc(100vh - 130px)',
          }}>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/wiki" element={<WikiBrowser />} />
              <Route path="/wiki/:pageName" element={<WikiBrowser />} />
              <Route path="/ingest" element={<IngestPage />} />
              <Route path="/query" element={<QueryPage />} />
              <Route path="/lint" element={<LintPage />} />
            </Routes>
          </div>
        </Content>
      </Layout>
    </Layout>
  )
}

export default App
