<template>
  <div class="space-y-6">
    <!-- KPI Grid -->
    <div class="grid grid-cols-4 gap-4">
      <div class="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
        <div class="text-xs uppercase text-slate-500 font-medium tracking-wide">Открытые наряды</div>
        <div class="mt-2 flex items-baseline gap-2">
          <div class="text-3xl font-bold text-slate-800">{{ stats.active_work_orders || 0 }}</div>
          <div class="text-sm text-slate-500">активных</div>
        </div>
      </div>
      <div class="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
        <div class="text-xs uppercase text-slate-500 font-medium tracking-wide">Всего изделий</div>
        <div class="mt-2 flex items-baseline gap-2">
          <div class="text-3xl font-bold text-slate-800">{{ stats.total_products || 0 }}</div>
          <div class="text-sm text-slate-500">позиций</div>
        </div>
      </div>
      <div class="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
        <div class="text-xs uppercase text-slate-500 font-medium tracking-wide">Заказов ПДО</div>
        <div class="mt-2 flex items-baseline gap-2">
          <div class="text-3xl font-bold text-slate-800">{{ stats.pdo_total || 0 }}</div>
          <div class="text-sm" :class="(stats.pdo_overdue||0)>0?'text-red-600':'text-green-600'">
            {{ stats.pdo_overdue || 0 }} просрочено
          </div>
        </div>
      </div>
      <div class="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
        <div class="text-xs uppercase text-slate-500 font-medium tracking-wide">Техпроцессов</div>
        <div class="mt-2 flex items-baseline gap-2">
          <div class="text-3xl font-bold text-slate-800">{{ stats.total_tech_processes || 0 }}</div>
          <div class="text-sm text-slate-500">единиц</div>
        </div>
      </div>
    </div>

    <!-- Workshop filter -->
    <div class="flex items-center gap-3">
      <span class="text-sm font-medium text-slate-600">🔧 Цех:</span>
      <select v-model="workshop" @change="loadAll" class="px-3 py-1.5 border border-slate-300 rounded-lg text-sm bg-white">
        <option value="">Все цеха</option>
        <option v-for="w in workshops" :key="w.code" :value="w.code">{{ w.name }}</option>
      </select>
      <button @click="printPDF" class="ml-auto inline-flex items-center gap-1 px-4 py-2 bg-orange-500 hover:bg-orange-600 text-white rounded-lg text-sm font-medium transition-colors">📄 PDF</button>
    </div>

    <!-- Live KPI -->
    <div v-if="liveStats" class="bg-emerald-50 border border-emerald-200 rounded-xl p-4 text-sm">
      <div class="flex gap-6 flex-wrap">
        <div><b>{{ liveStats.products }}</b> изделий</div>
        <div><b>{{ liveStats.tech_processes }}</b> ТП</div>
        <div><b>{{ liveStats.active_orders }}</b> в работе</div>
        <div><b>{{ liveStats.scrap_today }}</b> брак сегодня</div>
        <div class="text-emerald-700">● {{ liveStats.health }}</div>
      </div>
    </div>

    <!-- Charts -->
    <div class="grid grid-cols-2 gap-4">
      <div v-if="equipLoad.length" class="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
        <h3 class="font-semibold mb-3 text-slate-800">Загрузка оборудования</h3>
        <div class="h-72" ref="equipChartEl"></div>
      </div>
      <div v-if="scrapData.length" class="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
        <h3 class="font-semibold mb-3 text-slate-800">Брак по месяцам</h3>
        <div class="h-72" ref="scrapChartEl"></div>
      </div>
    </div>

    <div v-if="prodRate.length" class="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
      <h3 class="font-semibold mb-3 text-slate-800">Выработка по дням</h3>
      <div class="h-72" ref="prodRateChartEl"></div>
    </div>
  </div>
</template>

<script>
import * as echarts from 'echarts'

export default {
  name: 'DashboardPage',
  props: ['api', 'showError'],
  data() { return { stats: {}, equipLoad: [], liveStats: null, workshops: [], workshop: '', scrapData: [], prodRate: [] } },
  methods: {
    params() { return this.workshop ? '?workshop=' + this.workshop : '' },
    renderChart(refName, option) {
      const el = this.$refs[refName]
      if (!el) return
      const chart = echarts.init(el)
      chart.setOption(option)
    },
    renderEquipChart() {
      this.renderChart('equipChartEl', {
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'category', data: this.equipLoad.map(e => e.name) },
        yAxis: { type: 'value', name: 'Загрузка %' },
        series: [{ data: this.equipLoad.map(e => e.capacity_pct), type: 'bar', itemStyle: { color: '#f97316' } }]
      })
    },
    renderScrapChart() {
      this.renderChart('scrapChartEl', {
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'category', data: this.scrapData.map(d => d.month) },
        yAxis: { type: 'value', name: 'Брак (шт.)' },
        series: [{ data: this.scrapData.map(d => d.count), type: 'line', itemStyle: { color: '#ef4444' }, areaStyle: { color: 'rgba(239,68,68,0.1)' } }]
      })
    },
    renderProdRateChart() {
      this.renderChart('prodRateChartEl', {
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'category', data: this.prodRate.map(d => d.date), axisLabel: { rotate: 45, fontSize: 10 } },
        yAxis: { type: 'value', name: 'Операций' },
        dataZoom: [{ type: 'slider', start: 50, end: 100 }],
        series: [{ data: this.prodRate.map(d => d.count), type: 'bar', itemStyle: { color: '#22c55e' } }]
      })
    },
    connectKPI() {
      const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
      const ws = new WebSocket(proto + '//' + location.host + '/ws/kpi')
      this._kpiWs = ws
      ws.onmessage = (evt) => { const msg = JSON.parse(evt.data); if (msg.type === 'kpi') this.liveStats = msg.data }
      ws.onclose = () => { setTimeout(() => this.connectKPI(), 5000) }
    },
    async loadAll() {
      const p = this.params()
      try {
        this.stats = await this.api('/api/dashboard/stats' + p)
        this.equipLoad = (await this.api('/api/production/equipment-load' + p))?.rows || []
        this.scrapData = (await this.api('/api/dashboard/scrap-by-month' + p))?.months || []
        this.prodRate = (await this.api('/api/dashboard/production-rate' + p))?.days || []
        this.$nextTick(() => { this.renderEquipChart(); this.renderScrapChart(); this.renderProdRateChart() })
      } catch(e) {}
    },
    printPDF() { window.print() },
  },
  async mounted() {
    try { this.workshops = await this.api('/api/products/workshops') || [] } catch(e) {}
    this.loadAll()
    this.connectKPI()
  },
  beforeUnmount() { if (this._kpiWs) this._kpiWs.close() },
}
</script>
