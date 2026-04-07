import ReactMarkdown from 'react-markdown'
import { Typography } from 'antd'

interface Props {
  content: string
  onLinkClick?: (pageName: string) => void
}

export default function MarkdownViewer({ content, onLinkClick }: Props) {
  return (
    <Typography>
      <ReactMarkdown
        components={{
          a: ({ href, children }) => {
            // Intercept wiki page links (*.md)
            if (href && href.endsWith('.md') && onLinkClick) {
              const pageName = href.replace('.md', '')
              return (
                <a
                  href="#"
                  onClick={(e) => {
                    e.preventDefault()
                    onLinkClick(pageName)
                  }}
                >
                  {children}
                </a>
              )
            }
            return <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>
          },
          h1: ({ children }) => <Typography.Title level={3}>{children}</Typography.Title>,
          h2: ({ children }) => <Typography.Title level={4}>{children}</Typography.Title>,
          h3: ({ children }) => <Typography.Title level={5}>{children}</Typography.Title>,
          p: ({ children }) => <Typography.Paragraph>{children}</Typography.Paragraph>,
          code: ({ className, children, ...props }) => {
            const isBlock = className?.startsWith('language-')
            if (isBlock) {
              return (
                <pre style={{
                  background: '#f5f5f5',
                  padding: 16,
                  borderRadius: 6,
                  overflow: 'auto',
                  fontSize: 13,
                }}>
                  <code>{children}</code>
                </pre>
              )
            }
            return (
              <code style={{
                background: '#f0f0f0',
                padding: '2px 6px',
                borderRadius: 4,
                fontSize: 13,
              }} {...props}>
                {children}
              </code>
            )
          },
        }}
      />
    </Typography>
  )
}
