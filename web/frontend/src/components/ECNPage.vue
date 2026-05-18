<template>
  <div class="p-6">
    <h2 class="text-xl font-semibold text-slate-900 mb-4">ECN — Извещения об изменениях</h2>
    <div class="bg-white rounded-xl border border-slate-200 p-4">
      <p class="text-sm text-slate-500 mb-4">Управление изменениями конструкторско-технологической документации</p>

      <div class="grid grid-cols-2 gap-3 mb-4 p-3 bg-slate-50 rounded-lg">
        <select v-model="ecn.productId" class="px-2 py-1.5 border rounded text-sm">
          <option :value="null">— изделие —</option>
          <option v-for="p in products" :key="p.id" :value="p.id">{{ p.designation }}</option>
        </select>
        <select v-model="ecn.priority" class="px-2 py-1.5 border rounded text-sm">
          <option :value="1">Низкий приоритет</option>
          <option :value="3">Средний</option>
          <option :value="5">Высокий</option>
        </select>
        <textarea v-model="ecn.description" placeholder="Описание изменения..." class="col-span-2 px-2 py-1.5 border rounded text-sm" rows="2"></textarea>
        <button @click="createECN" class="px-4 py-1.5 bg-orange-500 hover:bg-orange-600 text-white rounded-lg text-sm col-span-2">Создать ECN</button>
      </div>

      <div v-if="ecnList.length" class="mt-4">
        <h3 class="font-medium mb-2">Активные ECN</h3>
        <div v-for="e in ecnList" :key="e.id" class="border-b py-2 text-sm flex justify-between items-center">
          <span><b>#{{ e.id }}</b> — {{ e.description || 'Без описания' }}</span>
          <span class="text-xs px-2 py-0.5 rounded-full" :class="e.status==='OPEN'?'bg-yellow-100 text-yellow-700':'bg-green-100 text-green-700'">{{ e.status }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'ECNPage',
  props: { api: Function, showError: Function },
  data() {
    return { products: [], ecnList: [], ecn: { productId: null, description: '', priority: 3 } }
  },
  async mounted() {
    const d = await this.api('/api/products?page_size=200')
    if (d) this.products = d.items || []
  },
  methods: {
    async createECN() {
      try {
        const d = await this.api('/api/editor/tech-processes', { method: 'POST', body: JSON.stringify({ product_id: this.ecn.productId, number: 'ECN-' + Date.now(), description: this.ecn.description }) })
        if (d) { this.ecnList.push({ id: d.id, description: this.ecn.description, status: 'OPEN' }); this.ecn = { productId: null, description: '', priority: 3 } }
      } catch (e) { this.showError('Ошибка: ' + e.message) }
    },
  },
}
</script>
