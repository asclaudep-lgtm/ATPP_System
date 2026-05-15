<template>
  <div class="space-y-4">
    <div class="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
      <div class="flex justify-between items-center">
        <h3 class="font-semibold text-slate-800">📋 Заказы ПДО</h3>
        <button @click="showCreate=!showCreate" class="px-4 py-2 bg-orange-500 hover:bg-orange-600 text-white rounded-lg text-sm font-medium transition-colors">+ Новый заказ</button>
      </div>
      <div v-if="showCreate" class="bg-slate-50 border border-slate-200 rounded-lg p-3 mt-3 flex gap-2 flex-wrap">
        <input v-model="pdoNew.des" placeholder="Обозначение" class="px-2 py-1.5 border border-slate-300 rounded text-sm w-40 bg-white" />
        <input v-model="pdoNew.qty" placeholder="Кол-во" type="number" class="px-2 py-1.5 border border-slate-300 rounded text-sm w-20 bg-white" />
        <input v-model="pdoNew.ac" placeholder="Тип ВС" class="px-2 py-1.5 border border-slate-300 rounded text-sm w-28 bg-white" />
        <input v-model="pdoNew.customer" placeholder="Заказчик" class="px-2 py-1.5 border border-slate-300 rounded text-sm w-36 bg-white" />
        <button @click="createOrder" class="px-4 py-1.5 bg-orange-500 hover:bg-orange-600 text-white rounded text-sm transition-colors">Создать</button>
        <span v-if="createMsg" class="text-xs text-slate-600 self-center">{{ createMsg }}</span>
      </div>
      <select v-model="filter" @change="loadOrders" class="mt-3 px-3 py-1.5 border border-slate-300 rounded-lg text-sm bg-white">
        <option value="">Все статусы</option>
        <option value="NEW">Новый</option><option value="OMTS_REVIEW">ОМТС: проработка</option><option value="TECH_DEPT">Тех.отдел</option>
        <option value="FEASIBLE">Возможно изготовить</option><option value="APPROVED">Утверждён</option><option value="IN_SHOP">В цехе</option><option value="CLOSED">Закрыт</option>
      </select>
      <div class="overflow-hidden mt-3">
        <table class="w-full text-sm">
          <thead class="bg-slate-50 text-slate-600 text-xs uppercase tracking-wide">
            <tr><th class="text-left px-4 py-3 font-medium">Заказ</th><th class="text-left px-4 py-3 font-medium">Изделие</th><th class="text-left px-4 py-3 font-medium">ВС</th><th class="text-left px-4 py-3 font-medium">Статус</th><th class="text-left px-4 py-3 font-medium">Поз.</th><th class="text-left px-4 py-3 font-medium">Срок</th></tr>
          </thead>
          <tbody>
            <tr v-for="o in orders" :key="o.id" @click="selectOrder(o)" class="border-t border-slate-100 hover:bg-slate-50 cursor-pointer" :style="{borderLeft:'4px solid '+statusColor(o.status)}">
              <td class="px-4 py-3 font-mono text-xs font-medium">{{ o.number }}</td><td class="px-4 py-3">{{ o.product }}</td>
              <td class="px-4 py-3 text-xs text-orange-600">{{ o.aircraft_type || '-' }}</td>
              <td class="px-4 py-3"><span class="tag tag-gray text-[10px]">{{ o.status }}</span></td>
              <td class="px-4 py-3 text-slate-500">{{ (o.nomenclature||[]).length || '-' }}</td>
              <td class="px-4 py-3 text-xs text-slate-600">{{ o.due_date || '-' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="detail" class="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
      <h3 class="font-semibold text-slate-800">{{ detail.number }} — {{ detail.product }} <span v-if="detail.aircraft_type" class="text-orange-600">✈ {{ detail.aircraft_type }}</span></h3>
      <p class="text-sm text-slate-600 mt-1">{{ detail.product_name }} | Статус: <b>{{ detail.status }}</b> | Кол-во: {{ detail.qty }}</p>
      <h4 class="font-medium text-sm mt-4 mb-2">📋 Номенклатура:</h4>
      <table v-if="detail.nomenclature?.length" class="w-full text-sm">
        <thead class="bg-slate-50 text-xs uppercase text-slate-600"><tr><th class="text-left px-3 py-2 font-medium">Feas.</th><th class="text-left px-3 py-2 font-medium">Обозначение</th><th class="text-left px-3 py-2 font-medium">Наименование</th><th class="text-left px-3 py-2 font-medium">Кол-во</th><th class="text-left px-3 py-2 font-medium">Материал</th></tr></thead>
        <tbody><tr v-for="it in detail.nomenclature" :key="it.id" :class="'border-t border-slate-100 '+(it.tech_feasible===true?'bg-emerald-50':it.tech_feasible===false?'bg-red-50':'')"><td class="px-3 py-2">{{ it.tech_feasible===true?'✅':it.tech_feasible===false?'❌':'⬜' }}</td><td class="px-3 py-2">{{ it.designation }}</td><td class="px-3 py-2">{{ it.name }}</td><td class="px-3 py-2">×{{ it.qty }}</td><td class="px-3 py-2 text-xs text-slate-600">{{ it.material_name || '-' }}</td></tr></tbody>
      </table>
      <h4 class="font-medium text-sm mt-4 mb-2">📄 Служебные записки:</h4>
      <div v-if="detail.memos?.length" class="space-y-1">
        <div v-for="m in detail.memos" :key="m.id" class="p-2 bg-slate-50 rounded text-sm">{{ m.memo_type==='У'?'📋':'📌' }} {{ m.memo_number }} — {{ m.content?.slice(0,80) }} <span class="text-xs text-slate-500">{{ m.issued_at }}</span></div>
      </div>
      <p v-else class="text-sm text-slate-400">Служебных записок нет</p>
    </div>
  </div>
</template>

<script>
export default {
  name: 'PDOPage',
  props: ['api', 'showError'],
  data() { return { orders: [], detail: null, filter: '', showCreate: false, pdoNew: { des:'', qty:'', ac:'', customer:'' }, createMsg: '' } },
  methods: {
    async loadOrders() { const qs = this.filter ? '?status=' + this.filter : ''; try { this.orders = await this.api('/api/pdo/orders' + qs) || [] } catch(e) {} },
    async selectOrder(o) { try { this.detail = await this.api('/api/pdo/orders/' + o.id) } catch(e) {} },
    statusColor(st) { const m={'Новый':'#95a5a6','Возможно изготовить':'#27ae60','Невозможно изготовить':'#c0392b','Утверждён':'#27ae60','В цехе':'#8e44ad','Закрыт':'#2c3e50'}; return m[st]||'#999' },
    async createOrder() {
      const des = this.pdoNew.des.trim(); this.createMsg = ''
      if (!des) { this.createMsg = 'Введите обозначение'; return }
      try { const r = await this.api('/api/pdo/orders?designation=' + encodeURIComponent(des) + '&qty=' + (this.pdoNew.qty||1) + '&aircraft_type=' + encodeURIComponent(this.pdoNew.ac||'') + '&customer=' + encodeURIComponent(this.pdoNew.customer||'') + '&priority=3', { method: 'POST' }); this.createMsg = 'Создан: ' + r.number; this.showCreate = false; this.pdoNew = { des:'', qty:'', ac:'', customer:'' }; this.loadOrders() } catch(e) { this.createMsg = 'Ошибка' }
    },
  },
  async mounted() { this.loadOrders() },
}
</script>
