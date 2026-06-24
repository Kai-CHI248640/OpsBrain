#!/usr/bin/env node

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');

const rootDir = path.resolve(__dirname, '..');
const venvDir = path.join(rootDir, 'venv');
const envFile = path.join(rootDir, '.env');
const envExample = path.join(rootDir, '.env.example');
const isWin = os.platform() === 'win32';

console.log('🚀 OpsBrain 项目初始化\n');

function checkNodeVersion() {
  const major = parseInt(process.version.slice(1).split('.')[0]);
  if (major < 18) {
    console.error(`❌ Node.js 版本过低: ${process.version}，需要 >= 18.0.0`);
    process.exit(1);
  }
  console.log(`✅ Node.js ${process.version}`);
}

function checkPythonVersion() {
  try {
    const pythonCmd = isWin ? 'python' : 'python3';
    const version = execSync(`${pythonCmd} --version`, { encoding: 'utf-8' }).trim();
    const match = version.match(/Python (\d+)\.(\d+)/);
    if (!match || parseInt(match[1]) < 3 || (parseInt(match[1]) === 3 && parseInt(match[2]) < 11)) {
      console.error(`❌ Python 版本过低: ${version}，需要 >= 3.11`);
      process.exit(1);
    }
    console.log(`✅ ${version}`);
  } catch (e) {
    console.error('❌ 未找到 Python，请先安装 Python 3.11+');
    process.exit(1);
  }
}

function stopBackend() {
  console.log('\n📦 停止后端进程...');
  try {
    if (isWin) {
      execSync('taskkill /F /IM python.exe /T 2>nul', { stdio: 'ignore' });
    } else {
      execSync('pkill -f "uvicorn app.__init__:app" 2>/dev/null || true', { stdio: 'ignore' });
    }
    console.log('✅ 后端进程已停止');
  } catch (e) {
    console.log('✅ 没有运行中的后端进程');
  }
}

function createVenv() {
  if (fs.existsSync(venvDir)) {
    console.log('✅ Python 虚拟环境已存在');
    return;
  }
  console.log('📦 创建 Python 虚拟环境...');
  const pythonCmd = isWin ? 'python' : 'python3';
  execSync(`${pythonCmd} -m venv venv`, { cwd: rootDir, stdio: 'inherit' });
  console.log('✅ Python 虚拟环境已创建');
}

function installNodeDeps() {
  console.log('\n📦 安装 Node.js 依赖...');
  execSync('npm install', { cwd: rootDir, stdio: 'inherit' });
  console.log('✅ 根目录依赖已安装');
  execSync('npm install', { cwd: path.join(rootDir, 'web', 'frontend'), stdio: 'inherit' });
  console.log('✅ 前端依赖已安装');
}

function installPythonDeps() {
  console.log('\n📦 安装 Python 依赖...');
  const pipBin = isWin
    ? path.join(venvDir, 'Scripts', 'pip.exe')
    : path.join(venvDir, 'bin', 'pip');
  const reqFile = path.join(rootDir, 'web', 'backend', 'requirements.txt');
  if (!fs.existsSync(reqFile)) {
    console.log('⚠️  未找到 requirements.txt，跳过');
    return;
  }
  execSync(`"${pipBin}" install -r "${reqFile}"`, { cwd: rootDir, stdio: 'inherit' });
  console.log('✅ Python 依赖已安装');
}

function createEnvFile() {
  if (fs.existsSync(envFile)) {
    console.log('✅ .env 文件已存在');
    return;
  }
  if (fs.existsSync(envExample)) {
    fs.copyFileSync(envExample, envFile);
    console.log('✅ 已从 .env.example 创建 .env 文件');
  }
}

function resetDatabase() {
  const dbPath = isWin
    ? path.join(os.homedir(), '.opsbrain', 'opsbrain.db')
    : '/var/lib/opsbrain/opsbrain.db';
  if (fs.existsSync(dbPath)) {
    try {
      fs.unlinkSync(dbPath);
      console.log('✅ 已删除数据库文件，项目将重新初始化');
      console.log('⚠️  请清除浏览器缓存和 localStorage（按 F12 → Application → Local Storage → 删除 opsbrain-token 和 opsbrain-user）');
    } catch (e) {
      if (e.code === 'EBUSY') {
        console.error('❌ 数据库被占用，请先停止后端');
        process.exit(1);
      }
    }
  } else {
    console.log('✅ 数据库文件不存在，无需删除');
  }
}

try {
  console.log('='.repeat(50));
  console.log('  环境检查');
  console.log('='.repeat(50) + '\n');
  checkNodeVersion();
  checkPythonVersion();

  console.log('\n' + '='.repeat(50));
  console.log('  依赖安装');
  console.log('='.repeat(50));
  createVenv();
  installNodeDeps();
  installPythonDeps();
  createEnvFile();

  console.log('\n' + '='.repeat(50));
  console.log('  数据库重置');
  console.log('='.repeat(50));
  stopBackend();
  resetDatabase();

  console.log('\n' + '='.repeat(50));
  console.log('  🎉 初始化完成！');
  console.log('='.repeat(50));
  console.log('\n下一步:');
  console.log('  1. 编辑 .env 文件配置环境变量');
  console.log('  2. 运行 npm run dev 启动开发环境');
  console.log('  3. 访问 http://localhost:3000 进行注册\n');
} catch (e) {
  console.error('\n❌ 初始化失败:', e.message);
  process.exit(1);
}
