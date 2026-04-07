import { useTranslation } from 'react-i18next'
import { Select, Space } from 'antd'
import { GlobalOutlined } from '@ant-design/icons'

const { Option } = Select

export default function LanguageSelector() {
  const { i18n } = useTranslation()

  const handleChange = (value: string) => {
    i18n.changeLanguage(value)
  }

  return (
    <Space>
      <GlobalOutlined />
      <Select
        value={i18n.language}
        onChange={handleChange}
        style={{ width: 100 }}
        size="small"
      >
        <Option value="zh">中文</Option>
        <Option value="en">English</Option>
      </Select>
    </Space>
  )
}
