<template>
  <div class="time-config-simple">
    <div class="week-row">
      <span class="label">星期选择</span>
      <div class="week-buttons">
        <el-button
          v-for="day in weekDays"
          :key="day.value"
          :type="config.weekDays?.includes(day.value) ? 'primary' : ''"
          :size="config.weekDays?.includes(day.value) ? 'default' : 'small'"
          @click="toggleDay(day.value)"
        >
          {{ day.label }}
        </el-button>
      </div>
      <div class="week-actions">
        <el-button size="small" text @click="selectAllDays">全选</el-button>
        <el-button size="small" text @click="clearAllDays">清除</el-button>
      </div>
    </div>

    <div class="time-row">
      <span class="label">执行时间</span>
      <div class="time-inputs">
        <el-time-picker
          v-model="config.time"
          type="time"
          placeholder="选择时间"
          format="HH:mm"
          value-format="HH:mm"
          @change="emitChange"
        />
      </div>
    </div>

    <div class="interval-row">
      <span class="label">循环间隔</span>
      <div class="interval-inputs">
        <el-input-number
          v-model="config.interval"
          :min="1"
          :max="24"
          :step="1"
          style="width: 100px"
        />
        <span class="interval-unit">小时</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, watch } from 'vue'

const props = defineProps({
  modelValue: {
    type: Object,
    default: () => ({})
  }
})

const emit = defineEmits(['update:modelValue', 'change'])

const weekDays = [
  { label: '一', value: 1 },
  { label: '二', value: 2 },
  { label: '三', value: 3 },
  { label: '四', value: 4 },
  { label: '五', value: 5 },
  { label: '六', value: 6 },
  { label: '日', value: 0 },
]

const config = reactive({
  weekDays: props.modelValue.weekDays || [],
  time: props.modelValue.time || '',
  interval: props.modelValue.interval || 1,
})

watch(() => props.modelValue, (val) => {
  if (val) {
    config.weekDays = val.weekDays || []
    config.time = val.time || ''
    config.interval = val.interval || 1
  }
}, { deep: true })

function toggleDay(day) {
  const index = config.weekDays.indexOf(day)
  if (index === -1) {
    config.weekDays.push(day)
  } else {
    config.weekDays.splice(index, 1)
  }
  emitChange()
}

function selectAllDays() {
  config.weekDays = [0, 1, 2, 3, 4, 5, 6]
  emitChange()
}

function clearAllDays() {
  config.weekDays = []
  emitChange()
}

function emitChange() {
  emit('update:modelValue', {
    weekDays: [...config.weekDays],
    time: config.time,
    interval: config.interval,
  })
  emit('change')
}
</script>

<style scoped>
.time-config-simple {
  padding: 12px;
}

.week-row, .time-row, .interval-row {
  display: flex;
  align-items: center;
  margin-bottom: 16px;
}

.week-row:last-child, .time-row:last-child, .interval-row:last-child {
  margin-bottom: 0;
}

.label {
  width: 100px;
  font-weight: 500;
  color: #606266;
}

.week-buttons {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.week-actions {
  margin-left: 16px;
  display: flex;
  gap: 8px;
}

.time-inputs {
  flex: 1;
}

.interval-inputs {
  display: flex;
  align-items: center;
  gap: 8px;
}

.interval-unit {
  color: #909399;
}
</style>
