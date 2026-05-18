<template>
  <div class="p-6">
    <h2 class="text-xl font-semibold text-slate-900 mb-4">Нормирование материалов</h2>
    <div class="bg-white rounded-xl border border-slate-200 p-4">
      <p class="text-sm text-slate-500 mb-4">Расчёт заготовок, КИМ, раскрой листового металла</p>

      <div class="grid grid-cols-3 gap-3 mb-4 p-3 bg-slate-50 rounded-lg">
        <div>
          <label class="block text-xs text-slate-500 mb-1">Тип заготовки</label>
          <select v-model="calc.blankType" class="w-full px-2 py-1.5 border rounded text-sm">
            <option value="круг">Круг</option>
            <option value="лист">Лист</option>
            <option value="труба">Труба</option>
            <option value="шестигранник">Шестигранник</option>
          </select>
        </div>
        <div>
          <label class="block text-xs text-slate-500 mb-1">Материал</label>
          <select v-model="calc.materialId" class="w-full px-2 py-1.5 border rounded text-sm">
            <option :value="null">— выберите —</option>
            <option v-for="m in materials" :key="m.id" :value="m.id">{{ m.name }} {{ m.grade }}</option>
          </select>
        </div>
        <div>
          <label class="block text-xs text-slate-500 mb-1">Количество деталей</label>
          <input v-model.number="calc.qty" type="number" min="1" class="w-full px-2 py-1.5 border rounded text-sm" />
        </div>
        <div>
          <label class="block text-xs text-slate-500 mb-1">Диаметр/длина, мм</label>
          <input v-model.number="calc.diameter" type="number" step="0.1" class="w-full px-2 py-1.5 border rounded text-sm" />
        </div>
        <div>
          <label class="block text-xs text-slate-500 mb-1">Припуск, мм</label>
          <input v-model.number="calc.allowance" type="number" step="0.1" class="w-full px-2 py-1.5 border rounded text-sm" />
        </div>
        <div>
          <label class="block text-xs text-slate-500 mb-1">Цена ₽/кг</label>
          <input v-model.number="calc.pricePerKg" type="number" step="0.01" class="w-full px-2 py-1.5 border rounded text-sm" />
        </div>
      </div>

      <button @click="calculate" class="px-4 py-2 bg-orange-500 hover:bg-orange-600 text-white rounded-lg text-sm">Рассчитать</button>

      <div v-if="result" class="mt-4 grid grid-cols-3 gap-3">
        <div class="p-3 bg-blue-50 rounded-lg"><div class="text-xs text-blue-600">Масса заготовки</div><div class="text-lg font-semibold">{{ result.blankMass }} кг</div></div>
        <div class="p-3 bg-green-50 rounded-lg"><div class="text-xs text-green-600">КИМ</div><div class="text-lg font-semibold">{{ result.kim }}%</div></div>
        <div class="p-3 bg-amber-50 rounded-lg"><div class="text-xs text-amber-600">Стоимость на партию</div><div class="text-lg font-semibold">{{ result.cost }} ₽</div></div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'MaterialPage',
  props: { api: Function, showError: Function },
  data() {
    return {
      materials: [], result: null,
      calc: { blankType: 'круг', materialId: null, qty: 100, diameter: 50, allowance: 3, pricePerKg: 120 },
    }
  },
  async mounted() {
    try {
      const d = await this.api('/api/mobile/materials')
      if (d?.items) this.materials = d.items
    } catch (e) { /* ignore */ }
  },
  methods: {
    calculate() {
      const d = this.calc.diameter / 1000
      const rho = 7850 // kg/m³ for steel
      let blankVolume, partVolume

      if (this.calc.blankType === 'круг') {
        const area = Math.PI * (d + this.calc.allowance / 1000) ** 2 / 4
        blankVolume = area * (d * 3)
      } else if (this.calc.blankType === 'лист') {
        blankVolume = (d + this.calc.allowance / 1000) ** 2 * d
      } else {
        blankVolume = Math.PI * (d / 2) ** 2 * (d * 3)
      }

      partVolume = Math.PI * (d / 2) ** 2 * (d * 3)
      const blankMass = +(blankVolume * rho).toFixed(2)
      const partMass = +(partVolume * rho).toFixed(2)
      const kim = +(partMass / Math.max(blankMass, 0.001) * 100).toFixed(1)
      const totalMass = blankMass * this.calc.qty
      const cost = +(totalMass * this.calc.pricePerKg).toFixed(0)

      this.result = { blankMass, kim, cost }
    },
  },
}
</script>
