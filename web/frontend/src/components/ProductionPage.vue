<template>
  <div>
    <div class="card">
      <h3>🔎 Сканер штрих-кода / поиск наряда</h3>
      <div class="scanner-area">
        <input class="barcode-input" v-model="barcode" placeholder="Отсканируйте штрих-код или введите номер наряда..."
               @keyup.enter="lookupBarcode" autofocus>
        <button @click="lookupBarcode" style="padding:8px 24px;cursor:pointer;background:#1976d2;color:#fff;border:none;border-radius:4px">Найти</button>
      </div>
    </div>
    <div class="card" v-if="routeSlip">
      <h3>Маршрутный лист: {{ routeSlip.work_order.number }}</h3>
      <p>{{ routeSlip.work_order.product_designation }} — {{ routeSlip.work_order.product_name }} |
         Статус: {{ routeSlip.work_order.status }} |
         Выполнено: {{ routeSlip.work_order.qty_done }}/{{ routeSlip.work_order.qty_total }}</p>
      <div v-for="s in routeSlip.steps" :key="s.id" :class="'route-step ' + (s.status==='Выполнен'?'done':(s.status==='В работе'?'active':''))">
        <span><b>{{ s.operation }}</b> — {{ s.workshop }}</span>
        <span style="font-size:12px;color:#666">{{ s.status }}</span>
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
        if (result.type === 'work_order') {
          this.routeSlip = await this.api('/api/production/route/' + result.id)
        }
      } catch(e) { this.showError('Наряд/партия не найден: ' + code) }
    },
  },
}
</script>

<style scoped>
.scanner-area { border:2px dashed #bdc3c7; border-radius:8px; padding:24px; text-align:center; color:#999; margin-bottom:16px }
.barcode-input { font-size:24px; padding:12px; width:100%; border:2px solid #1976d2; border-radius:8px; text-align:center; letter-spacing:2px; margin-bottom:16px }
.route-step { padding:8px 12px; margin:4px 0; background:#f8f9fa; border-radius:4px; display:flex; justify-content:space-between; align-items:center }
.route-step.active { background:#d4edda; border-left:4px solid #27ae60 }
.route-step.done { background:#e8f5e9; color:#666 }
</style>
