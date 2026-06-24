<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="emit('update:visible', $event)"
    :title="isEdit ? '编辑定时任务' : '新增定时任务'"
    width="700px"
    :close-on-click-modal="false"
    @close="handleClose"
    :max-height="700"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="100px" style="max-height: 520px; overflow-y: auto;">
      <el-form-item label="任务名称" prop="name">
        <el-input
          v-model="form.name"
          placeholder="请输入任务名称"
          maxlength="50"
          show-word-limit
        />
      </el-form-item>

      <el-form-item label="目标Agent" prop="target_agent_id">
        <el-select
          v-model="form.target_agent_id"
          placeholder="请选择目标Agent"
          style="width: 100%"
        >
          <el-option
            v-for="agent in agents"
            :key="agent.id"
            :label="agent.name"
            :value="agent.id"
          />
        </el-select>
      </el-form-item>

      <el-form-item label="开始时间" prop="start_time">
        <el-date-picker
          v-model="form.start_time"
          type="datetime"
          placeholder="选择开始时间"
          format="yyyy-MM-dd HH:mm"
          value-format="yyyy-MM-dd HH:mm"
        />
      </el-form-item>

      <el-form-item label="时间模式">
        <div class="time-mode-switch">
          <el-button
            :type="form.time_mode === 'simple' ? 'primary' : ''"
            @click="switchTimeMode('simple')"
          >
            简单模式
          </el-button>
          <el-button
            :type="form.time_mode === 'advanced' ? 'primary' : ''"
            @click="switchTimeMode('advanced')"
          >
            高级模式
          </el-button>
        </div>
      </el-form-item>

      <el-form-item label="时间配置">
        <TimeConfigSimple
          v-if="form.time_mode === 'simple'"
          v-model="form.time_config"
          @change="validateForm"
        />
        <TimeConfigAdvanced
          v-else
          v-model="form.time_config"
          @change="validateForm"
        />
      </el-form-item>

      <el-form-item label="任务内容" prop="task_content">
        <el-input
          v-model="form.task_content"
          type="textarea"
          :rows="4"
          placeholder="请输入任务指令描述"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="handleReset">重置</el-button>
      <el-button @click="handleClose">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">
        {{ isEdit ? '保存' : '新增' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, watch } from 'vue'
import TimeConfigSimple from './TimeConfigSimple.vue'
import TimeConfigAdvanced from './TimeConfigAdvanced.vue'

const props = defineProps({
  visible: Boolean,
  editData: Object,
  agents: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['update:visible', 'submit'])

const formRef = ref(null)
const submitting = ref(false)
const isEdit = ref(false)

const form = reactive({
  name: '',
  target_agent_id: '',
  target_agent_name: '',
  start_time: '',
  time_mode: 'simple',
  time_config: {
    weekDays: [],
    time: '',
    interval: 1
  },
  task_content: ''
})

const rules = {
  name: [
    { required: true, message: '请输入任务名称', trigger: 'blur' },
    { max: 50, message: '任务名称不能超过50个字符', trigger: 'blur' }
  ],
  target_agent_id: [
    { required: true, message: '请选择目标Agent', trigger: 'change' }
  ],
  start_time: [
    { required: true, message: '请选择开始时间', trigger: 'change' }
  ],
  task_content: [
    { required: true, message: '请输入任务内容', trigger: 'blur' }
  ]
}

watch(() => props.visible, (val) => {
  if (val) {
    if (props.editData) {
      isEdit.value = true
      Object.assign(form, {
        ...props.editData,
        time_config: props.editData.time_config || { weekDays: [], time: '', interval: 1 }
      })
    } else {
      isEdit.value = false
      resetForm()
    }
  }
})

watch(() => props.editData, (val) => {
  if (val && props.visible) {
    isEdit.value = true
    Object.assign(form, {
      ...val,
      time_config: val.time_config || { weekDays: [], time: '', interval: 1 }
    })
  }
})

function switchTimeMode(mode) {
  form.time_mode = mode
  if (mode === 'simple' && !form.time_config.weekDays) {
    form.time_config = { weekDays: [], time: '', interval: 1 }
  } else if (mode === 'advanced' && !form.time_config.schedules) {
    form.time_config = { schedules: {} }
  }
}

function validateForm() {
  if (formRef.value) {
    formRef.value.validate()
  }
}

function resetForm() {
  form.name = ''
  form.target_agent_id = ''
  form.target_agent_name = ''
  form.start_time = ''
  form.time_mode = 'simple'
  form.time_config = { weekDays: [], time: '', interval: 1 }
  form.task_content = ''
  if (formRef.value) {
    formRef.value.resetFields()
  }
}

function handleReset() {
  resetForm()
}

function handleClose() {
  emit('update:visible', false)
  resetForm()
}

async function handleSubmit() {
  if (!formRef.value) return
  
  try {
    await formRef.value.validate()
  } catch (e) {
    return
  }

  const agent = props.agents.find(a => a.id === form.target_agent_id)
  if (agent) {
    form.target_agent_name = agent.name
  }

  submitting.value = true
  try {
    emit('submit', {
      ...form,
      id: isEdit.value ? props.editData.id : undefined
    })
    handleClose()
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.time-mode-switch {
  display: flex;
  gap: 12px;
}
</style>
