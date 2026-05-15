<template>
  <div class="space-y-4">
    <div class="flex gap-2 items-center">
      <input v-model="toolingSearch" @input="loadItems" placeholder="Поиск по названию или инв. номеру..." class="px-3 py-2 border border-slate-300 rounded-lg text-sm w-72 bg-white focus:outline-none focus:border-orange-500" />
    </div>
    <div class="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
      <table class="w-full text-sm">
        <thead class="bg-slate-50 text-slate-600 text-xs uppercase tracking-wide">
          <tr><th class="text-left px-4 py-3 font-medium">Инв. №</th><th class="text-left px-4 py-3 font-medium">Наименование</th><th class="text-left px-4 py-3 font-medium">Статус</th><th class="text-left px-4 py-3 font-medium">Износ</th><th class="text-left px-4 py-3 font-medium">Место</th></tr>
        </thead>
        <tbody>
          <tr v-for="ti in items" :key="ti.id" @click="selectItem(ti)" class="border-t border-slate-100 hover:bg-slate-50 cursor-pointer">
            <td class="px-4 py-3 font-mono text-xs font-medium">{{ ti.inventory_no }}</td>
            <td class="px-4 py-3">{{ ti.name }}</td>
            <td class="px-4 py-3">{{ ti.status }}</td>
            <td class="px-4 py-3">{{ ti.wear_percent }}%</td>
            <td class="px-4 py-3 text-slate-600">{{ ti.location }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-if="selected" class="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
      <h3 class="font-semibold text-slate-800 mb-3">{{ selected.item.inventory_no }} — {{ selected.item.name }}</h3>
      <table class="w-full text-sm">
        <thead class="bg-slate-50 text-xs uppercase text-slate-600"><tr><th class="text-left px-3 py-2 font-medium">Выдана</th><th class="text-left px-3 py-2 font-medium">Возвращена</th><th class="text-left px-3 py-2 font-medium">Кому</th><th class="text-left px-3 py-2 font-medium">Наряд</th></tr></thead>
        <tbody><tr v-for="iss in selected.issues" :key="iss.id" class="border-t border-slate-100"><td class="px-3 py-2 text-slate-600">{{ iss.issued_at || '-' }}</td><td class="px-3 py-2 text-slate-600">{{ iss.returned_at || '— (на руках)' }}</td><td class="px-3 py-2">{{ iss.issued_to }}</td><td class="px-3 py-2 font-mono text-xs">{{ iss.work_order_id }}</td></tr></tbody>
      </table>
    </div>
  </div>
</template>

<script>
export default {
  name: 'ToolingPage',
  props: ['api', 'showError'],
  data() { return { toolingSearch: '', items: [], selected: null } },
  methods: {
    async loadItems() { try { this.items = await this.api('/api/tooling/items?search=' + encodeURIComponent(this.toolingSearch)) || [] } catch(e) {} },
    async selectItem(ti) { try { this.selected = await this.api('/api/tooling/history/' + ti.id) } catch(e) { this.showError('Не удалось загрузить историю') } },
  },
  async mounted() { this.loadItems() },
}
</script>
