<template>
  <div class="space-y-4 max-w-3xl">
    <div class="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
      <h3 class="font-semibold text-slate-800 mb-3">🔎 Сканер штрих-кода / поиск наряда</h3>
      <div class="border-2 border-dashed border-slate-300 rounded-lg p-6 text-center text-slate-500 mb-4">
        <input class="w-full text-2xl px-4 py-3 border-2 border-orange-300 rounded-lg text-center tracking-wider mb-3 focus:outline-none focus:border-orange-500" v-model="barcode" placeholder="Отсканируйте или введите номер наряда..." @keyup.enter="lookupBarcode" autofocus />
        <button @click="lookupBarcode" class="px-6 py-2 bg-orange-500 hover:bg-orange-600 text-white rounded-lg font-medium text-sm transition-colors">Найти</button>
      </div>
    </div>
    <div v-if="routeSlip" class="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
      <h3 class="font-semibold text-slate-800">{{ routeSlip.work_order.number }}</h3>
      <p class="text-sm text-slate-600 mt-1">{{ routeSlip.work_order.product_designation }} — {{ routeSlip.work_order.product_name }} | Статус: {{ routeSlip.work_order.status }} | {{ routeSlip.work_order.qty_done }}/{{ routeSlip.work_order.qty_total }}</p>
      <div class="space-y-2 mt-4">
        <div v-for="s in routeSlip.steps" :key="s.id" class="p-3 rounded-lg border flex justify-between items-center"
          :class="s.status==='Выполнен'?'bg-emerald-50 border-emerald-200':s.status==='В работе'?'bg-orange-50 border-orange-200':'bg-slate-50 border-slate-200'">
          <span><b>{{ s.operation }}</b> — {{ s.workshop }}</span>
          <span class="text-xs text-slate-600">{{ s.status }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'ProductionPage',
  props: ['api', 'showError'],
  data() { return { barcode: '', routeSlip: null } },
  methods: {
    async lookupBarcode() {
      const code = this.barcode.trim()
      if (!code) return
      try {
        const result = await this.api('/api/production/barcode/' + encodeURIComponent(code))
        if (result.type === 'work_order') this.routeSlip = await this.api('/api/production/route/' + result.id)
      } catch(e) { this.showError('Наряд не найден: ' + code) }
    },
  },
}
</script>
