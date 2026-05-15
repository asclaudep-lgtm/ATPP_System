<template>
  <div class="card">
    <table>
      <thead><tr><th>Наряд</th><th>Изделие</th><th>Статус</th><th>Кол-во</th><th>Выполнено</th><th>Срок</th></tr></thead>
      <tbody>
        <tr v-for="wo in orders" :key="wo.id">
          <td><b>{{ wo.number }}</b></td><td>{{ wo.product_designation || '—' }}</td>
          <td><span class="status status-in-progress">{{ wo.status }}</span></td>
          <td>{{ wo.qty_total }}</td><td>{{ wo.qty_done }}</td><td>{{ wo.due_date || '—' }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script>
export default {
  name: 'OrdersPage',
  props: ['api', 'showError'],
  data() { return { orders: [] } },
  async mounted() {
    try { const d = await this.api('/api/work-orders?page_size=100'); if (d) this.orders = d.items } catch(e) {}
  },
}
</script>
