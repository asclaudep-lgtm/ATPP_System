<template>
  <div class="space-y-4">
    <div class="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
      <h3 class="font-semibold text-slate-800 mb-3">📋 Журнал изменений</h3>
      <div class="flex gap-2 mb-3">
        <select v-model="filterEntity" @change="loadAudit" class="px-3 py-1.5 border border-slate-300 rounded-lg text-sm bg-white">
          <option value="">Все типы</option><option value="TechProcess">Техпроцессы</option><option value="Product">Изделия</option><option value="WorkOrder">Наряды</option><option value="Operation">Операции</option>
        </select>
        <select v-model="filterAction" @change="loadAudit" class="px-3 py-1.5 border border-slate-300 rounded-lg text-sm bg-white">
          <option value="">Все действия</option><option value="create">Создание</option><option value="update">Изменение</option><option value="delete">Удаление</option><option value="approve">Утверждение</option><option value="batch_approve">Массовое утв.</option>
        </select>
      </div>
      <div class="overflow-hidden">
        <table class="w-full text-sm">
          <thead class="bg-slate-50 text-slate-600 text-xs uppercase tracking-wide">
            <tr><th class="text-left px-4 py-3 font-medium">Время</th><th class="text-left px-4 py-3 font-medium">Пользователь</th><th class="text-left px-4 py-3 font-medium">Тип</th><th class="text-left px-4 py-3 font-medium">Действие</th><th class="text-left px-4 py-3 font-medium">Описание</th><th class="text-left px-4 py-3 font-medium">Изменения</th></tr>
          </thead>
          <tbody>
            <tr v-for="e in entries" :key="e.id" class="border-t border-slate-100 hover:bg-slate-50">
              <td class="px-4 py-3 text-xs whitespace-nowrap">{{ e.timestamp?.slice(0,16) }}</td>
              <td class="px-4 py-3">{{ e.user_name || '-' }}</td>
              <td class="px-4 py-3">{{ e.entity_type }}</td>
              <td class="px-4 py-3"><span class="tag" :class="{'create':'tag-green','delete':'tag-red','approve':'tag-green','batch_approve':'tag-green','batch_assign':'tag-blue'}[e.action]||'tag-gray'">{{ e.action }}</span></td>
              <td class="px-4 py-3 text-xs">{{ e.description }}</td>
              <td class="px-4 py-3"><span v-if="e.changes" class="text-orange-600 text-xs cursor-pointer hover:underline" @click="diffEntry=e">{{ Object.keys(e.changes).length }} пол.</span></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
    <div v-if="diffEntry" class="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
      <h3 class="font-semibold text-slate-800 mb-3">Изменения полей — запись #{{ diffEntry.id }}</h3>
      <table class="w-full text-sm">
        <thead class="bg-slate-50 text-xs uppercase text-slate-600"><tr><th class="text-left px-3 py-2 font-medium">Поле</th><th class="text-left px-3 py-2 font-medium">Было</th><th class="text-left px-3 py-2 font-medium">Стало</th></tr></thead>
        <tbody><tr v-for="(v,k) in diffEntry.changes" :key="k" class="border-t border-slate-100"><td class="px-3 py-2 font-medium">{{ k }}</td><td class="px-3 py-2 text-red-600">{{ v.before }}</td><td class="px-3 py-2 text-emerald-600">{{ v.after }}</td></tr></tbody>
      </table>
    </div>
  </div>
</template>

<script>
export default {
  name: 'AuditPage',
  props: ['api', 'showError'],
  data() { return { entries: [], filterEntity: '', filterAction: '', diffEntry: null } },
  methods: {
    async loadAudit() {
      const p = new URLSearchParams()
      if (this.filterEntity) p.set('entity_type', this.filterEntity)
      if (this.filterAction) p.set('action', this.filterAction)
      p.set('limit', '200')
      try { this.entries = await this.api('/api/audit?' + p) || [] } catch(e) {}
    },
  },
  async mounted() { this.loadAudit() },
}
</script>
