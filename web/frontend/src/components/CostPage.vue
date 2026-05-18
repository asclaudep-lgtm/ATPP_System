<template>
  <div class="p-6">
    <h2 class="text-xl font-semibold text-slate-900 mb-4">Расчёт себестоимости</h2>
    <div class="bg-white rounded-xl border border-slate-200 p-4">
      <div class="grid grid-cols-2 gap-4 mb-4">
        <div>
          <label class="block text-sm text-slate-600 mb-1">Изделие</label>
          <select v-model="productId" @change="loadCost" class="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm">
            <option :value="null">— выберите —</option>
            <option v-for="p in products" :key="p.id" :value="p.id">{{ p.designation }} - {{ p.name }}</option>
          </select>
        </div>
      </div>

      <div v-if="costData" class="space-y-3">
        <div class="grid grid-cols-2 gap-3">
          <div class="p-3 bg-blue-50 rounded-lg"><div class="text-xs text-blue-600">Материалы</div><div class="text-lg font-semibold">{{ costData.material_cost || 0 }} ₽</div></div>
          <div class="p-3 bg-green-50 rounded-lg"><div class="text-xs text-green-600">Зарплата</div><div class="text-lg font-semibold">{{ costData.labor_cost || 0 }} ₽</div></div>
          <div class="p-3 bg-amber-50 rounded-lg"><div class="text-xs text-amber-600">Оборудование</div><div class="text-lg font-semibold">{{ costData.equipment_cost || 0 }} ₽</div></div>
          <div class="p-3 bg-purple-50 rounded-lg"><div class="text-xs text-purple-600">Накладные</div><div class="text-lg font-semibold">{{ costData.shop_overhead || 0 }} ₽</div></div>
        </div>
        <div class="p-4 bg-slate-900 text-white rounded-xl text-center">
          <div class="text-sm text-slate-300">Полная себестоимость</div>
          <div class="text-2xl font-bold">{{ costData.full_cost || costData.production_cost || 0 }} ₽</div>
        </div>
      </div>
      <div v-else class="text-sm text-slate-400">Выберите изделие для расчёта себестоимости</div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'CostPage',
  props: { api: Function, showError: Function },
  data() { return { products: [], productId: null, costData: null } },
  async mounted() {
    const d = await this.api('/api/products?page_size=200')
    if (d) this.products = d.items || []
  },
  methods: {
    async loadCost() {
      this.costData = null
      if (!this.productId) return
      try {
        const d = await this.api(`/api/products/${this.productId}`)
        if (d) this.costData = d
      } catch (e) { this.showError('Ошибка загрузки: ' + e.message) }
    },
  },
}
</script>
