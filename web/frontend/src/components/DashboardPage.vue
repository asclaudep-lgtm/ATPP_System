<template>
  <div>
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
      <div style="display:flex;gap:24px;margin-top:8px">
        <div><b>{{ liveStats.products }}</b> изделий</div>
        <div><b>{{ liveStats.tech_processes }}</b> ТП</div>
        <div><b>{{ liveStats.active_orders }}</b> нарядов в работе</div>
        <div><b>{{ liveStats.scrap_today }}</b> брак сегодня</div>
        <div style="color:#27ae60">● {{ liveStats.health }}</div>
      </div>
    </div>
    <div class="card" v-if="equipLoad.length">
      <h3>Загрузка оборудования</h3>
      <div class="chart-box" ref="chartEl"></div>
    </div>
  </div>
</template>

<script>
import * as echarts from 'echarts'

export default {
  name: 'DashboardPage',
  props: ['api', 'showError'],
  data() { return { stats: {}, equipLoad: [], liveStats: null } },
  methods: {
    renderEquipChart() {
      const el = this.$refs.chartEl
      if (!el || !this.equipLoad.length) return
      const chart = echarts.init(el)
      chart.setOption({
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'category', data: this.equipLoad.map(e => e.name) },
        yAxis: { type: 'value', name: 'Загрузка %' },
        series: [{ data: this.equipLoad.map(e => e.capacity_pct), type: 'bar', itemStyle: { color: '#1976d2' } }]
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
  },
  async mounted() {
    try {
      this.stats = await this.api('/api/dashboard/stats')
      this.equipLoad = await this.api('/api/production/equipment-load')
      this.$nextTick(() => this.renderEquipChart())
    } catch(e) { /* silently ignore */ }
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
</style>
