<template>
  <div class="space-y-4 max-w-4xl">
    <div class="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
      <h3 class="font-semibold text-slate-800 mb-3">✅ Массовое утверждение ТП</h3>
      <p class="text-sm text-slate-500 mb-3">Выберите техпроцессы для утверждения</p>
      <div class="overflow-hidden">
        <table class="w-full text-sm">
          <thead class="bg-slate-50 text-slate-600 text-xs uppercase tracking-wide">
            <tr><th class="text-left px-4 py-3 font-medium w-10"><input type="checkbox" @change="toggleAllTPs" v-model="allTPsChecked"></th><th class="text-left px-4 py-3 font-medium">Номер ТП</th><th class="text-left px-4 py-3 font-medium">Изделие</th><th class="text-left px-4 py-3 font-medium">Статус</th></tr>
          </thead>
          <tbody>
            <tr v-for="tp in tps" :key="tp.id" class="border-t border-slate-100 hover:bg-slate-50"><td class="px-4 py-3"><input type="checkbox" :value="tp.id" v-model="selectedTPs"></td><td class="px-4 py-3 font-mono text-xs font-medium">{{ tp.number }}</td><td class="px-4 py-3">{{ tp.product_designation || '-' }}</td><td class="px-4 py-3"><span class="tag tag-gray">{{ tp.status }}</span></td></tr>
          </tbody>
        </table>
      </div>
      <button @click="approveTPs" :disabled="!selectedTPs.length" class="mt-3 px-5 py-2 bg-orange-500 hover:bg-orange-600 text-white rounded-lg text-sm font-medium transition-colors disabled:opacity-40">Утвердить выбранные ({{ selectedTPs.length }})</button>
      <span v-if="tpResult" class="ml-3 text-sm text-slate-600">{{ tpResult }}</span>
    </div>

    <div class="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
      <h3 class="font-semibold text-slate-800 mb-3">🏭 Массовое назначение нарядов в цех</h3>
      <select v-model="targetWorkshop" class="px-3 py-1.5 border border-slate-300 rounded-lg text-sm bg-white mb-3 w-64">
        <option value="">-- Выберите цех --</option>
        <option v-for="w in workshops" :key="w.id" :value="w.id">{{ w.name }}</option>
      </select>
      <div class="overflow-hidden">
        <table class="w-full text-sm">
          <thead class="bg-slate-50 text-slate-600 text-xs uppercase tracking-wide">
            <tr><th class="text-left px-4 py-3 font-medium w-10"><input type="checkbox" @change="toggleAllWOs" v-model="allWOsChecked"></th><th class="text-left px-4 py-3 font-medium">Наряд</th><th class="text-left px-4 py-3 font-medium">Изделие</th><th class="text-left px-4 py-3 font-medium">Статус</th></tr>
          </thead>
          <tbody>
            <tr v-for="wo in workOrders" :key="wo.id" class="border-t border-slate-100 hover:bg-slate-50"><td class="px-4 py-3"><input type="checkbox" :value="wo.id" v-model="selectedWOs"></td><td class="px-4 py-3 font-mono text-xs font-medium">{{ wo.number }}</td><td class="px-4 py-3">{{ wo.product_designation || '-' }}</td><td class="px-4 py-3"><span class="tag tag-yellow">{{ wo.status }}</span></td></tr>
          </tbody>
        </table>
      </div>
      <button @click="assignWOs" :disabled="!selectedWOs.length || !targetWorkshop" class="mt-3 px-5 py-2 bg-orange-500 hover:bg-orange-600 text-white rounded-lg text-sm font-medium transition-colors disabled:opacity-40">Назначить в цех ({{ selectedWOs.length }})</button>
      <span v-if="woResult" class="ml-3 text-sm text-slate-600">{{ woResult }}</span>
    </div>
  </div>
</template>

<script>
export default {
  name: 'BatchOpsPage',
  props: ['api', 'showError'],
  data() { return { tps: [], workOrders: [], workshops: [], selectedTPs: [], selectedWOs: [], allTPsChecked: false, allWOsChecked: false, targetWorkshop: '', tpResult: '', woResult: '' } },
  methods: {
    async loadData() {
      try {
        const tpData = await this.api('/api/tech-processes?page_size=200'); if (tpData) this.tps = tpData.items.filter(t => t.status === 'Draft' || t.status === 'Review' || t.status === 'Черновик' || t.status === 'На согласовании')
        const woData = await this.api('/api/work-orders?page_size=200'); if (woData) this.workOrders = woData.items.filter(w => w.status !== 'Завершён' && w.status !== 'Отменён')
        this.workshops = await this.api('/api/products/workshops') || []
      } catch(e) {}
    },
    toggleAllTPs() { this.selectedTPs = this.allTPsChecked ? this.tps.map(t => t.id) : [] },
    toggleAllWOs() { this.selectedWOs = this.allWOsChecked ? this.workOrders.map(w => w.id) : [] },
    async approveTPs() {
      this.tpResult = ''; try { const r = await this.api('/api/batch/approve-tps', { method:'POST', body:JSON.stringify({ tp_ids:this.selectedTPs, comment:'Массовое утверждение' }) }); const ok = r.results.filter(x => x.status==='approved').length; this.tpResult = `Утверждено: ${ok}/${r.total}`; if (ok>0) this.loadData() } catch(e) { this.tpResult = 'Ошибка' }
    },
    async assignWOs() {
      this.woResult = ''; try { const r = await this.api('/api/batch/assign-work-orders', { method:'POST', body:JSON.stringify({ wo_ids:this.selectedWOs, workshop_id:this.targetWorkshop }) }); const ok = r.results.filter(x => x.status==='assigned').length; this.woResult = `Назначено: ${ok}/${r.total}`; if (ok>0) this.loadData() } catch(e) { this.woResult = 'Ошибка' }
    },
  },
  async mounted() { this.loadData() },
}
</script>
