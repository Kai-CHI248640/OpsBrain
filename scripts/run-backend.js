#!/usr/bin/env node

const { execSync, spawn } = require('child_process');
const path = require('path');
const os = require('os');

const rootDir = path.resolve(__dirname, '..');
const venvDir = path.join(rootDir, 'venv');
const backendDir = path.join(rootDir, 'web', 'backend');

const isWin = os.platform() === 'win32';
const pythonBin = isWin
  ? path.join(venvDir, 'Scripts', 'python.exe')
  : path.join(venvDir, 'bin', 'python');

const reload = process.argv.includes('--reload');

const args = [
  '-m', 'uvicorn', 'app.__init__:app',
  '--host', '0.0.0.0', '--port', '8000',
];
if (reload) args.push('--reload');

const child = spawn(pythonBin, args, {
  cwd: backendDir,
  stdio: 'inherit',
});

child.on('exit', (code) => process.exit(code));
