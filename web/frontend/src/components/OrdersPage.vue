<template>
  <div class="space-y-4">
    <div class="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
      <table class="w-full text-sm">
        <thead class="bg-slate-50 text-slate-600 text-xs uppercase tracking-wide">
          <tr><th class="text-left px-4 py-3 font-medium">Наряд</th><th class="text-left px-4 py-3 font-medium">Изделие</th><th class="text-left px-4 py-3 font-medium">Статус</th><th class="text-left px-4 py-3 font-medium">Кол-во</th><th class="text-left px-4 py-3 font-medium">Выполнено</th><th class="text-left px-4 py-3 font-medium">Срок</th></tr>
        </thead>
        <tbody>
          <tr v-for="wo in orders" :key="wo.id" class="border-t border-slate-100 hover:bg-slate-50">
            <td class="px-4 py-3 font-mono text-xs font-medium">{{ wo.number }}</td>
            <td class="px-4 py-3">{{ wo.product_designation || '-' }}</td>
            <td class="px-4 py-3"><span class="tag tag-yellow">{{ wo.status }}</span></td>
            <td class="px-4 py-3">{{ wo.qty_total }}</td>
            <td class="px-4 py-3">{{ wo.qty_done }}</td>
            <td class="px-4 py-3 text-slate-600">{{ wo.due_date || '-' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
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
