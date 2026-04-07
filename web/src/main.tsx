import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { HashRouter } from 'react-router-dom'
import { ConfigProvider, theme } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import App from './App.tsx'
import './i18n'
import './index.css'

// Ant Design theme config
const themeConfig = {
  algorithm: theme.defaultAlgorithm,
  token: {
    colorPrimary: '#1677ff',
    borderRadius: 10,
    colorBgContainer: '#ffffff',
    colorBgLayout: '#f5f7fa',
    colorBorder: '#e8e8e8',
    colorBorderSecondary: '#f0f0f0',
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
      primaryShadow: '0 2px 8px rgba(22, 119, 255, 0.2)',
    },
    Input: {
      borderRadius: 8,
      controlHeight: 40,
    },
    Statistic: {
      titleFontSize: 14,
      contentFontSize: 24,
    },
  },
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ConfigProvider
      theme={themeConfig}
      locale={zhCN}
    >
      <HashRouter>
        <App />
      </HashRouter>
    </ConfigProvider>
  </StrictMode>,
)
