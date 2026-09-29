const { app, BrowserWindow } = require('electron')
const { spawn } = require('child_process')
const path = require('path')
const http = require('http')

let mainWindow
let backendProcess

const BACKEND_URL = 'http://127.0.0.1:8731'
const isDev = !app.isPackaged

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    backgroundColor: '#161510',
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
    },
  })

  if (isDev) {
    // en desarrollo, el frontend lo sirve `npm run dev` (Vite) en el 5173
    mainWindow.loadURL('http://localhost:5173')
    mainWindow.webContents.openDevTools()
  } else {
    // en producción, carga el build estático generado por `npm run build`
    mainWindow.loadFile(path.join(__dirname, '../frontend/dist/index.html'))
  }
}

function startBackend() {
  // En desarrollo llamamos directamente al intérprete python del sistema.
  // Para distribuir la app empaquetada, lo ideal es congelar server.py con
  // PyInstaller y lanzar el ejecutable resultante en vez de "python3".
  const backendDir = path.join(__dirname, '../backend')
  backendProcess = spawn('python3', ['server.py'], { cwd: backendDir })

  backendProcess.stdout.on('data', d => console.log(`[backend] ${d}`))
  backendProcess.stderr.on('data', d => console.error(`[backend] ${d}`))
}

function waitForBackend(retries = 30) {
  return new Promise((resolve, reject) => {
    const attempt = (n) => {
      http.get(`${BACKEND_URL}/health`, () => resolve())
        .on('error', () => {
          if (n <= 0) return reject(new Error('El backend no arrancó a tiempo'))
          setTimeout(() => attempt(n - 1), 300)
        })
    }
    attempt(retries)
  })
}

app.whenReady().then(async () => {
  startBackend()
  try {
    await waitForBackend()
  } catch (err) {
    console.error(err)
  }
  createWindow()
})

app.on('window-all-closed', () => {
  if (backendProcess) backendProcess.kill()
  if (process.platform !== 'darwin') app.quit()
})

app.on('before-quit', () => {
  if (backendProcess) backendProcess.kill()
})
