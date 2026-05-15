<template>
  <div class="space-y-4">
    <input v-model="tpSearch" @input="loadTPs" placeholder="Поиск по номеру ТП..." class="px-3 py-2 border border-slate-300 rounded-lg text-sm w-72 bg-white focus:outline-none focus:border-orange-500 mb-3" />
    <div class="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
      <table class="w-full text-sm">
        <thead class="bg-slate-50 text-slate-600 text-xs uppercase tracking-wide">
          <tr><th class="text-left px-4 py-3 font-medium">Номер ТП</th><th class="text-left px-4 py-3 font-medium">Изделие</th><th class="text-left px-4 py-3 font-medium">Статус</th><th class="text-left px-4 py-3 font-medium">Версия</th><th class="text-left px-4 py-3 font-medium">Вариант</th></tr>
        </thead>
        <tbody>
          <tr v-for="tp in tps" :key="tp.id" @click="loadDetail(tp.id)" class="border-t border-slate-100 hover:bg-slate-50 cursor-pointer">
            <td class="px-4 py-3 font-mono text-xs font-medium">{{ tp.number }}</td><td class="px-4 py-3">{{ tp.product_designation || '-' }}</td>
            <td class="px-4 py-3"><span class="tag" :class="{'Draft':'tag-gray','Approved':'tag-green','Review':'tag-yellow'}[tp.status]||'tag-gray'">{{ tp.status }}</span></td>
            <td class="px-4 py-3 text-slate-600">{{ tp.version || '-' }}</td><td class="px-4 py-3 text-slate-600">{{ tp.execution_variant || '-' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-if="tpDetail" class="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
      <h3 class="font-semibold text-slate-800">{{ tpDetail.number }} — {{ tpDetail.product_designation }} {{ tpDetail.product_name }}</h3>
      <p class="text-sm text-slate-600 mt-1">Статус: {{ tpDetail.status }} | Технология: {{ tpDetail.technology_type }}</p>
      <table class="w-full text-sm mt-3">
        <thead class="bg-slate-50 text-xs uppercase text-slate-600"><tr><th class="text-left px-3 py-2 font-medium">№</th><th class="text-left px-3 py-2 font-medium">Операция</th><th class="text-left px-3 py-2 font-medium">Оборудование</th><th class="text-left px-3 py-2 font-medium">Тпз</th><th class="text-left px-3 py-2 font-medium">Тшт</th><th class="text-left px-3 py-2 font-medium">Цех</th></tr></thead>
        <tbody><tr v-for="op in tpDetail.operations" :key="op.number" class="border-t border-slate-100"><td class="px-3 py-2">{{ op.number }}</td><td class="px-3 py-2">{{ op.name }}</td><td class="px-3 py-2 text-slate-600">{{ op.equipment }}</td><td class="px-3 py-2">{{ op.t_setup }}</td><td class="px-3 py-2">{{ op.t_piece }}</td><td class="px-3 py-2 text-slate-600">{{ op.shop }}</td></tr></tbody>
      </table>
    </div>
  </div>
</template>

<script>
export default {
  name: 'TPsPage',
  props: ['api', 'showError'],
  data() { return { tpSearch: '', tps: [], tpDetail: null } },
  methods: {
    async loadTPs() { try { const d = await this.api('/api/tech-processes?search=' + encodeURIComponent(this.tpSearch) + '&page_size=100'); if (d) this.tps = d.items } catch(e) { this.showError('Не удалось загрузить ТП') } },
    async loadDetail(tpId) { try { this.tpDetail = await this.api('/api/tech-processes/' + tpId) } catch(e) { this.showError('Не удалось загрузить ТП') } },
  },
  async mounted() { this.loadTPs() },
}
</script>
