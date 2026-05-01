const { app, BrowserWindow } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const http = require('http');

let mainWindow;
let flaskProcess;

const PORT = process.env.PORT || 5000;
const PROJECT_DIR = app.isPackaged
  ? path.join(process.resourcesPath, 'app')
  : path.resolve(__dirname, '..');

function findPython() {
  const candidates = [
    path.join(PROJECT_DIR, 'venv', 'bin', 'python3'),
    path.join(PROJECT_DIR, 'venv', 'bin', 'python'),
    path.join(PROJECT_DIR, '.venv', 'bin', 'python3'),
    path.join(PROJECT_DIR, '.venv', 'bin', 'python'),
    'python3',
    'python',
  ];
  // On Windows, try venv Scripts
  if (process.platform === 'win32') {
    candidates.unshift(
      path.join(PROJECT_DIR, 'venv', 'Scripts', 'python.exe'),
      path.join(PROJECT_DIR, '.venv', 'Scripts', 'python.exe')
    );
  }
  return candidates;
}

function startFlask() {
  return new Promise((resolve, reject) => {
    const pythons = findPython();
    const py = pythons.shift();
    flaskProcess = spawn(py, [path.join(PROJECT_DIR, 'app.py')], {
      cwd: PROJECT_DIR,
      env: { ...process.env, PORT: String(PORT) },
      stdio: ['ignore', 'pipe', 'pipe'],
    });

    flaskProcess.stdout.on('data', (data) => {
      const text = data.toString();
      console.log(`[flask] ${text.trim()}`);
      if (text.includes(`http://localhost:${PORT}`)) {
        resolve();
      }
    });

    flaskProcess.stderr.on('data', (data) => {
      console.error(`[flask:err] ${data.toString().trim()}`);
    });

    flaskProcess.on('error', (err) => {
      if (pythons.length > 0) {
        const next = pythons.shift();
        flaskProcess = spawn(next, [path.join(PROJECT_DIR, 'app.py')], {
          cwd: PROJECT_DIR,
          env: { ...process.env, PORT: String(PORT) },
          stdio: ['ignore', 'pipe', 'pipe'],
        });
        // reattach handlers...
        // For simplicity, just reject if first attempt fails
      }
      reject(err);
    });

    flaskProcess.on('exit', (code) => {
      if (code !== 0) {
        console.error(`Flask exited with code ${code}`);
      }
    });

    // Poll until Flask is ready (fallback if stdout check misses it)
    const poll = () => {
      http.get(`http://127.0.0.1:${PORT}`, (res) => {
        resolve();
      }).on('error', () => {
        setTimeout(poll, 300);
      });
    };
    setTimeout(poll, 500);
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 900,
    minHeight: 600,
    backgroundColor: '#1C1C1C',
    icon: path.join(PROJECT_DIR, 'static', 'icon.png'),
    title: 'PunkTrader',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  mainWindow.loadURL(`http://127.0.0.1:${PORT}`);
  mainWindow.on('closed', () => { mainWindow = null; });
}

app.whenReady().then(async () => {
  try {
    await startFlask();
    createWindow();
  } catch (err) {
    console.error('Failed to start Flask:', err);
    app.quit();
  }
});

app.on('window-all-closed', () => {
  if (flaskProcess) {
    flaskProcess.kill();
  }
  app.quit();
});

app.on('before-quit', () => {
  if (flaskProcess) {
    flaskProcess.kill();
  }
});
