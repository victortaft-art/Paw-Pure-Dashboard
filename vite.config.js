import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import fs from 'fs'
import path from 'path'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    {
      name: 'serve-parent-data',
      configureServer(server) {
        const parentDir = path.resolve(__dirname, '..')
        server.middlewares.use('/api/data', (req, res) => {
          const folder = new URL(req.url, 'http://localhost').searchParams.get('folder')
          if (!folder) {
            // List available folders
            const folders = ['sc_data', 'ci_data', 'pl_data', 'voc_data', 'copy', 'images', 'kw_data']
            res.setHeader('Content-Type', 'application/json')
            res.end(JSON.stringify({ folders }))
            return
          }

          const folderPath = path.join(parentDir, folder)
          // Prevent path traversal
          if (!folderPath.startsWith(parentDir)) {
            res.statusCode = 403
            res.end('Forbidden')
            return
          }

          try {
            if (folder === 'experiment_log.json' || folder === 'pl_data/pl_config.json') {
              const filePath = path.join(parentDir, folder)
              const content = fs.readFileSync(filePath, 'utf-8')
              res.setHeader('Content-Type', 'application/json')
              res.end(content)
              return
            }

            const files = fs.readdirSync(folderPath)
              .filter(f => f.endsWith('.json'))
              .sort()
            res.setHeader('Content-Type', 'application/json')
            res.end(JSON.stringify({ files }))
          } catch {
            res.setHeader('Content-Type', 'application/json')
            res.end(JSON.stringify({ files: [] }))
          }
        })

        server.middlewares.use('/api/file', (req, res) => {
          const filePath = new URL(req.url, 'http://localhost').searchParams.get('path')
          if (!filePath) {
            res.statusCode = 400
            res.end('Missing path')
            return
          }
          const fullPath = path.join(parentDir, filePath)
          if (!fullPath.startsWith(parentDir)) {
            res.statusCode = 403
            res.end('Forbidden')
            return
          }
          try {
            const content = fs.readFileSync(fullPath, 'utf-8')
            res.setHeader('Content-Type', 'application/json')
            res.end(content)
          } catch {
            res.statusCode = 404
            res.end(JSON.stringify(null))
          }
        })
      }
    }
  ],
})
