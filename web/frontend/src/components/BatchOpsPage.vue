<template>
  <div>
    <div class="card">
      <h3>✅ Массовое утверждение ТП</h3>
      <p style="color:#666;margin-bottom:8px">Выберите техпроцессы для утверждения</p>
      <table>
        <thead><tr><th><input type="checkbox" @change="toggleAllTPs" v-model="allTPsChecked"></th><th>Номер ТП</th><th>Изделие</th><th>Статус</th></tr></thead>
        <tbody>
          <tr v-for="tp in tps" :key="tp.id">
            <td><input type="checkbox" :value="tp.id" v-model="selectedTPs"></td>
            <td><b>{{ tp.number }}</b></td>
            <td>{{ tp.product_designation || '-' }}</td>
            <td><span :class="'status status-'+tp.status.toLowerCase()">{{ tp.status }}</span></td>
          </tr>
        </tbody>
      </table>
      <button @click="approveTPs" :disabled="!selectedTPs.length"
        style="margin-top:12px;padding:8px 24px;background:#27ae60;color:#fff;border:none;border-radius:4px;cursor:pointer">
        Утвердить выбранные ({{ selectedTPs.length }})
      </button>
      <span v-if="tpResult" style="margin-left:12px;font-size:13px">{{ tpResult }}</span>
    </div>

    <div class="card">
      <h3>🏭 Массовое назначение нарядов в цех</h3>
      <select v-model="targetWorkshop" style="padding:6px;margin-bottom:8px;width:250px">
        <option value="">-- Выберите цех --</option>
        <option v-for="w in workshops" :key="w.id" :value="w.id">{{ w.name }}</option>
      </select>
      <table>
        <thead><tr><th><input type="checkbox" @change="toggleAllWOs" v-model="allWOsChecked"></th><th>Наряд</th><th>Изделие</th><th>Статус</th></tr></thead>
        <tbody>
          <tr v-for="wo in workOrders" :key="wo.id">
            <td><input type="checkbox" :value="wo.id" v-model="selectedWOs"></td>
            <td><b>{{ wo.number }}</b></td>
            <td>{{ wo.product_designation || '-' }}</td>
            <td><span class="status status-in-progress">{{ wo.status }}</span></td>
          </tr>
        </tbody>
      </table>
      <button @click="assignWOs" :disabled="!selectedWOs.length || !targetWorkshop"
        style="margin-top:12px;padding:8px 24px;background:#1976d2;color:#fff;border:none;border-radius:4px;cursor:pointer">
        Назначить в цех ({{ selectedWOs.length }})
      </button>
      <span v-if="woResult" style="margin-left:12px;font-size:13px">{{ woResult }}</span>
    </div>
  </div>
</template>

<script>
export default {
  name: 'BatchOpsPage',
  props: ['api', 'showError'],
  data() { return {
    tps: [], workOrders: [], workshops: [],
    selectedTPs: [], selectedWOs: [], allTPsChecked: false, allWOsChecked: false,
    targetWorkshop: '', tpResult: '', woResult: '',
  }},
  methods: {
    async loadData() {
      try {
        const tpData = await this.api('/api/tech-processes?page_size=200')
        if (tpData) this.tps = tpData.items.filter(t => t.status === 'Draft' || t.status === 'Review')
        const woData = await this.api('/api/work-orders?page_size=200')
        if (woData) this.workOrders = woData.items.filter(w => w.status !== 'Завершён' && w.status !== 'Отменён')
        this.workshops = await this.api('/api/products/workshops') || []
      } catch(e) {}
    },
    toggleAllTPs() { this.selectedTPs = this.allTPsChecked ? this.tps.map(t => t.id) : [] },
    toggleAllWOs() { this.selectedWOs = this.allWOsChecked ? this.workOrders.map(w => w.id) : [] },
    async approveTPs() {
      this.tpResult = ''
      try {
        const r = await this.api('/api/batch/approve-tps', {
          method: 'POST', body: JSON.stringify({ tp_ids: this.selectedTPs, comment: 'Массовое утверждение' })
        })
        const ok = r.results.filter(x => x.status === 'approved').length
        this.tpResult = `Утверждено: ${ok}/${r.total}`
        if (ok > 0) this.loadData()
      } catch(e) { this.tpResult = 'Ошибка: ' + e }
    },
    async assignWOs() {
      this.woResult = ''
      try {
        const r = await this.api('/api/batch/assign-work-orders', {
          method: 'POST', body: JSON.stringify({ wo_ids: this.selectedWOs, workshop_id: this.targetWorkshop })
        })
        const ok = r.results.filter(x => x.status === 'assigned').length
        this.woResult = `Назначено: ${ok}/${r.total}`
        if (ok > 0) this.loadData()
      } catch(e) { this.woResult = 'Ошибка: ' + e }
    },
  },
  async mounted() { this.loadData() },
}
</script>
