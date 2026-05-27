<template>
  <div class="settings-view">
    <h2>系统设置</h2>
    <p style="color: #909399; margin-bottom: 20px;">管理 OpsBrain 平台配置</p>

    <el-tabs v-model="activeTab" type="border-card" :tab-position="tabPosition" style="min-height: 500px">
      <!-- ═══ ① 外观 ═══ -->
      <el-tab-pane label="外观" name="theme">
        <div class="tab-content">
          <h3>界面主题</h3>
          <p class="tab-desc">更改 OpsBrain 管理界面的显示主题</p>

          <el-radio-group v-model="currentTheme" @change="changeTheme" size="large">
            <el-radio-button value="light">
              <el-icon style="margin-right: 4px; vertical-align: middle"><Sunny /></el-icon>
              浅色模式
            </el-radio-button>
            <el-radio-button value="dark">
              <el-icon style="margin-right: 4px; vertical-align: middle"><Moon /></el-icon>
              深色模式
            </el-radio-button>
          </el-radio-group>

          <el-divider />

          <div class="theme-preview-box" :class="'preview-' + currentTheme">
            <div class="preview-topbar"></div>
            <div class="preview-body">
              <div class="preview-side"></div>
              <div class="preview-main">
                <div class="preview-card"></div>
                <div class="preview-card"></div>
              </div>
            </div>
          </div>

          <p style="color: #909399; font-size: 12px; margin-top: 12px;">
            当前主题：{{ currentTheme === 'dark' ? '深色模式' : '浅色模式' }}
          </p>
        </div>
      </el-tab-pane>

      <!-- ═══ ② 项目文件管理 ═══ -->
      <el-tab-pane label="项目文件" name="projects">
        <div class="tab-content">
          <div class="tab-header">
            <div>
              <h3>项目文件管理</h3>
              <p class="tab-desc">配置拉取的项目、镜像、数据等文件的存放路径</p>
            </div>
          </div>

          <el-form :model="projectForm" label-width="140px" size="default">
            <el-form-item label="项目存储路径">
              <el-input v-model="projectForm.projects_path" placeholder="/var/lib/opsbrain/projects" />
            </el-form-item>
            <el-form-item label="镜像存储路径">
              <el-input v-model="projectForm.images_path" placeholder="/var/lib/opsbrain/images" />
            </el-form-item>
            <el-form-item label="数据存储路径">
              <el-input v-model="projectForm.data_path" placeholder="/var/lib/opsbrain/data" />
            </el-form-item>
            <el-form-item label="日志存储路径">
              <el-input v-model="projectForm.logs_path" placeholder="/var/lib/opsbrain/logs" />
            </el-form-item>
            <el-form-item label="备份存储路径">
              <el-input v-model="projectForm.backup_path" placeholder="/var/lib/opsbrain/backups" />
            </el-form-item>
            <el-form-item label="Docker Registry">
              <el-input v-model="projectForm.docker_registry" placeholder="私有镜像仓库地址（可选）" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="saveProjectConfig">保存配置</el-button>
              <el-button @click="resetProjectConfig">恢复默认</el-button>
            </el-form-item>
          </el-form>
        </div>
      </el-tab-pane>

      <!-- ═══ ③ API 管理 ═══ -->
      <el-tab-pane label="API 管理" name="apis">
        <div class="tab-content">
          <div class="tab-header">
            <div>
              <h3>API Key 管理</h3>
              <p class="tab-desc">参考 OpenClaw 设计，支持多 API 多提供商切换</p>
            </div>
            <el-button type="primary" :icon="Plus" @click="showAddApi = true">
              新增 API Key
            </el-button>
          </div>

          <!-- API Key 列表 -->
          <el-table v-if="apiList.length > 0" :data="apiList" stripe style="width: 100%" max-height="400">
            <el-table-column prop="name" label="名称" min-width="120" />
            <el-table-column prop="provider" label="提供商" width="110">
              <template #default="{ row }">
                <el-tag
                  :type="providerTagType(row.provider)"
                  size="small"
                  effect="plain"
                >{{ row.provider }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="model" label="模型" width="120" />
            <el-table-column label="类型" width="80">
              <template #default="{ row }">
                <el-tag v-if="row.api_type === 'llm'" size="small" type="primary" effect="plain">LLM</el-tag>
                <el-tag v-else size="small" type="warning" effect="plain">向量</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="API Key" width="150">
              <template #default="{ row }">
                <code style="font-size: 12px; color: #909399">{{ maskKey(row.api_key) }}</code>
              </template>
            </el-table-column>
            <el-table-column label="启用" width="90">
              <template #default="{ row }">
                <el-button v-if="!row.is_active" size="small" type="primary" @click="activateApi(row)">启用</el-button>
                <el-tag v-else size="small" type="success" effect="plain">✓ 已启用</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="100">
              <template #default="{ row }">
                <el-button text size="small" type="danger" @click="deleteApi(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>

          <el-empty v-else description="暂无 API Key，点击上方按钮新增" :image-size="80" />

          <!-- 新增 API Key 对话框 -->
          <el-dialog
            v-model="showAddApi"
            title="新增 API Key"
            width="520px"
            :close-on-click-modal="false"
          >
            <el-form :model="apiForm" label-width="100px">
              <el-form-item label="名称" required>
                <el-input v-model="apiForm.name" placeholder="如：生产 DeepSeek" />
              </el-form-item>
              <el-form-item label="提供商" required>
                <el-select v-model="apiForm.provider" style="width: 100%">
                  <el-option label="OpenAI" value="openai" />
                  <el-option label="DeepSeek" value="deepseek" />
                  <el-option label="SiliconFlow" value="siliconflow" />
                  <el-option label="Anthropic" value="anthropic" />
                  <el-option label="Ollama（本地）" value="ollama" />
                  <el-option label="自定义（兼容 OpenAI）" value="custom" />
                </el-select>
              </el-form-item>
              <el-form-item label="API 地址">
                <el-input v-model="apiForm.api_base" placeholder="留空使用提供商默认地址" />
              </el-form-item>
              <el-form-item label="API Key" required>
                <el-input
                  v-model="apiForm.api_key"
                  type="password"
                  show-password
                  placeholder="sk-..."
                />
              </el-form-item>
              <el-form-item label="类型" required>
                <el-select v-model="apiForm.api_type" style="width: 100%">
                  <el-option label="LLM 大模型" value="llm" />
                  <el-option label="向量/嵌入模型" value="embedding" />
                </el-select>
              </el-form-item>
              <el-form-item label="默认模型">
                <el-input v-model="apiForm.model" placeholder="留空使用提供商默认模型" />
              </el-form-item>
              <el-form-item label="设为默认">
                <el-switch v-model="apiForm.is_default" />
              </el-form-item>
            </el-form>
            <template #footer>
              <el-button @click="showAddApi = false">取消</el-button>
              <el-button type="primary" :loading="savingApi" @click="saveApi">
                {{ savingApi ? '保存中...' : '保存' }}
              </el-button>
            </template>
          </el-dialog>
        </div>
      </el-tab-pane>

      <!-- ═══ ④ 飞书集成 ═══ -->
      <el-tab-pane label="飞书集成" name="feishu">
        <div class="tab-content">
          <div class="tab-header">
            <div>
              <h3>飞书机器人</h3>
              <p class="tab-desc">将总控 Commander Agent 接入飞书/Lark，群聊消息自动路由到 Agent 处理</p>
            </div>
            <div>
              <template v-if="feishuConfigured">
                <el-button size="small" type="primary" :icon="Setting" @click="openWizard">重新配置</el-button>
                <el-button
                  size="small"
                  :loading="testingFeishu"
                  @click="testFeishuConnection"
                >{{ testingFeishu ? '测试中...' : '测试连接' }}</el-button>
                <el-button size="small" type="danger" :icon="Delete" @click="resetFeishuConfig">重置配置</el-button>
              </template>
              <template v-else>
                <el-button size="small" type="primary" :icon="Plus" @click="openWizard">开始配置</el-button>
              </template>
            </div>
          </div>

          <!-- 状态卡片 -->
          <div v-if="feishuConfigured" class="feishu-status-card">
            <el-row :gutter="20">
              <el-col :span="8">
                <div class="status-item">
                  <span class="status-label">连接模式</span>
                  <span class="status-value">
                    <el-tag :type="feishuForm.connection_mode === 'websocket' ? 'success' : 'primary'" size="small">
                      {{ feishuForm.connection_mode === 'websocket' ? 'WebSocket' : 'Webhook' }}
                    </el-tag>
                  </span>
                </div>
              </el-col>
              <el-col :span="8">
                <div class="status-item">
                  <span class="status-label">App ID</span>
                  <span class="status-value"><code>{{ feishuForm.app_id }}</code></span>
                </div>
              </el-col>
              <el-col :span="8">
                <div class="status-item">
                  <span class="status-label">域</span>
                  <span class="status-value">{{ feishuForm.domain === 'feishu' ? '飞书' : 'Lark' }}</span>
                </div>
              </el-col>
            </el-row>
            <el-row :gutter="20" style="margin-top:12px">
              <el-col :span="8">
                <div class="status-item">
                  <span class="status-label">群聊策略</span>
                  <span class="status-value">{{ {open:'开放',allowlist:'白名单',disabled:'禁用'}[feishuForm.group_policy] }}</span>
                </div>
              </el-col>
              <el-col :span="8">
                <div class="status-item">
                  <span class="status-label">@提及要求</span>
                  <span class="status-value">{{ feishuForm.require_mention ? '需要@' : '不需要' }}</span>
                </div>
              </el-col>
              <el-col :span="8">
                <div class="status-item">
                  <span class="status-label">启用状态</span>
                  <span class="status-value">
                    <el-tag :type="feishuForm.enabled ? 'success' : 'info'" size="small">
                      {{ feishuForm.enabled ? '已启用' : '已禁用' }}
                    </el-tag>
                  </span>
                </div>
              </el-col>
            </el-row>

            <!-- Webhook URL 展示 -->
            <template v-if="feishuForm.connection_mode === 'webhook'">
              <el-divider />
              <div class="webhook-url-row">
                <span class="status-label" style="min-width:120px">Webhook URL：</span>
                <el-input :model-value="feishuWebhookUrl" readonly size="small" style="flex:1">
                  <template #append>
                    <el-button @click="copyWebhookUrl">复制</el-button>
                  </template>
                </el-input>
              </div>
            </template>

            <!-- 测试结果 -->
            <div v-if="testResult" :class="['test-result-inline', testResult.ok ? 'test-ok' : 'test-fail']">
              <el-icon v-if="testResult.ok" color="#67c23a"><SuccessFilled /></el-icon>
              <el-icon v-else color="#f56c6c"><WarningFilled /></el-icon>
              <span>{{ testResult.message || testResult.error }}</span>
            </div>
          </div>

          <!-- 未配置状态 -->
          <div v-else class="feishu-welcome">
            <div class="welcome-icon">
              <el-icon :size="48" color="#409eff"><Connection /></el-icon>
            </div>
            <h3 style="margin:16px 0 8px">飞书机器人集成</h3>
            <p style="color:#909399;font-size:13px;max-width:480px;margin:0 auto 20px;line-height:1.7">
              将总控 Commander Agent 接入飞书/Lark，团队成员可以在飞书群聊中直接与 Agent 对话，
              查询网络拓扑、设备状态、执行运维任务。
              <br/><br/>
              <strong>只绑定总控 Agent</strong>：飞书消息路由到 Commander Agent，由它调度 Subagent 执行具体任务。
            </p>
            <el-button type="primary" size="large" :icon="Plus" @click="openWizard">开始配置</el-button>

            <!-- 集成文档 -->
            <el-divider />
            <div class="feishu-docs">
              <h4>📖 飞书集成指南</h4>
              <div class="docs-grid">
                <div class="doc-card" @click="openWizard('websocket')">
                  <div class="doc-card-icon"><el-icon :size="28" color="#67c23a"><Connection /></el-icon></div>
                  <div class="doc-card-title">WebSocket 模式</div>
                  <div class="doc-card-desc">长连接实时通信，无需公网地址，适合内网部署</div>
                  <div class="doc-card-steps">
                    ① 飞书开放平台创建应用<br/>
                    ② 获取 App ID + App Secret<br/>
                    ③ 事件回调 → 选择「长连接(WebSocket)」<br/>
                    ④ 开启接收消息事件<br/>
                    ⑤ 发布应用，拉入群聊
                  </div>
                </div>
                <div class="doc-card" @click="openWizard('webhook')">
                  <div class="doc-card-icon"><el-icon :size="28" color="#409eff"><Link /></el-icon></div>
                  <div class="doc-card-title">Webhook 模式</div>
                  <div class="doc-card-desc">HTTP POST 回调，需公网可访问地址，适合云服务器</div>
                  <div class="doc-card-steps">
                    ① 飞书开放平台创建应用<br/>
                    ② 获取 App ID + App Secret<br/>
                    ③ 事件订阅设置回调 URL<br/>
                    ④ 配置 Verification Token / Encrypt Key<br/>
                    ⑤ 发布应用，拉入群聊
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </el-tab-pane>

      <!-- 飞书配置向导对话框 -->
      <el-dialog
        v-model="showWizard"
        title="飞书机器人设置向导"
        width="680px"
        :close-on-click-modal="false"
        :before-close="closeWizard"
      >
        <div class="wizard-steps">
          <el-steps :active="wizardStep - 1" align-center finish-status="success" style="margin-bottom:24px">
            <el-step title="连接方式" />
            <el-step title="设置方式" />
            <el-step title="配置凭证" />
            <el-step title="测试连接" />
            <el-step title="完成" />
          </el-steps>
        </div>

        <!-- Step 1: 选择连接模式 -->
        <div v-if="wizardStep === 1" class="wizard-content">
          <h3 style="margin-bottom:16px">选择连接方式</h3>
          <p style="color:#909399;font-size:13px;margin-bottom:20px">飞书支持两种连接方式，请根据部署环境选择：</p>

          <div class="mode-cards">
            <div
              :class="['mode-card', { active: wizardForm.connection_mode === 'websocket' }]"
              @click="wizardForm.connection_mode = 'websocket'"
            >
              <el-icon :size="36" color="#67c23a"><Connection /></el-icon>
              <div class="mode-card-title">WebSocket 模式</div>
              <div class="mode-card-desc">长连接实时通信</div>
              <div class="mode-card-details">
                <span class="tag-green">✅ 无需公网</span>
                <span class="tag-green">✅ 实时推送</span>
                <span class="tag-green">✅ 适合内网</span>
              </div>
              <div class="mode-card-info">
                OpsBrain 主动连接飞书 WebSocket 端点，
                保持长连接接收实时消息事件。
                配置简单，稳定性好。
              </div>
            </div>

            <div
              :class="['mode-card', { active: wizardForm.connection_mode === 'webhook' }]"
              @click="wizardForm.connection_mode = 'webhook'"
            >
              <el-icon :size="36" color="#409eff"><Link /></el-icon>
              <div class="mode-card-title">Webhook 模式</div>
              <div class="mode-card-desc">HTTP POST 回调</div>
              <div class="mode-card-details">
                <span class="tag-blue">🔗 需公网</span>
                <span class="tag-blue">📡 标准协议</span>
                <span class="tag-blue">☁️ 适云服务器</span>
              </div>
              <div class="mode-card-info">
                飞书通过 HTTP POST 将事件推送到 OpsBrain。
                需要公网可访问的地址，
                可通过反向代理暴露。
              </div>
            </div>
          </div>
        </div>

        <!-- Step 2: 选择设置方式 -->
        <div v-if="wizardStep === 2" class="wizard-content">
          <h3 style="margin-bottom:16px">选择设置方式</h3>
          <p style="color:#909399;font-size:13px;margin-bottom:20px">选择如何获取飞书应用的 App ID 和 App Secret：</p>

          <div class="setup-method-cards">
            <div
              :class="['setup-method-card', { active: wizardForm.setup_method === 'scan' }]"
              @click="wizardForm.setup_method = 'scan'"
            >
              <el-icon :size="40" color="#409eff"><Camera /></el-icon>
              <div class="method-card-title">扫码注册</div>
              <div class="method-card-desc">
                用飞书 App 扫描二维码，自动创建机器人应用
                <br/>
                <span style="font-size:12px;color:#909399">仅支持飞书国内版，Lark 国际版不可用</span>
              </div>
            </div>

            <div
              :class="['setup-method-card', { active: wizardForm.setup_method === 'manual' }]"
              @click="wizardForm.setup_method = 'manual'"
            >
              <el-icon :size="40" color="#e6a23c"><Edit /></el-icon>
              <div class="method-card-title">手动输入</div>
              <div class="method-card-desc">
                在飞书开放平台创建应用后，手动输入 App ID 和 App Secret
                <br/>
                <span style="font-size:12px;color:#909399">支持飞书国内版和 Lark 国际版</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Step 3a: 扫码等待 -->
        <div v-if="wizardStep === 3 && wizardForm.setup_method === 'scan'" class="wizard-content" style="text-align:center">
          <h3 style="margin-bottom:16px">扫码注册应用</h3>

          <div v-if="qrCodeImg" class="qr-area">
            <img :src="qrCodeImg" alt="QR Code" style="width:220px;height:220px;border:2px solid #eee;border-radius:8px;padding:8px" />
            <p style="margin:12px 0;color:#606266;font-size:13px">
              请使用飞书 App 扫描上方二维码<br/>
              扫码后在飞书中确认授权，系统将自动获取应用凭证
            </p>
            <div>
              <el-button size="small" @click="cancelQrScan" :disabled="!qrPolling">取消扫码，改为手动输入</el-button>
            </div>
          </div>

          <div v-else-if="qrError" class="qr-error">
            <el-icon :size="48" color="#f56c6c"><WarningFilled /></el-icon>
            <p style="margin:12px 0;color:#909399;font-size:13px">{{ qrError }}</p>
            <el-button @click="wizardForm.setup_method = 'manual'; wizardStep = 2">改为手动输入</el-button>
          </div>

          <div v-else>
            <p style="color:#909399;font-size:13px">正在初始化...</p>
          </div>
        </div>

        <!-- Step 3b: 手动输入凭证 -->
        <div v-if="wizardStep === 3 && wizardForm.setup_method === 'manual'" class="wizard-content">
          <h3 style="margin-bottom:16px">填写应用凭证</h3>
          <p style="color:#909399;font-size:13px;margin-bottom:16px">
            在 <a href="https://open.feishu.cn" target="_blank" style="color:#409eff">飞书开放平台</a> 创建企业自建应用后，
            获取以下信息：
          </p>

          <el-form :model="wizardForm" label-width="140px" size="default">
            <el-form-item label="域名" required>
              <el-select v-model="wizardForm.domain" style="width:100%">
                <el-option label="飞书 (feishu.cn)" value="feishu" />
                <el-option label="Lark (larksuite.com)" value="lark" />
              </el-select>
            </el-form-item>
            <el-form-item label="App ID" required>
              <el-input v-model="wizardForm.app_id" placeholder="cli_xxxxxxxxxxxxxx" />
            </el-form-item>
            <el-form-item label="App Secret" required>
              <el-input v-model="wizardForm.app_secret" type="password" show-password placeholder="飞书开放平台获取的 App Secret" />
            </el-form-item>

            <!-- Webhook 模式附加字段 -->
            <template v-if="wizardForm.connection_mode === 'webhook'">
              <el-form-item label="Verification Token">
                <el-input v-model="wizardForm.verification_token" type="password" show-password placeholder="事件订阅中的 Verification Token（可选）" />
              </el-form-item>
              <el-form-item label="Encrypt Key">
                <el-input v-model="wizardForm.encrypt_key" type="password" show-password placeholder="事件订阅中的 Encrypt Key（可选）" />
              </el-form-item>
            </template>

            <template v-if="wizardForm.connection_mode === 'websocket'">
              <el-alert
                type="success"
                :closable="false"
                show-icon
                style="margin-top:12px"
              >
                <template #default>
                  <p style="margin:4px 0;font-size:13px">
                    WebSocket 模式不需要额外的 Token 和 Key。<br/>
                    在飞书开放平台 → 事件与回调 → 选择「长连接(WebSocket)」即可。
                  </p>
                </template>
              </el-alert>
            </template>
          </el-form>
        </div>

        <!-- Step 4: 测试连接 -->
        <div v-if="wizardStep === 4" class="wizard-content">
          <h3 style="margin-bottom:16px">测试连接</h3>
          <p style="color:#909399;font-size:13px;margin-bottom:20px">
            验证 App ID 和 App Secret 是否有效，能否正常连接到飞书 API：
          </p>

          <el-descriptions :column="1" border style="margin-bottom:20px">
            <el-descriptions-item label="连接模式">{{ wizardForm.connection_mode === 'websocket' ? 'WebSocket' : 'Webhook' }}</el-descriptions-item>
            <el-descriptions-item label="域">{{ wizardForm.domain === 'feishu' ? '飞书' : 'Lark' }}</el-descriptions-item>
            <el-descriptions-item label="App ID"><code>{{ wizardForm.app_id }}</code></el-descriptions-item>
            <el-descriptions-item label="Webhook">{{ wizardForm.connection_mode === 'webhook' ? '需要配置回调 URL' : '不需要' }}</el-descriptions-item>
          </el-descriptions>

          <el-button type="primary" :loading="testingFeishu" @click="testWizardConnection" style="margin-bottom:16px">
            {{ testingFeishu ? '测试中...' : '测试连接' }}
          </el-button>

          <div v-if="testResult" :class="['test-result-inline', testResult.ok ? 'test-ok' : 'test-fail']">
            <el-icon v-if="testResult.ok" color="#67c23a"><SuccessFilled /></el-icon>
            <el-icon v-else color="#f56c6c"><WarningFilled /></el-icon>
            <span>{{ testResult.message || testResult.error }}</span>
          </div>
        </div>

        <!-- Step 5: 完成 -->
        <div v-if="wizardStep === 5" class="wizard-content" style="text-align:center">
          <el-icon :size="56" color="#67c23a" style="margin:20px 0"><SuccessFilled /></el-icon>
          <h3 style="margin-bottom:8px">配置摘要</h3>

          <el-descriptions :column="1" border style="max-width:400px;margin:0 auto 24px">
            <el-descriptions-item label="连接模式">{{ wizardForm.connection_mode === 'websocket' ? 'WebSocket' : 'Webhook' }}</el-descriptions-item>
            <el-descriptions-item label="域名">{{ wizardForm.domain === 'feishu' ? '飞书' : 'Lark' }}</el-descriptions-item>
            <el-descriptions-item label="App ID"><code>{{ wizardForm.app_id }}</code></el-descriptions-item>
            <el-descriptions-item label="连接测试">
              <el-tag :type="testResult?.ok ? 'success' : (testResult ? 'danger' : 'info')" size="small">
                {{ testResult?.ok ? '通过' : (testResult ? '失败' : '未测试') }}
              </el-tag>
            </el-descriptions-item>
          </el-descriptions>

          <p style="color:#909399;font-size:13px;margin-bottom:20px">
            <template v-if="wizardForm.connection_mode === 'websocket'">
              保存配置后，OpsBrain 将自动启动 WebSocket 连接。将机器人拉入群聊即可开始使用。
            </template>
            <template v-else>
              保存配置后，还需将下方 URL 配置到飞书开放平台的事件订阅中：
              <br/>
              <code style="font-size:12px;word-break:break-all">{{ feishuWebhookUrl }}</code>
              <el-button size="small" @click="copyWebhookUrl" style="margin-left:8px">复制</el-button>
            </template>
          </p>
        </div>

        <template #footer>
          <el-button v-if="wizardStep > 1 && wizardStep < 5" @click="prevStep">上一步</el-button>
          <el-button
            v-if="wizardStep < 5"
            type="primary"
            :disabled="wizardStep === 3 && wizardForm.setup_method === 'scan' && !wizardForm.app_id"
            @click="nextStep"
          >
            {{ wizardStep === 4 ? '跳过测试，继续' : '下一步' }}
          </el-button>
          <el-button
            v-if="wizardStep === 5"
            type="primary"
            :loading="savingFeishu"
            @click="saveWizardConfig"
          >
            {{ savingFeishu ? '保存中...' : '✅ 确认并保存' }}
          </el-button>
        </template>
      </el-dialog>

      <!-- ═══ ⑤ 关于 ═══ -->
      <el-tab-pane label="关于" name="about">
        <div class="tab-content" style="text-align: center">
          <div style="padding: 40px 0">
            <h1 style="font-size: 36px; font-weight: 800; color: #409eff; letter-spacing: 4px; margin-bottom: 8px;">
              OpsBrain
            </h1>
            <p style="color: #909399; margin-bottom: 32px;">企业网络智能运维平台</p>

            <el-descriptions :column="1" border style="max-width: 420px; margin: 0 auto">
              <el-descriptions-item label="版本">0.1.0</el-descriptions-item>
              <el-descriptions-item label="后端">FastAPI + SQLAlchemy + SQLite</el-descriptions-item>
              <el-descriptions-item label="前端">Vue 3 + Element Plus + Vite</el-descriptions-item>
              <el-descriptions-item label="引擎">Python 3.12 / Paramiko / TextFSM</el-descriptions-item>
              <el-descriptions-item label="部署">Docker Compose</el-descriptions-item>
              <el-descriptions-item label="数据目录">/var/lib/opsbrain</el-descriptions-item>
              <el-descriptions-item label="作者">OpsBrain Team</el-descriptions-item>
            </el-descriptions>
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Sunny, Moon, Plus, Link, Connection, SuccessFilled, WarningFilled, Setting, Camera, Edit, Delete } from '@element-plus/icons-vue'
import { api } from '@/stores/auth'

const activeTab = ref('theme')
const tabPosition = ref(window.innerWidth < 768 ? 'top' : 'left')

// ── 主题 ──────────────────────────────────────────────────────────────
const currentTheme = ref(localStorage.getItem('opsbrain-theme') || 'dark')

function changeTheme(val) {
  currentTheme.value = val
  document.documentElement.setAttribute('data-theme', val)
  localStorage.setItem('opsbrain-theme', val)
}

// ── 项目文件 ──────────────────────────────────────────────────────────
const projectForm = reactive({
  projects_path: '/var/lib/opsbrain/projects',
  images_path: '/var/lib/opsbrain/images',
  data_path: '/var/lib/opsbrain/data',
  logs_path: '/var/lib/opsbrain/logs',
  backup_path: '/var/lib/opsbrain/backups',
  docker_registry: '',
  image_cache_path: '/var/lib/opsbrain/images/cache',
})

function saveProjectConfig() {
  ElMessage.success('项目文件配置已保存')
}

function resetProjectConfig() {
  Object.assign(projectForm, {
    projects_path: '/var/lib/opsbrain/projects',
    images_path: '/var/lib/opsbrain/images',
    data_path: '/var/lib/opsbrain/data',
    logs_path: '/var/lib/opsbrain/logs',
    backup_path: '/var/lib/opsbrain/backups',
    docker_registry: '',
    image_cache_path: '/var/lib/opsbrain/images/cache',
  })
  ElMessage.success('已恢复默认值')
}

// ── API Key ───────────────────────────────────────────────────────────
const apiList = ref([])
const showAddApi = ref(false)
const savingApi = ref(false)
const apiForm = reactive({
  name: '', provider: 'deepseek', api_base: '',
  api_key: '', api_type: 'llm', model: '', is_default: false,
})

async function loadApis() {
  try {
    const res = await api.get('/apis/')
    apiList.value = res.data.api_keys || []
  } catch {
    apiList.value = []
  }
}

async function saveApi() {
  savingApi.value = true
  try {
    await api.post('/apis/', { ...apiForm })
    ElMessage.success('API Key 已添加')
    showAddApi.value = false
    Object.assign(apiForm, { name: '', provider: 'deepseek', api_base: '', api_key: '', api_type: 'llm', model: '', is_default: false })
    await loadApis()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  } finally {
    savingApi.value = false
  }
}

async function activateApi(row) {
  try {
    // 关闭所有其他 API，启用当前这一个
    for (const k of apiList.value) {
      if (k.is_active && k.id !== row.id) {
        await api.post(`/apis/${k.id}/toggle`)
        k.is_active = false
      }
    }
    if (!row.is_active) {
      await api.post(`/apis/${row.id}/toggle`)
      row.is_active = true
    }
    // 自动设为默认
    if (!row.is_default) await api.post(`/apis/${row.id}/set-default`)
    row.is_default = true
  } catch { ElMessage.error('操作失败') }
}

async function deleteApi(row) {
  try {
    await ElMessageBox.confirm(`确定删除 API Key「${row.name}」？`, '确认删除', { type: 'warning' })
    await api.delete(`/apis/${row.id}`)
    ElMessage.success('已删除')
    await loadApis()
  } catch {}
}

function providerTagType(provider) {
  const map = { openai: '', deepseek: 'success', siliconflow: 'warning', ollama: 'info', custom: 'danger' }
  return map[provider] || 'info'
}

function maskKey(key) {
  if (!key) return ''
  if (key.length <= 12) return '****' + key.slice(-4)
  return key.slice(0, 8) + '****' + key.slice(-4)
}

// ── 飞书集成 ───────────────────────────────────────────────────────────
const feishuForm = reactive({
  enabled: false,
  connection_mode: 'webhook',
  domain: 'feishu',
  app_id: '',
  app_secret: '',
  verification_token: '',
  encrypt_key: '',
  webhook_path: '/opsbrain/api/v1/agent/feishu-webhook',
  group_policy: 'allowlist',
  require_mention: true,
  dm_policy: 'pairing',
})

const feishuConfigured = ref(false)
const savingFeishu = ref(false)
const testingFeishu = ref(false)
const testResult = ref(null)

// 设置向导
const showWizard = ref(false)
const wizardStep = ref(1)
const wizardForm = reactive({
  connection_mode: 'websocket',
  setup_method: 'manual',  // manual | scan
  domain: 'feishu',
  app_id: '',
  app_secret: '',
  verification_token: '',
  encrypt_key: '',
})

// 扫码相关
const qrState = ref(null)        // { device_code, qr_url, user_code, interval, expire_in }
const qrPolling = ref(false)
const qrCodeImg = ref('')
const qrError = ref('')

const feishuWebhookUrl = computed(() => {
  const host = window.location.host
  const path = '/opsbrain/api/v1/agent/feishu-webhook'
  return `https://${host}${path}`
})

async function loadFeishuConfig() {
  try {
    const res = await api.get('/feishu/config')
    const data = res.data
    feishuConfigured.value = data.configured ?? false
    feishuForm.enabled = data.enabled ?? false
    feishuForm.connection_mode = data.connection_mode || 'webhook'
    feishuForm.domain = data.domain || 'feishu'
    feishuForm.app_id = data.app_id || ''
    feishuForm.webhook_path = data.webhook_path || '/opsbrain/api/v1/agent/feishu-webhook'
    feishuForm.group_policy = data.group_policy || 'allowlist'
    feishuForm.require_mention = data.require_mention ?? true
    feishuForm.dm_policy = data.dm_policy || 'pairing'
  } catch {
    feishuConfigured.value = false
  }
}

function openWizard(mode) {
  // 重置向导表单
  Object.assign(wizardForm, {
    connection_mode: mode || feishuForm.connection_mode || 'websocket',
    setup_method: 'manual',
    domain: feishuForm.domain || 'feishu',
    app_id: feishuForm.app_id || '',
    app_secret: '',
    verification_token: feishuForm.verification_token || '',
    encrypt_key: feishuForm.encrypt_key || '',
  })
  wizardStep.value = 1
  qrState.value = null
  qrCodeImg.value = ''
  qrError.value = ''
  testResult.value = null
  showWizard.value = true
}

function closeWizard() {
  showWizard.value = false
  if (qrPolling.value) {
    qrPolling.value = false
  }
}

async function nextStep() {
  const s = wizardStep.value

  if (s === 1) {
    // Step 1: 选择了连接模式，进入下一步
    wizardStep.value = 2
    return
  }

  if (s === 2) {
    if (wizardForm.setup_method === 'scan') {
      // 扫码模式：发起扫码
      wizardStep.value = 3
      await beginQrScan()
      return
    }
    // 手动模式：跳到填写凭证
    wizardStep.value = 3
    return
  }

  if (s === 3) {
    if (wizardForm.setup_method === 'manual') {
      // 验证必填字段
      if (!wizardForm.app_id || !wizardForm.app_secret) {
        ElMessage.warning('请填写 App ID 和 App Secret')
        return
      }
    } else {
      // 扫码模式，等待扫描结果
      if (!qrState.value?.device_code) {
        ElMessage.warning('请先扫描二维码')
        return
      }
    }
    wizardStep.value = 4
    return
  }

  if (s === 4) {
    // 测试连接
    if (wizardForm.app_id && wizardForm.app_secret) {
      await testWizardConnection()
    }
    wizardStep.value = 5
    return
  }

  if (s === 5) {
    // 完成：保存配置
    await saveWizardConfig()
    return
  }
}

function prevStep() {
  if (wizardStep.value > 1) {
    wizardStep.value--
  }
}

// ── 扫码注册 ──────────────────────────────────────────────────────

async function beginQrScan() {
  qrError.value = ''
  qrState.value = null
  qrCodeImg.value = ''

  try {
    const res = await api.post('/feishu/qr/begin', {
      domain: wizardForm.domain,
    })
    qrState.value = res.data

    // 用 QR 码 API 生成二维码图片
    // 使用 https://api.qrserver.com 或类似的 qr 码服务
    qrCodeImg.value = `https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=${encodeURIComponent(res.data.qr_url)}`

    // 开始轮询
    qrPolling.value = true
    pollQrResult()
  } catch (e) {
    qrError.value = e.response?.data?.detail || '扫码初始化失败，请使用手动输入方式'
    ElMessage.error(qrError.value)
  }
}

async function pollQrResult() {
  if (!qrState.value || !qrPolling.value) return

  const interval = (qrState.value.interval || 5) * 1000

  const poll = async () => {
    if (!qrPolling.value) return

    try {
      const res = await api.post('/feishu/qr/poll', {
        device_code: qrState.value.device_code,
        domain: wizardForm.domain,
        interval: qrState.value.interval || 5,
      })

      if (res.data.status === 'success') {
        // 扫码成功
        wizardForm.app_id = res.data.app_id
        wizardForm.app_secret = res.data.app_secret
        qrPolling.value = false
        ElMessage.success('✅ 扫码成功！已获取应用凭证')
        // 自动跳到下一步
        wizardStep.value = 4
        return
      }

      if (res.data.status === 'pending') {
        setTimeout(poll, interval)
        return
      }

      // 错误状态
      qrPolling.value = false
      qrError.value = res.data.error || '扫码失败'
      ElMessage.error(qrError.value)
    } catch {
      if (qrPolling.value) {
        setTimeout(poll, interval)
      }
    }
  }

  setTimeout(poll, interval)
}

function cancelQrScan() {
  qrPolling.value = false
  wizardForm.setup_method = 'manual'
  wizardStep.value = 3
}

// ── 测试连接 ──────────────────────────────────────────────────────

async function testWizardConnection() {
  testResult.value = null
  try {
    const res = await api.post('/feishu/test', {
      connection_mode: wizardForm.connection_mode,
      app_id: wizardForm.app_id,
      app_secret: wizardForm.app_secret,
      domain: wizardForm.domain,
      verification_token: wizardForm.verification_token,
      encrypt_key: wizardForm.encrypt_key,
    })
    testResult.value = res.data
  } catch (e) {
    testResult.value = { ok: false, error: e.response?.data?.detail || '测试请求失败' }
  }
}

async function saveWizardConfig() {
  savingFeishu.value = true
  try {
    await api.put('/feishu/config', {
      enabled: true,
      connection_mode: wizardForm.connection_mode,
      domain: wizardForm.domain,
      app_id: wizardForm.app_id,
      app_secret: wizardForm.app_secret,
      verification_token: wizardForm.verification_token || '',
      encrypt_key: wizardForm.encrypt_key || '',
      group_policy: 'allowlist',
      require_mention: true,
      webhook_path: '/opsbrain/api/v1/agent/feishu-webhook',
    })
    ElMessage.success('✅ 飞书集成配置完成！')
    closeWizard()
    await loadFeishuConfig()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  } finally {
    savingFeishu.value = false
  }
}

// ── 已配置后的操作 ──────────────────────────────────────────────

async function testFeishuConnection() {
  if (!feishuForm.app_id) {
    ElMessage.warning('尚未配置飞书')
    return
  }
  testingFeishu.value = true
  testResult.value = null
  try {
    // 不发送 app_secret（可能是掩码值），由后端从数据库加载真实值
    const res = await api.post('/feishu/test', {
      connection_mode: feishuForm.connection_mode,
      app_id: feishuForm.app_id,
      app_secret: '',  // 后端会从 DB 加载真实值
      domain: feishuForm.domain,
    })
    testResult.value = res.data
    if (res.data.ok) {
      ElMessage.success(res.data.message || '连接测试成功')
    } else {
      ElMessage.error(res.data.error || '连接测试失败')
    }
  } catch (e) {
    testResult.value = { ok: false, error: e.response?.data?.detail || '测试请求失败' }
    ElMessage.error('测试请求失败')
  } finally {
    testingFeishu.value = false
  }
}

function copyWebhookUrl() {
  navigator.clipboard.writeText(feishuWebhookUrl.value).then(() => {
    ElMessage.success('已复制 Webhook URL')
  }).catch(() => {
    ElMessage.warning('复制失败，请手动复制')
  })
}

async function resetFeishuConfig() {
  try {
    await ElMessageBox.confirm(
      '确定要重置飞书集成配置吗？这将清除所有已保存的 App ID、App Secret 等设置。',
      '确认重置',
      { type: 'warning', confirmButtonText: '确认重置', cancelButtonText: '取消' }
    )
    await api.post('/feishu/reset')
    ElMessage.success('飞书配置已重置')
    await loadFeishuConfig()
  } catch {}
}

// 页面加载时获取后端配置
onMounted(() => {
  loadApis()
  loadFeishuConfig()
  window.addEventListener('resize', handleResize)
})

function handleResize() {
  tabPosition.value = window.innerWidth < 768 ? 'top' : 'left'
}

</script>

<style scoped>
.settings-view {
  max-width: 1100px;
}

.tab-content {
  padding: 8px 16px;
}

.tab-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
}

.tab-content h3 {
  margin: 0 0 4px;
  font-size: 16px;
}

.tab-desc {
  color: #909399;
  font-size: 13px;
  margin: 0 0 20px;
}

/* Theme preview */
.theme-preview-box {
  border: 1px solid var(--border-color);
  border-radius: 8px;
  overflow: hidden;
  width: 100%;
  max-width: 360px;
  font-size: 0;
}

.theme-preview-box .preview-topbar {
  height: 28px;
  padding: 0 12px;
  display: flex;
  align-items: center;
}

.preview-light .preview-topbar { background: #f5f7fa; border-bottom: 1px solid #e4e7ed; }
.preview-dark .preview-topbar { background: #2c2d2e; border-bottom: 1px solid #363637; }

.theme-preview-box .preview-body {
  display: flex;
  min-height: 80px;
}

.theme-preview-box .preview-side {
  width: 48px;
}

.preview-light .preview-side { background: #fafafa; border-right: 1px solid #e4e7ed; }
.preview-dark .preview-side { background: #252627; border-right: 1px solid #363637; }

.theme-preview-box .preview-main {
  flex: 1;
  padding: 8px;
  display: flex;
  gap: 8px;
}

.theme-preview-box .preview-card {
  flex: 1;
  border-radius: 4px;
  height: 50px;
}

.preview-light .preview-main { background: #f5f7fa; }
.preview-dark .preview-main { background: #161718; }
.preview-light .preview-card { background: #fff; border: 1px solid #e4e7ed; }
.preview-dark .preview-card { background: #1d1e1f; border: 1px solid #363637; }

/* ═══ 飞书集成 ═══ */

/* 欢迎页 */
.feishu-welcome { text-align: center; padding: 32px 0; }
.welcome-icon { display: flex; justify-content: center; }

/* 状态卡片 */
.feishu-status-card {
  background: var(--el-fill-color-lighter, #f5f7fa);
  border: 1px solid var(--el-border-color-light, #e4e7ed);
  border-radius: 8px; padding: 20px;
}
.status-item { display: flex; flex-direction: column; gap: 4px; }
.status-label { font-size: 12px; color: #909399; }
.status-value { font-size: 14px; }
.webhook-url-row { display: flex; align-items: center; gap: 12px; }

/* 文档卡片 */
.feishu-docs { text-align: left; }
.docs-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 16px; }
.doc-card {
  border: 1px solid var(--el-border-color-light, #e4e7ed);
  border-radius: 10px; padding: 20px; cursor: pointer; transition: all 0.2s;
}
.doc-card:hover { border-color: #409eff; box-shadow: 0 2px 12px rgba(64,158,255,0.1); }
.doc-card-icon { margin-bottom: 12px; }
.doc-card-title { font-size: 16px; font-weight: 600; margin-bottom: 6px; }
.doc-card-desc { font-size: 13px; color: #909399; margin-bottom: 12px; }
.doc-card-steps {
  font-size: 12px; color: #606266; line-height: 1.9;
  padding: 10px 12px; background: var(--el-fill-color-lighter, #f5f7fa); border-radius: 6px;
}

/* 设置向导 */
.wizard-content { min-height: 280px; }

/* 连接模式选择卡片 */
.mode-cards { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.mode-card {
  border: 2px solid var(--el-border-color-light, #e4e7ed);
  border-radius: 12px; padding: 24px; cursor: pointer; transition: all 0.2s; text-align: center;
}
.mode-card:hover { border-color: #409eff; box-shadow: 0 4px 16px rgba(64,158,255,0.12); }
.mode-card.active { border-color: #409eff; background: rgba(64,158,255,0.04); }
.mode-card-title { font-size: 18px; font-weight: 700; margin: 12px 0 4px; }
.mode-card-desc { font-size: 13px; color: #909399; margin-bottom: 12px; }
.mode-card-details { display: flex; justify-content: center; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }
.tag-green { font-size: 11px; color: #67c23a; background: #f0f9eb; padding: 2px 8px; border-radius: 4px; }
.tag-blue { font-size: 11px; color: #409eff; background: #ecf5ff; padding: 2px 8px; border-radius: 4px; }
.mode-card-info {
  font-size: 12px; color: #606266; line-height: 1.7;
  text-align: left; padding: 10px 12px;
  background: var(--el-fill-color-lighter, #f5f7fa); border-radius: 6px;
}

/* 设置方式选择卡片 */
.setup-method-cards { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.setup-method-card {
  border: 2px solid var(--el-border-color-light, #e4e7ed);
  border-radius: 12px; padding: 28px 20px; cursor: pointer; transition: all 0.2s; text-align: center;
}
.setup-method-card:hover { border-color: #409eff; box-shadow: 0 4px 16px rgba(64,158,255,0.12); }
.setup-method-card.active { border-color: #409eff; background: rgba(64,158,255,0.04); }
.method-card-title { font-size: 16px; font-weight: 600; margin: 12px 0 8px; }
.method-card-desc { font-size: 13px; color: #909399; line-height: 1.6; }

/* 扫码区域 */
.qr-area { padding: 16px 0; }
.qr-error { padding: 24px 0; }

/* 内联测试结果 */
.test-result-inline { margin-top: 12px; padding: 10px 14px; border-radius: 6px; font-size: 13px; display: flex; align-items: center; gap: 6px; }
.test-ok { background: #f0f9eb; border: 1px solid #e1f3d8; color: #67c23a; }
.test-fail { background: #fef0f0; border: 1px solid #fde2e2; color: #f56c6c; }
[data-theme="dark"] .test-ok { background: #1f2d1c; border-color: #2d4a2d; }
[data-theme="dark"] .test-fail { background: #2d1c1c; border-color: #4a2d2d; }
[data-theme="dark"] .mode-card-info,
[data-theme="dark"] .doc-card-steps { background: #1d1e1f; }
[data-theme="dark"] .feishu-status-card { background: #1d1e1f; border-color: #363637; }
</style>
