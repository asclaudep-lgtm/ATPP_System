<template>
  <div>
    <div style="display:flex;gap:12px;align-items:center;margin-bottom:12px">
      <span style="font-weight:600">🔧 Цех:</span>
      <select v-model="workshop" @change="loadAll" style="padding:6px;width:200px">
        <option value="">Все цеха</option>
        <option v-for="w in workshops" :key="w.code" :value="w.code">{{ w.name }}</option>
      </select>
      <button @click="printPDF" style="margin-left:auto;padding:6px 16px;cursor:pointer;background:#1976d2;color:#fff;border:none;border-radius:4px">📄 PDF</button>
    </div>

    <div class="stats">
      <div class="stat"><div class="num">{{ stats.total_products }}</div><div class="lbl">Изделий</div></div>
      <div class="stat"><div class="num">{{ stats.total_tech_processes }}</div><div class="lbl">Техпроцессов</div></div>
      <div class="stat"><div class="num">{{ stats.total_work_orders }}</div><div class="lbl">Нарядов</div></div>
      <div class="stat"><div class="num">{{ stats.active_work_orders }}</div><div class="lbl">В работе</div></div>
      <div class="stat"><div class="num">{{ stats.total_users }}</div><div class="lbl">Пользователей</div></div>
      <div class="stat"><div class="num">{{ stats.pdo_total || 0 }}</div><div class="lbl">Заказов ПДО</div></div>
      <div class="stat" :style="{background: (stats.pdo_overdue||0)>0?'linear-gradient(135deg,#d32f2f,#c0392b)':''}">
        <div class="num">{{ stats.pdo_overdue || 0 }}</div><div class="lbl">Просрочено</div>
      </div>
    </div>

    <div class="card" v-if="liveStats" style="background:#e8f5e9">
      <h3>🔴 Live KPI</h3>
      <div style="display:flex;gap:24px;margin-top:8px;flex-wrap:wrap">
        <div><b>{{ liveStats.products }}</b> изделий</div>
        <div><b>{{ liveStats.tech_processes }}</b> ТП</div>
        <div><b>{{ liveStats.active_orders }}</b> нарядов в работе</div>
        <div><b>{{ liveStats.scrap_today }}</b> брак сегодня</div>
        <div style="color:#27ae60">● {{ liveStats.health }}</div>
      </div>
    </div>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
      <div class="card" v-if="equipLoad.length">
        <h3>Загрузка оборудования</h3>
        <div class="chart-box" ref="equipChartEl"></div>
      </div>
      <div class="card" v-if="scrapData.length">
        <h3>Брак по месяцам</h3>
        <div class="chart-box" ref="scrapChartEl"></div>
      </div>
    </div>

    <div class="card" v-if="prodRate.length">
      <h3>Выработка по дням</h3>
      <div class="chart-box" ref="prodRateChartEl"></div>
    </div>
  </div>
</template>

<script>
import * as echarts from 'echarts'

export default {
  name: 'DashboardPage',
  props: ['api', 'showError'],
  data() { return {
    stats: {}, equipLoad: [], liveStats: null, workshops: [],
    workshop: '', scrapData: [], prodRate: [],
  }},
  methods: {
    params() { return this.workshop ? '?workshop=' + this.workshop : '' },

    renderEquipChart() {
      const el = this.$refs.equipChartEl
      if (!el || !this.equipLoad.length) return
      const chart = echarts.init(el)
      chart.setOption({
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'category', data: this.equipLoad.map(e => e.name) },
        yAxis: { type: 'value', name: 'Загрузка %' },
        series: [{ data: this.equipLoad.map(e => e.capacity_pct), type: 'bar', itemStyle: { color: '#1976d2' } }]
      })
    },
    renderScrapChart() {
      const el = this.$refs.scrapChartEl
      if (!el || !this.scrapData.length) return
      const chart = echarts.init(el)
      chart.setOption({
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'category', data: this.scrapData.map(d => d.month) },
        yAxis: { type: 'value', name: 'Брак (шт.)' },
        series: [{ data: this.scrapData.map(d => d.count), type: 'line', itemStyle: { color: '#d32f2f' }, areaStyle: { color: 'rgba(211,47,47,0.1)' } }]
      })
    },
    renderProdRateChart() {
      const el = this.$refs.prodRateChartEl
      if (!el || !this.prodRate.length) return
      const chart = echarts.init(el)
      chart.setOption({
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'category', data: this.prodRate.map(d => d.date), axisLabel: { rotate: 45, fontSize: 10 } },
        yAxis: { type: 'value', name: 'Операций' },
        dataZoom: [{ type: 'slider', start: 50, end: 100 }],
        series: [{ data: this.prodRate.map(d => d.count), type: 'bar', itemStyle: { color: '#27ae60' } }]
      })
    },
    connectKPI() {
      const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
      const ws = new WebSocket(proto + '//' + location.host + '/ws/kpi')
      this._kpiWs = ws
      ws.onmessage = (evt) => {
        const msg = JSON.parse(evt.data)
        if (msg.type === 'kpi') this.liveStats = msg.data
      }
      ws.onclose = () => { setTimeout(() => this.connectKPI(), 5000) }
    },
    printPDF() { window.print() },
    async loadAll() {
      const p = this.params()
      try {
        this.stats = await this.api('/api/dashboard/stats' + p)
        this.equipLoad = (await this.api('/api/production/equipment-load' + p))?.rows || []
        this.scrapData = (await this.api('/api/dashboard/scrap-by-month' + p))?.months || []
        this.prodRate = (await this.api('/api/dashboard/production-rate' + p))?.days || []
        this.$nextTick(() => {
          this.renderEquipChart()
          this.renderScrapChart()
          this.renderProdRateChart()
        })
      } catch(e) {}
    },
  },
  async mounted() {
    try { this.workshops = await this.api('/api/products/workshops') || [] } catch(e) {}
    this.loadAll()
    this.connectKPI()
  },
  beforeUnmount() {
    if (this._kpiWs) this._kpiWs.close()
  },
}
</script>

<style scoped>
.stats { display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:12px }
.stat { padding:16px; text-align:center; border-radius:8px; background:linear-gradient(135deg,#667eea,#764ba2); color:#fff }
.stat .num { font-size:28px; font-weight:bold }
.stat .lbl { font-size:12px; opacity:.85; margin-top:4px }
.chart-box { width:100%; height:280px; margin-top:12px }
@media print {
  body * { visibility: hidden }
  #app-root, #app-root * { visibility: visible }
  #app-root { position: absolute; left:0; top:0; width:100% }
  .header, .nav, button { display: none !important }
}
</style>
