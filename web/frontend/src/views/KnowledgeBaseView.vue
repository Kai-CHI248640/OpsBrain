<template>
  <div class="kb-view">
    <h2>知识库</h2>
    <p style="color:#909399;margin-bottom:20px">网络设备配置命令模板（Cisco/Huawei/H3C/Juniper 等）</p>

    <el-row :gutter="16">
      <el-col :xs="24" :md="12">
        <el-card>
          <template #header>
            <div style="display:flex;align-items:center;justify-content:space-between">
              <span>📚 配置模板 ({{ configs.length }})</span>
              <el-button type="primary" size="small" @click="showImport = true">📥 导入</el-button>
            </div>
          </template>
          <el-table :data="configs" stripe size="small" max-height="500">
            <el-table-column prop="vendor" label="厂商" width="80">
              <template #default="{row}">
                <el-tag size="small" effect="plain">{{ row.vendor === '*' ? '通用' : row.vendor }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="task" label="任务" min-width="120" />
            <el-table-column prop="commands" label="命令" min-width="180" show-overflow-tooltip />
            <el-table-column prop="notes" label="说明" min-width="120" show-overflow-tooltip />
          </el-table>
        </el-card>
      </el-col>

      <el-col :xs="24" :md="12">
        <el-card style="margin-bottom:16px">
          <template #header><span>🔍 搜索配置</span></template>
          <el-input v-model="searchQuery" placeholder="如: VLAN, 端口, 路由..." size="small" style="margin-bottom:8px">
            <template #prepend>
              <el-select v-model="searchVendor" style="width:90px">
                <el-option label="全部" value="*" />
                <el-option label="Cisco" value="cisco" />
                <el-option label="华为" value="huawei" />
                <el-option label="H3C" value="h3c" />
                <el-option label="Juniper" value="juniper" />
              </el-select>
            </template>
          </el-input>
          <el-button type="primary" size="small" @click="doSearch" :loading="searching">搜索</el-button>
          <div v-if="searchResults.length" style="margin-top:12px">
            <div v-for="(r, i) in searchResults" :key="i" class="search-item">
              <el-tag size="small" effect="plain">{{ r.vendor === '*' ? '通用' : r.vendor }}</el-tag>
              <strong>{{ r.task }}</strong>
              <code>{{ r.commands.substring(0, 100) }}</code>
              <span style="color:#909399;font-size:11px">{{ r.notes }}</span>
            </div>
          </div>
        </el-card>

        <el-card>
          <template #header><span>📈 统计</span></template>
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item v-for="(v, k) in summary.vendors" :key="k" :label="k === '*' ? '通用' : k">{{ v }} 条</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
    </el-row>

    <!-- 导入对话框 -->
    <el-dialog v-model="showImport" title="导入知识库" width="420px">
      <el-upload
        ref="uploadRef"
        :auto-upload="false"
        :limit="1"
        accept=".csv,.xlsx,.xls"
        :on-change="onFileChange"
      >
        <template #trigger>
          <el-button type="primary">选择文件</el-button>
        </template>
        <template #tip>
          <div class="el-upload__tip" style="margin-top:8px">
            支持 CSV / XLSX / XLS 格式<br>
            表头: vendor/厂商, task/任务, commands/命令, notes/备注
          </div>
        </template>
      </el-upload>
      <template #footer>
        <el-button @click="showImport = false">取消</el-button>
        <el-button type="primary" :loading="importing" :disabled="!selectedFile" @click="doImport">
          开始导入
        </el-button>
      </template>
    </el-dialog>

    <!-- 导入结果提示 -->
    <el-alert
      v-if="importResult"
      :title="importResult"
      :type="importResultOk ? 'success' : 'error'"
      show-icon
      closable
      style="margin-top:12px"
      @close="importResult = ''"
    />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { api } from '@/stores/auth'
import { ElMessage } from 'element-plus'

const configs = ref([])
const summary = reactive({ total: 0, vendors: {} })
const searchQuery = ref('')
const searchVendor = ref('*')
const searchResults = ref([])
const searching = ref(false)

const showImport = ref(false)
const selectedFile = ref(null)
const importing = ref(false)
const importResult = ref('')
const importResultOk = ref(false)

onMounted(async () => {
  try {
    const res = await api.get('/dashboard/knowledge')
    configs.value = res.data.configs || []
    Object.assign(summary, res.data.summary || {})
  } catch {}
})

async function doSearch() {
  if (!searchQuery.value.trim()) return
  searching.value = true
  try {
    const res = await api.post('/dashboard/knowledge/search', {
      query: searchQuery.value.trim(),
      vendor: searchVendor.value,
      top_k: 10,
    })
    searchResults.value = res.data.results || []
  } catch {} finally { searching.value = false }
}

function onFileChange(file) {
  selectedFile.value = file.raw
}

async function doImport() {
  if (!selectedFile.value) return
  importing.value = true
  importResult.value = ''
  try {
    const formData = new FormData()
    formData.append('file', selectedFile.value)
    const res = await api.post('/dashboard/knowledge/import-file', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    const data = res.data
    if (data.added && data.added > 0) {
      importResult.value = `✅ 成功导入 ${data.added} 条配置，共 ${data.total} 条`
      importResultOk.value = true
      // 刷新列表
      const listRes = await api.get('/dashboard/knowledge')
      configs.value = listRes.data.configs || []
      Object.assign(summary, listRes.data.summary || {})
      showImport.value = false
    } else {
      importResult.value = `❌ 导入失败：${data.error || '无有效数据'}`
      importResultOk.value = false
    }
  } catch (e) {
    importResult.value = `❌ 导入出错：${e.response?.data?.detail || e.message}`
    importResultOk.value = false
  } finally {
    importing.value = false
  }
}
</script>

<style scoped>
.kb-view { max-width: 1200px; }
.search-item { padding: 8px; border-bottom: 1px solid var(--border-color); display: flex; flex-direction: column; gap: 4px; }
.search-item code { font-size: 11px; background: var(--main-bg); padding: 2px 6px; border-radius: 3px; }
</style>
