import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { ConfigProvider, theme } from 'antd'
import 'antd/dist/reset.css'
import './index.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ConfigProvider
      theme={{
        algorithm: theme.defaultAlgorithm,
        token: {
          colorPrimary: '#1f6feb',
          colorInfo: '#1f6feb',
          borderRadius: 8,
          fontFamily:
            'Inter, "Microsoft YaHei", "PingFang SC", "Hiragino Sans GB", "Segoe UI", sans-serif',
        },
      }}
    >
      <App />
    </ConfigProvider>
  </StrictMode>,
)
