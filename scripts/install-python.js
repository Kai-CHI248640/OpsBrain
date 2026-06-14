#!/usr/bin/env node

const { execSync } = require('child_process');
const path = require('path');
const os = require('os');

const rootDir = path.resolve(__dirname, '..');
const venvDir = path.join(rootDir, 'venv');
const reqFile = path.join(rootDir, 'web', 'backend', 'requirements.txt');

const isWin = os.platform() === 'win32';
const pipBin = isWin
  ? path.join(venvDir, 'Scripts', 'pip.exe')
  : path.join(venvDir, 'bin', 'pip');

console.log('📦 安装 Python 依赖...');
try {
  execSync(`"${pipBin}" install -r "${reqFile}"`, { cwd: rootDir, stdio: 'inherit' });
  console.log('✅ Python 依赖已安装');
} catch (e) {
  console.error('❌ 安装失败，请确保虚拟环境已创建');
  process.exit(1);
}
