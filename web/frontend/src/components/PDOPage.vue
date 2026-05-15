<template>
  <div>
    <div class="card">
      <div style="display:flex;justify-content:space-between;align-items:center">
        <h3>📋 Заказы ПДО</h3>
        <button @click="showCreate=!showCreate" style="padding:6px 16px;cursor:pointer;background:#27ae60;color:#fff;border:none;border-radius:4px">+ Новый заказ</button>
      </div>
      <div v-if="showCreate" style="background:#f8f9fa;padding:12px;border-radius:4px;margin:8px 0">
        <input v-model="pdoNew.des" placeholder="Обозначение изделия" style="padding:6px;width:200px;margin-right:8px">
        <input v-model="pdoNew.qty" placeholder="Кол-во" type="number" style="padding:6px;width:80px;margin-right:8px">
        <input v-model="pdoNew.ac" placeholder="Тип ВС" style="padding:6px;width:120px;margin-right:8px">
        <input v-model="pdoNew.customer" placeholder="Заказчик" style="padding:6px;width:150px">
        <button @click="createOrder" style="margin-left:8px;padding:6px 16px;cursor:pointer;background:#1976d2;color:#fff;border:none;border-radius:4px">Создать</button>
        <span v-if="createMsg" style="margin-left:8px;font-size:12px">{{ createMsg }}</span>
      </div>
      <select v-model="filter" @change="loadOrders" style="padding:6px;margin-bottom:8px">
        <option value="">Все</option>
        <option value="NEW">Новый</option>
        <option value="OMTS_REVIEW">ОМТС: проработка</option>
        <option value="TECH_DEPT">Тех.отдел</option>
        <option value="FEASIBLE">Возможно изготовить</option>
        <option value="NOT_FEASIBLE">Невозможно</option>
        <option value="DEPUTY_APPROVAL">Зам.Тех.Дир</option>
        <option value="APPROVED">Утверждён</option>
        <option value="IN_SHOP">В цехе</option>
        <option value="QC">ОТК</option>
        <option value="CLOSED">Закрыт</option>
      </select>
      <table>
        <thead><tr><th>Заказ</th><th>Изделие</th><th>ВС</th><th>Статус</th><th>Поз.</th><th>Записки</th><th>Срок</th></tr></thead>
        <tbody>
          <tr v-for="o in orders" :key="o.id" @click="selectOrder(o)" style="cursor:pointer"
              :style="{borderLeft:'4px solid '+statusColor(o.status)}">
            <td><b>{{ o.number }}</b></td>
            <td>{{ o.product }}</td>
            <td style="font-size:11px;color:#1976d2">{{ o.aircraft_type || '—' }}</td>
            <td><span style="font-size:11px">{{ o.status }}</span></td>
            <td>{{ (o.nomenclature||[]).length || '—' }}</td>
            <td style="font-size:11px">{{ (o.memos||[]).length ? '📄'+(o.memos||[]).length : '—' }}</td>
            <td style="font-size:11px">{{ o.due_date || '—' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="card" v-if="detail">
      <h3>{{ detail.number }} — {{ detail.product }}
        <span v-if="detail.aircraft_type" style="color:#1976d2;font-size:14px">✈ {{ detail.aircraft_type }}</span>
      </h3>
      <p>{{ detail.product_name }} | Статус: <b>{{ detail.status }}</b> | Кол-во: {{ detail.qty }}</p>

      <h4 style="margin-top:12px">📋 Номенклатура:</h4>
      <table v-if="detail.nomenclature && detail.nomenclature.length">
        <thead><tr><th>Feas.</th><th>КД</th><th>Обозначение</th><th>Наименование</th><th>Кол-во</th><th>Материал</th></tr></thead>
        <tbody>
          <tr v-for="it in detail.nomenclature" :key="it.id"
              :style="{background: it.tech_feasible===true?'#e8f5e9':it.tech_feasible===false?'#ffebee':'#fff'}">
            <td>{{ it.tech_feasible===true?'✅':it.tech_feasible===false?'❌':'⬜' }}</td>
            <td>{{ it.kd_ready?'📄':'' }}</td>
            <td>{{ it.designation }}</td>
            <td>{{ it.name }}</td>
            <td>×{{ it.qty }}</td>
            <td style="font-size:11px">{{ it.material_name || '—' }}</td>
          </tr>
        </tbody>
      </table>
      <p v-else style="color:#999">Номенклатура не задана</p>

      <h4 style="margin-top:12px">📄 Служебные записки:</h4>
      <table v-if="detail.memos && detail.memos.length">
        <thead><tr><th>Тип</th><th>Номер</th><th>Отдел</th><th>Содержание</th><th>Дата</th></tr></thead>
        <tbody>
          <tr v-for="m in detail.memos" :key="m.id">
            <td>{{ m.memo_type==='У'?'📋 Указание':'📌 Приказ' }}</td>
            <td>{{ m.memo_number }}</td><td>{{ m.from_dept }}</td>
            <td style="font-size:11px">{{ m.content }}</td><td>{{ m.issued_at }}</td>
          </tr>
        </tbody>
      </table>
      <p v-else style="color:#999">Служебных записок нет</p>

      <h4 style="margin-top:12px">🔄 История передач:</h4>
      <table v-if="detail.handoffs && detail.handoffs.length">
        <thead><tr><th>От</th><th>Кому</th><th>Статус</th><th>Дата</th></tr></thead>
        <tbody>
          <tr v-for="h in detail.handoffs" :key="h.created_at">
            <td>{{ h.from }}</td><td>{{ h.to }}</td><td>{{ h.status }}</td><td>{{ h.created_at }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script>
export default {
  name: 'PDOPage',
  props: ['api', 'showError'],
  data() { return {
    orders: [], detail: null, filter: '',
    showCreate: false, pdoNew: { des:'', qty:'', ac:'', customer:'' }, createMsg: '',
  }},
  methods: {
    async loadOrders() {
      const qs = this.filter ? '?status=' + this.filter : ''
      try { this.orders = await this.api('/api/pdo/orders' + qs) || [] } catch(e) {}
    },
    async selectOrder(o) {
      try { this.detail = await this.api('/api/pdo/orders/' + o.id) } catch(e) {}
    },
    statusColor(st) {
      const m = { 'Новый':'#95a5a6', 'ОМТС: проработка':'#16a085',
                  'Тех.отдел: проверка':'#2980b9', 'Возможно изготовить':'#27ae60',
                  'Невозможно изготовить':'#c0392b', 'Зам.Тех.Дир: утверждение':'#8e44ad',
                  'Утверждён':'#27ae60', 'В цехе':'#8e44ad', 'ОТК':'#e67e22',
                  'Закрыт':'#2c3e50' }
      return m[st] || '#999'
    },
    async createOrder() {
      const des = this.pdoNew.des.trim()
      this.createMsg = ''
      if (!des) { this.createMsg = 'Введите обозначение'; return }
      try {
        const qty = this.pdoNew.qty || 1
        const r = await this.api('/api/pdo/orders?' +
          'designation=' + encodeURIComponent(des) +
          '&qty=' + qty +
          '&aircraft_type=' + encodeURIComponent(this.pdoNew.ac || '') +
          '&customer=' + encodeURIComponent(this.pdoNew.customer || '') +
          '&priority=3', { method: 'POST' })
        this.createMsg = 'Создан: ' + r.number
        this.showCreate = false
        this.pdoNew = { des:'', qty:'', ac:'', customer:'' }
        this.loadOrders()
      } catch(e) { this.createMsg = 'Ошибка: изделие не найдено или нет прав' }
    },
  },
  async mounted() { this.loadOrders() },
}
</script>
