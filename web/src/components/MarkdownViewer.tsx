import ReactMarkdown from 'react-markdown'

interface Props {
  content: string
  onLinkClick?: (pageName: string) => void
}

export default function MarkdownViewer({ onLinkClick }: Props) {
  return (
    <div className="markdown-viewer">
      <ReactMarkdown
        components={{
          a: ({ href, children }) => {
            // Intercept wiki page links (*.md)
            if (href && href.endsWith('.md') && onLinkClick) {
              const pageName = href.replace('.md', '')
              return (
                <a
                  href="#"
                  className="wiki-link"
                  onClick={(e) => {
                    e.preventDefault()
                    onLinkClick(pageName)
                  }}
                >
                  {children}
                </a>
              )
            }
            return <a href={href} target="_blank" rel="noopener noreferrer" className="external-link">{children}</a>
          },
          h1: ({ children }) => <h1>{children}</h1>,
          h2: ({ children }) => <h2>{children}</h2>,
          h3: ({ children }) => <h3>{children}</h3>,
          h4: ({ children }) => <h4>{children}</h4>,
          h5: ({ children }) => <h5>{children}</h5>,
          h6: ({ children }) => <h6>{children}</h6>,
          p: ({ children }) => <p>{children}</p>,
          ul: ({ children }) => <ul>{children}</ul>,
          ol: ({ children }) => <ol>{children}</ol>,
          li: ({ children }) => <li>{children}</li>,
          blockquote: ({ children }) => (
            <blockquote>{children}</blockquote>
          ),
          hr: () => <hr />,
          table: ({ children }) => <div className="markdown-table-container"><table>{children}</table></div>,
          thead: ({ children }) => <thead>{children}</thead>,
          tbody: ({ children }) => <tbody>{children}</tbody>,
          tr: ({ children }) => <tr>{children}</tr>,
          th: ({ children }) => <th>{children}</th>,
          td: ({ children }) => <td>{children}</td>,
          code: ({ className, children, ...props }) => {
            const isBlock = className?.startsWith('language-')
            if (isBlock) {
              return (
                <pre className="markdown-code-block">
                  <code className={className}>{children}</code>
                </pre>
              )
            }
            return (
              <code className="markdown-code-inline" {...props}>
                {children}
              </code>
            )
          },
        }}
      />
    </div>
  )
}
