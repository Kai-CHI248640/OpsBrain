<template>
  <div class="base-table">
    <el-table
      :data="data"
      :loading="loading"
      :stripe="stripe"
      :border="border"
      :max-height="maxHeight"
      :size="size"
      @sort-change="handleSortChange"
      v-bind="$attrs"
    >
      <slot />
    </el-table>

    <el-pagination
      v-if="pagination"
      :total="total"
      :page-size="pageSize"
      :current-page="currentPage"
      :page-sizes="pageSizes"
      layout="total, sizes, prev, pager, next, jumper"
      @size-change="handleSizeChange"
      @current-change="handleCurrentChange"
      style="margin-top: 16px; text-align: right"
    />
  </div>
</template>

<script setup>
import { defineProps, defineEmits } from 'vue'

defineProps({
  data: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  stripe: { type: Boolean, default: true },
  border: { type: Boolean, default: false },
  maxHeight: { type: Number, default: 500 },
  size: { type: String, default: 'default' },
  pagination: { type: Boolean, default: false },
  total: { type: Number, default: 0 },
  pageSize: { type: Number, default: 10 },
  currentPage: { type: Number, default: 1 },
  pageSizes: { type: Array, default: () => [10, 20, 50, 100] },
})

const emit = defineEmits(['sort-change', 'size-change', 'current-change'])

function handleSortChange({ prop, order }) {
  emit('sort-change', { prop, order })
}

function handleSizeChange(val) {
  emit('size-change', val)
}

function handleCurrentChange(val) {
  emit('current-change', val)
}
</script>

<style scoped>
.base-table {
  width: 100%;
}
</style>