<template>
  <div class="space-y-4">
    <div class="flex gap-2 items-center">
      <input v-model="search" @input="loadProducts" placeholder="Поиск по обозначению..." class="px-3 py-2 border border-slate-300 rounded-lg text-sm w-72 bg-white focus:outline-none focus:border-orange-500" />
      <span class="text-sm text-slate-500">{{ productsTotal }} всего · стр. {{ page_num }}/{{ Math.ceil(productsTotal/50) || 1 }}</span>
      <div class="flex-1"></div>
      <button @click="page_num--;loadProducts()" :disabled="page_num<=1" class="px-3 py-1.5 border border-slate-300 rounded-lg text-sm disabled:opacity-40">←</button>
      <button @click="page_num++;loadProducts()" :disabled="page_num*50>=productsTotal" class="px-3 py-1.5 border border-slate-300 rounded-lg text-sm disabled:opacity-40">→</button>
    </div>
    <div class="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
      <table class="w-full text-sm">
        <thead class="bg-slate-50 text-slate-600 text-xs uppercase tracking-wide">
          <tr><th class="text-left px-4 py-3 font-medium">Обозначение</th><th class="text-left px-4 py-3 font-medium">Наименование</th><th class="text-left px-4 py-3 font-medium">Масса</th><th class="text-left px-4 py-3 font-medium">Габариты</th><th class="text-left px-4 py-3 font-medium">Класс точн.</th></tr>
        </thead>
        <tbody>
          <tr v-for="p in products" :key="p.id" @click="loadBOM(p.id)" class="border-t border-slate-100 hover:bg-slate-50 cursor-pointer" title="Нажмите для BOM">
            <td class="px-4 py-3 font-mono text-xs font-medium">{{ p.designation }}</td><td class="px-4 py-3">{{ p.name }}</td>
            <td class="px-4 py-3 text-slate-600">{{ p.mass || '-' }}</td><td class="px-4 py-3 text-slate-600">{{ p.dimensions || '-' }}</td><td class="px-4 py-3 text-slate-600">{{ p.accuracy_class || '-' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-if="bomTree.length" class="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
      <h3 class="font-semibold text-slate-800 mb-3">Состав изделия (BOM):</h3>
      <div v-for="node in bomTree" :key="node.id"><BomNode :node="node" /></div>
    </div>
  </div>
</template>

<script>
import BomNode from './BomNode.vue'
export default {
  name: 'ProductsPage',
  components: { BomNode },
  props: ['api', 'showError'],
  data() { return { search: '', products: [], productsTotal: 0, page_num: 1, bomTree: [], Math } },
  methods: {
    async loadProducts() {
      try { const d = await this.api('/api/products?page=' + this.page_num + '&page_size=50&search=' + encodeURIComponent(this.search)); this.products = d.items; this.productsTotal = d.total } catch(e) { this.showError('Не удалось загрузить изделия') }
    },
    async loadBOM(id) { try { const d = await this.api('/api/bom/' + id); this.bomTree = d?.tree || [] } catch(e) {} },
  },
  async mounted() { this.loadProducts() },
}
</script>
