<template>
  <div>
    <div class="card">
      <input v-model="tpSearch" placeholder="Поиск по номеру ТП..." @input="loadTPs"
             style="padding:8px;width:300px;border:1px solid #ddd;border-radius:4px">
      <table>
        <thead><tr><th>Номер ТП</th><th>Изделие</th><th>Статус</th><th>Версия</th><th>Вариант</th></tr></thead>
        <tbody>
          <tr v-for="tp in tps" :key="tp.id" @click="loadDetail(tp.id)" style="cursor:pointer">
            <td><b>{{ tp.number }}</b></td><td>{{ tp.product_designation || '—' }}</td>
            <td><span :class="'status status-'+tp.status.toLowerCase()">{{ tp.status }}</span></td>
            <td>{{ tp.version || '—' }}</td><td>{{ tp.execution_variant || '—' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="card" v-if="tpDetail">
      <h3>{{ tpDetail.number }} — {{ tpDetail.product_designation }} {{ tpDetail.product_name }}</h3>
      <p>Статус: {{ tpDetail.status }} | Технология: {{ tpDetail.technology_type }}</p>
      <table style="margin-top:8px">
        <thead><tr><th>№</th><th>Операция</th><th>Оборудование</th><th>Тпз</th><th>Тшт</th><th>Цех</th></tr></thead>
        <tbody>
          <tr v-for="op in tpDetail.operations" :key="op.number">
            <td>{{ op.number }}</td><td>{{ op.name }}</td><td>{{ op.equipment }}</td>
            <td>{{ op.t_setup }}</td><td>{{ op.t_piece }}</td><td>{{ op.shop }}</td>
          </tr>
        </tbody>
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
    async loadTPs() {
      try { const d = await this.api('/api/tech-processes?search=' + encodeURIComponent(this.tpSearch) + '&page_size=100')
        if (d) this.tps = d.items } catch(e) { this.showError('Не удалось загрузить техпроцессы') }
    },
    async loadDetail(tpId) {
      try { this.tpDetail = await this.api('/api/tech-processes/' + tpId) } catch(e) { this.showError('Не удалось загрузить ТП') }
    },
  },
  async mounted() { this.loadTPs() },
}
</script>
