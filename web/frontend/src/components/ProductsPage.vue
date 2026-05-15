<template>
  <div>
    <div class="card">
      <input v-model="search" placeholder="Поиск по обозначению..." @input="loadProducts"
             style="padding:8px;width:300px;border:1px solid #ddd;border-radius:4px">
      <table>
        <thead><tr><th>Обозначение</th><th>Наименование</th><th>Масса</th><th>Габариты</th><th>Класс точн.</th></tr></thead>
        <tbody>
          <tr v-for="p in products" :key="p.id" @click="loadBOM(p.id)" style="cursor:pointer" :title="'Нажмите для BOM'">
            <td><b>{{ p.designation }}</b></td><td>{{ p.name }}</td>
            <td>{{ p.mass || '—' }}</td><td>{{ p.dimensions || '—' }}</td><td>{{ p.accuracy_class || '—' }}</td>
          </tr>
        </tbody>
      </table>
      <div style="margin-top:8px;color:#666;font-size:12px">
        Всего: {{ productsTotal }} | Страница {{ page_num }} из {{ Math.ceil(productsTotal/50) || 1 }}
        <button @click="page_num--;loadProducts()" :disabled="page_num<=1">←</button>
        <button @click="page_num++;loadProducts()" :disabled="page_num*50>=productsTotal">→</button>
      </div>
    </div>
    <div class="card" v-if="bomTree.length">
      <h3>Состав изделия (BOM):</h3>
      <div v-for="node in bomTree" :key="node.id">
        <BomNode :node="node" />
      </div>
    </div>
  </div>
</template>

<script>
import BomNode from './BomNode.vue'

export default {
  name: 'ProductsPage',
  components: { BomNode },
  props: ['api', 'showError'],
  data() { return {
    search: '', products: [], productsTotal: 0, page_num: 1, bomTree: [],
    Math: Math,
  }},
  methods: {
    async loadProducts() {
      const p = this.page_num; const s = this.search
      try { const d = await this.api('/api/products?page=' + p + '&page_size=50&search=' + encodeURIComponent(s))
        this.products = d.items; this.productsTotal = d.total } catch(e) { this.showError('Не удалось загрузить изделия') }
    },
    async loadBOM(productId) {
      try { const d = await this.api('/api/bom/' + productId); this.bomTree = d?.tree || [] } catch(e) {}
    },
  },
  async mounted() { this.loadProducts() },
}
</script>
