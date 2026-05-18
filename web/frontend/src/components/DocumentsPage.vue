<template>
  <div class="p-6">
    <h2 class="text-xl font-semibold text-slate-900 mb-4">ГОСТ-документы</h2>
    <div class="bg-white rounded-xl border border-slate-200 p-4">
      <p class="text-sm text-slate-500 mb-4">Автоматическая генерация технологической документации по ГОСТ 3.1109-82</p>

      <div class="grid grid-cols-2 gap-4 mb-4">
        <div>
          <label class="block text-sm text-slate-600 mb-1">Изделие</label>
          <select v-model="selectedProductId" @change="checkTP" class="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm">
            <option :value="null">— выберите —</option>
            <option v-for="p in products" :key="p.id" :value="p.id">{{ p.designation }} — {{ p.name }}</option>
          </select>
        </div>
        <div>
          <label class="block text-sm text-slate-600 mb-1">Тип документа</label>
          <select v-model="docType" class="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm">
            <option value="MK">МК — Маршрутная карта (ГОСТ 3.1118-82)</option>
            <option value="MSK">МСК — Маршрутно-сопроводительная карта</option>
            <option value="MTP">МТП — Маршрутный технологический процесс</option>
            <option value="VO">ВО — Ведомость оснастки</option>
          </select>
        </div>
      </div>

      <div v-if="tpInfo" class="text-sm text-green-600 mb-3">✓ Утверждённый ТП найден: {{ tpInfo.number }}</div>
      <div v-if="tpError" class="text-sm text-red-500 mb-3">{{ tpError }}</div>

      <button @click="generate" :disabled="!canGenerate" class="px-4 py-2 bg-orange-500 hover:bg-orange-600 disabled:bg-slate-300 text-white rounded-lg text-sm">Сформировать документ</button>

      <div v-if="lastResult" class="mt-4 p-3 bg-green-50 rounded-lg text-sm text-green-700">
        Документ сформирован: {{ lastResult.file_path }}
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'DocumentsPage',
  props: { api: Function, showError: Function },
  data() {
    return { products: [], selectedProductId: null, docType: 'MK', tpInfo: null, tpError: '', lastResult: null }
  },
  computed: { canGenerate() { return this.selectedProductId && this.tpInfo } },
  async mounted() {
    const d = await this.api('/api/products?page_size=200')
    if (d) this.products = d.items || []
  },
  methods: {
    async checkTP() {
      this.tpInfo = null; this.tpError = ''
      if (!this.selectedProductId) return
      const d = await this.api(`/api/tech-processes?product_id=${this.selectedProductId}&status=APPROVED`)
      if (d?.items?.length) { this.tpInfo = d.items[0] }
      else { this.tpError = 'Нет утверждённого ТП для этого изделия' }
    },
    async generate() {
      try {
        const d = await this.api('/api/editor/documents/generate', { method: 'POST', body: JSON.stringify({ product_id: this.selectedProductId, doc_type: this.docType }) })
        if (d) this.lastResult = d
      } catch (e) { this.showError('Ошибка генерации: ' + e.message) }
    },
  },
}
</script>
