<template>
  <div>
    <div class="card">
      <h3>🧰 Оснастка</h3>
      <input v-model="toolingSearch" placeholder="Поиск по названию или инв. номеру..." @input="loadItems"
             style="padding:8px;width:300px;border:1px solid #ddd;border-radius:4px;margin-bottom:12px">
      <table>
        <thead><tr><th>Инв. №</th><th>Наименование</th><th>Статус</th><th>Износ</th><th>Место</th></tr></thead>
        <tbody>
          <tr v-for="ti in items" :key="ti.id" @click="selectItem(ti)" style="cursor:pointer">
            <td><b>{{ ti.inventory_no }}</b></td><td>{{ ti.name }}</td>
            <td>{{ ti.status }}</td><td>{{ ti.wear_percent }}%</td><td>{{ ti.location }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="card" v-if="selected">
      <h3>История: {{ selected.item.inventory_no }} — {{ selected.item.name }}</h3>
      <table>
        <thead><tr><th>Выдана</th><th>Возвращена</th><th>Кому</th><th>Наряд</th></tr></thead>
        <tbody>
          <tr v-for="iss in selected.issues" :key="iss.id">
            <td>{{ iss.issued_at || '—' }}</td><td>{{ iss.returned_at || '— (на руках)' }}</td>
            <td>{{ iss.issued_to }}</td><td>{{ iss.work_order_id }}</td>
          </tr>
        </tbody>
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
    async loadItems() {
      try { this.items = await this.api('/api/tooling/items?search=' + encodeURIComponent(this.toolingSearch)) || [] } catch(e) {}
    },
    async selectItem(ti) {
      try { this.selected = await this.api('/api/tooling/history/' + ti.id) } catch(e) { this.showError('Не удалось загрузить историю') }
    },
  },
  async mounted() { this.loadItems() },
}
</script>
