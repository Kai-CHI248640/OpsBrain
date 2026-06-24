<template>
  <div class="time-config-advanced">
    <div class="matrix-container">
      <div class="time-header">
        <div class="day-label-cell"></div>
        <div 
          v-for="hour in 24" 
          :key="hour" 
          class="hour-cell"
          :class="{ active: isHourActive(hour) }"
        >
          {{ hour - 1 }}:00
        </div>
      </div>
      
      <div 
        v-for="day in weekDays" 
        :key="day.value" 
        class="day-row"
      >
        <div class="day-label-cell">{{ day.label }}</div>
        <div 
          v-for="hour in 24" 
          :key="hour" 
          class="hour-cell"
          :class="{ 
            active: isTimeActive(day.value, hour),
            hover: hoveredCell?.day === day.value && hoveredCell?.hour === hour
          }"
          @click="toggleTime(day.value, hour)"
          @mouseenter="hoveredCell = { day: day.value, hour: hour }"
          @mouseleave="hoveredCell = null"
        >
          <div 
            v-if="isTimeActive(day.value, hour)"
            class="time-marker"
            @click.stop="removeTime(day.value, hour)"
          >
            ✕
          </div>
        </div>
      </div>
    </div>

    <div class="selected-times">
      <span class="label">已选时间点</span>
      <div v-if="selectedTimes.length > 0" class="time-list">
        <el-tag
          v-for="(time, index) in selectedTimes"
          :key="index"
          closable
          @close="removeTime(time.day, time.hour)"
        >
          {{ time.dayLabel }} {{ time.hour - 1 }}:00
        </el-tag>
      </div>
      <span v-else class="empty-text">暂无选择，点击上方时间格添加</span>
    </div>
  </div>
</template>

<script setup>
import { reactive, computed, watch } from 'vue'

const props = defineProps({
  modelValue: {
    type: Object,
    default: () => ({})
  }
})

const emit = defineEmits(['update:modelValue', 'change'])

const weekDays = [
  { label: '周一', value: 1 },
  { label: '周二', value: 2 },
  { label: '周三', value: 3 },
  { label: '周四', value: 4 },
  { label: '周五', value: 5 },
  { label: '周六', value: 6 },
  { label: '周日', value: 0 },
]

const dayLabels = {
  0: '周日',
  1: '周一',
  2: '周二',
  3: '周三',
  4: '周四',
  5: '周五',
  6: '周六',
}

const config = reactive({
  schedules: props.modelValue.schedules || {},
})

const hoveredCell = reactive({ day: null, hour: null })

watch(() => props.modelValue, (val) => {
  if (val) {
    config.schedules = val.schedules || {}
  }
}, { deep: true })

function isTimeActive(day, hour) {
  const daySchedules = config.schedules[day] || []
  return daySchedules.includes(hour)
}

function isHourActive(hour) {
  return weekDays.some(day => isTimeActive(day.value, hour))
}

function toggleTime(day, hour) {
  if (!config.schedules[day]) {
    config.schedules[day] = []
  }
  const index = config.schedules[day].indexOf(hour)
  if (index === -1) {
    config.schedules[day].push(hour)
    config.schedules[day].sort((a, b) => a - b)
  } else {
    config.schedules[day].splice(index, 1)
  }
  emitChange()
}

function removeTime(day, hour) {
  if (config.schedules[day]) {
    const index = config.schedules[day].indexOf(hour)
    if (index !== -1) {
      config.schedules[day].splice(index, 1)
      if (config.schedules[day].length === 0) {
        delete config.schedules[day]
      }
      emitChange()
    }
  }
}

const selectedTimes = computed(() => {
  const times = []
  Object.keys(config.schedules).forEach(day => {
    config.schedules[day].forEach(hour => {
      times.push({
        day: parseInt(day),
        hour: hour,
        dayLabel: dayLabels[parseInt(day)]
      })
    })
  })
  return times.sort((a, b) => {
    if (a.day !== b.day) return a.day - b.day
    return a.hour - b.hour
  })
})

function emitChange() {
  emit('update:modelValue', {
    schedules: { ...config.schedules },
  })
  emit('change')
}
</script>

<style scoped>
.time-config-advanced {
  padding: 12px;
  max-height: 320px;
  overflow-y: auto;
}

.matrix-container {
  overflow-x: auto;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  margin-bottom: 16px;
  max-height: 240px;
  overflow-y: auto;
}

.time-header {
  display: flex;
  background: #f5f7fa;
  border-bottom: 1px solid #e4e7ed;
}

.day-row {
  display: flex;
  border-bottom: 1px solid #e4e7ed;
}

.day-row:last-child {
  border-bottom: none;
}

.day-label-cell {
  min-width: 60px;
  width: 60px;
  padding: 8px 4px;
  text-align: center;
  font-weight: 500;
  background: #fafafa;
  border-right: 1px solid #e4e7ed;
  font-size: 12px;
  color: #606266;
}

.hour-cell {
  min-width: 48px;
  width: 48px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-right: 1px solid #e4e7ed;
  cursor: pointer;
  font-size: 10px;
  color: #909399;
  transition: all 0.2s;
}

.hour-cell:last-child {
  border-right: none;
}

.hour-cell:hover {
  background: #ecf5ff;
}

.hour-cell.active {
  background: #409eff;
  color: #fff;
}

.hour-cell.hover:not(.active) {
  background: #ecf5ff;
}

.time-marker {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #fff;
  color: #409eff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: bold;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.2s;
}

.hour-cell:hover .time-marker {
  opacity: 1;
}

.selected-times {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.selected-times .label {
  font-weight: 500;
  color: #606266;
}

.time-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.empty-text {
  color: #909399;
  font-size: 13px;
}
</style>
