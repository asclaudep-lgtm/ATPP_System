<template>
  <div class="p-6">
    <h2 class="text-xl font-semibold text-slate-900 mb-4">Редактор изделий и ТП</h2>

    <!-- Продукты -->
    <div class="mb-6 bg-white rounded-xl border border-slate-200 p-4">
      <div class="flex items-center gap-3 mb-3">
        <h3 class="font-medium text-slate-800">Изделия</h3>
        <button @click="showProductForm=!showProductForm" class="px-3 py-1.5 bg-orange-500 hover:bg-orange-600 text-white rounded-lg text-xs">+ Создать</button>
      </div>

      <div v-if="showProductForm" class="grid grid-cols-3 gap-3 mb-4 p-3 bg-slate-50 rounded-lg">
        <input v-model="prod.designation" placeholder="Обозначение*" class="px-2 py-1.5 border rounded text-sm" />
        <input v-model="prod.name" placeholder="Название*" class="px-2 py-1.5 border rounded text-sm" />
        <input v-model="prod.mass" placeholder="Масса, кг" type="number" step="0.1" class="px-2 py-1.5 border rounded text-sm" />
        <input v-model="prod.dimensions" placeholder="Габариты (напр. 100x50x20)" class="px-2 py-1.5 border rounded text-sm" />
        <input v-model="prod.accuracy_class" placeholder="Класс точности (IT7)" class="px-2 py-1.5 border rounded text-sm" />
        <input v-model="prod.blank_type" placeholder="Тип заготовки (круг)" class="px-2 py-1.5 border rounded text-sm" />
        <button @click="createProduct" class="px-4 py-1.5 bg-green-500 hover:bg-green-600 text-white rounded-lg text-sm col-span-3">Сохранить изделие</button>
      </div>

      <table class="w-full text-sm">
        <thead><tr class="text-left text-slate-500 border-b"><th>Обозначение</th><th>Название</th><th>Масса</th><th>Точность</th><th></th></tr></thead>
        <tbody>
          <tr v-for="p in products" :key="p.id" class="border-b hover:bg-slate-50">
            <td class="py-2">{{ p.designation }}</td>
            <td>{{ p.name }}</td>
            <td>{{ p.mass }} кг</td>
            <td>{{ p.accuracy_class }}</td>
            <td><button @click="selectProduct(p)" class="text-orange-600 hover:text-orange-800 text-xs">Выбрать →</button></td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- ТП редактор -->
    <div v-if="selectedProduct" class="bg-white rounded-xl border border-slate-200 p-4">
      <h3 class="font-medium text-slate-800 mb-3">ТП для: {{ selectedProduct.designation }} — {{ selectedProduct.name }}</h3>

      <div v-if="!currentTP" class="mb-3">
        <div class="flex gap-2">
          <input v-model="tpNumber" placeholder="Номер ТП" class="px-2 py-1.5 border rounded text-sm" />
          <button @click="createTP" class="px-3 py-1.5 bg-orange-500 hover:bg-orange-600 text-white rounded-lg text-xs">Создать ТП</button>
        </div>
      </div>

      <div v-else>
        <div class="text-sm text-slate-500 mb-3">ТП №{{ currentTP.number }} (ID: {{ currentTP.id }})</div>
        <div class="mb-3 flex gap-2">
          <input v-model="newOp.number" placeholder="Номер" class="px-2 py-1.5 border rounded text-xs w-20" />
          <input v-model="newOp.name" placeholder="Название операции" class="px-2 py-1.5 border rounded text-xs flex-1" />
          <input v-model="newOp.t_setup" placeholder="Tпз" type="number" step="0.1" class="px-2 py-1.5 border rounded text-xs w-20" />
          <input v-model="newOp.t_piece" placeholder="Tшт" type="number" step="0.1" class="px-2 py-1.5 border rounded text-xs w-20" />
          <input v-model="newOp.grade" placeholder="Разряд" type="number" class="px-2 py-1.5 border rounded text-xs w-16" />
          <button @click="addOperation" class="px-3 py-1.5 bg-green-500 hover:bg-green-600 text-white rounded-lg text-xs">+</button>
        </div>
        <table class="w-full text-sm">
          <thead><tr class="text-left text-slate-500 border-b"><th>№</th><th>Операция</th><th>Tпз</th><th>Tшт</th><th>Разряд</th><th></th></tr></thead>
          <tbody>
            <tr v-for="op in operations" :key="op.id" class="border-b">
              <td class="py-1">{{ op.number }}</td>
              <td>{{ op.name }}</td>
              <td>{{ op.t_setup }}</td>
              <td>{{ op.t_piece }}</td>
              <td>{{ op.grade }}</td>
              <td><button @click="deleteOperation(op.id)" class="text-red-500 hover:text-red-700 text-xs">✕</button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'EditorPage',
  props: { api: Function, showError: Function },
  data() {
    return {
      products: [], selectedProduct: null, showProductForm: false,
      prod: { designation: '', name: '', mass: null, dimensions: '', accuracy_class: '', blank_type: '' },
      currentTP: null, tpNumber: 'TP-001', operations: [],
      newOp: { number: '005', name: '', t_setup: 0, t_piece: 0, grade: 3 },
    }
  },
  async mounted() { await this.loadProducts() },
  methods: {
    async loadProducts() {
      const d = await this.api('/api/products?page_size=200')
      if (d) this.products = d.items || []
    },
    async createProduct() {
      const d = await this.api('/api/editor/products', { method: 'POST', body: JSON.stringify(this.prod) })
      if (d) { this.showProductForm = false; this.prod = { designation: '', name: '', mass: null, dimensions: '', accuracy_class: '', blank_type: '' }; await this.loadProducts() }
    },
    async selectProduct(p) { this.selectedProduct = p; this.currentTP = null; this.operations = []; await this.loadTPs(p.id) },
    async loadTPs(pid) {
      const d = await this.api(`/api/tech-processes?product_id=${pid}`)
      if (d?.items?.length) { this.currentTP = d.items[0]; await this.loadOps(this.currentTP.id) }
    },
    async createTP() {
      const d = await this.api('/api/editor/tech-processes', { method: 'POST', body: JSON.stringify({ product_id: this.selectedProduct.id, number: this.tpNumber }) })
      if (d) { this.currentTP = d; this.operations = [] }
    },
    async loadOps(tpid) {
      const d = await this.api(`/api/tech-processes/${tpid}`)
      if (d?.operations) this.operations = d.operations
    },
    async addOperation() {
      const d = await this.api('/api/editor/operations', { method: 'POST', body: JSON.stringify({ ...this.newOp, tech_process_id: this.currentTP.id, sort_order: this.operations.length }) })
      if (d) { this.newOp = { number: String((this.operations.length+1)*5).padStart(3,'0'), name: '', t_setup: 0, t_piece: 0, grade: 3 }; await this.loadOps(this.currentTP.id) }
    },
    async deleteOperation(opid) {
      await this.api(`/api/editor/operations/${opid}`, { method: 'DELETE' })
      await this.loadOps(this.currentTP.id)
    },
  },
}
</script>
