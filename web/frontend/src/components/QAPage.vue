<template>
  <div class="grid grid-cols-2 gap-4">
    <div class="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
      <h3 class="font-semibold text-slate-800 mb-3">🔍 Ожидают контроля ОТК</h3>
      <table v-if="qaPending.length" class="w-full text-sm">
        <thead class="bg-slate-50 text-xs uppercase text-slate-600"><tr><th class="text-left px-3 py-2 font-medium">Операция</th><th class="text-left px-3 py-2 font-medium">Участок</th><th class="text-left px-3 py-2 font-medium">Завершена</th></tr></thead>
        <tbody><tr v-for="s in qaPending" :key="s.id" class="border-t border-slate-100"><td class="px-3 py-2">{{ s.operation }}</td><td class="px-3 py-2">{{ s.workshop }}</td><td class="px-3 py-2 text-slate-500">{{ s.actual_end || '-' }}</td></tr></tbody>
      </table>
      <p v-else class="text-slate-400 text-center py-8">Нет операций, ожидающих ОТК.</p>
    </div>
    <div class="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
      <h3 class="font-semibold text-slate-800 mb-3">Последние проблемы</h3>
      <table v-if="issues.length" class="w-full text-sm">
        <thead class="bg-slate-50 text-xs uppercase text-slate-600"><tr><th class="text-left px-3 py-2 font-medium">Наряд</th><th class="text-left px-3 py-2 font-medium">Проблема</th><th class="text-left px-3 py-2 font-medium">Статус</th></tr></thead>
        <tbody><tr v-for="i in issues" :key="i.id" class="border-t border-slate-100"><td class="px-3 py-2 font-mono text-xs">{{ i.work_order_id }}</td><td class="px-3 py-2">{{ i.title }}</td><td class="px-3 py-2"><span class="tag" :class="i.status==='Решена'?'tag-green':'tag-yellow'">{{ i.status }}</span></td></tr></tbody>
      </table>
      <p v-else class="text-slate-400 text-center py-8">Проблем не зарегистрировано.</p>
    </div>
  </div>
</template>

<script>
export default {
  name: 'QAPage',
  props: ['api', 'showError'],
  data() { return { qaPending: [], issues: [] } },
  async mounted() {
    try { this.qaPending = await this.api('/api/production/qa/pending') || []; this.issues = await this.api('/api/production/issues') || [] } catch(e) {}
  },
}
</script>
