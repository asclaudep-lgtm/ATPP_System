<template>
  <!-- LOGIN -->
  <div v-if="!token" class="min-h-screen flex items-center justify-center bg-slate-100">
    <div class="bg-white rounded-2xl shadow-lg p-8 w-full max-w-sm border border-slate-200">
      <div class="flex items-center gap-2 mb-6">
        <div class="w-8 h-8 rounded-lg bg-orange-500 flex items-center justify-center font-bold text-white">A</div>
        <div>
          <div class="font-semibold text-slate-900">ATPP System</div>
          <div class="text-xs text-slate-500">v14.0</div>
        </div>
      </div>
      <input v-model="login.username" placeholder="Логин" class="w-full px-3 py-2.5 border border-slate-300 rounded-lg mb-3 text-sm focus:outline-none focus:border-orange-500 focus:ring-2 focus:ring-orange-100" @keyup.enter="doLogin" />
      <input v-model="login.password" type="password" placeholder="Пароль или API-ключ" class="w-full px-3 py-2.5 border border-slate-300 rounded-lg mb-3 text-sm focus:outline-none focus:border-orange-500 focus:ring-2 focus:ring-orange-100" @keyup.enter="doLogin" />
      <div class="text-xs text-slate-500 mb-3">API-ключ: вставьте в поле пароля (sk-... или atpp_...)</div>
      <div v-if="loginError" class="text-red-600 text-xs mb-3">{{ loginError }}</div>
      <button @click="doLogin" class="w-full py-2.5 bg-orange-500 hover:bg-orange-600 text-white rounded-lg font-medium text-sm transition-colors">Войти</button>
      <div class="mt-4 text-center">
        <a href="#" @click.prevent="showReset=true" class="text-xs text-orange-600 hover:text-orange-700">Забыли пароль?</a>
      </div>
      <div v-if="showReset && resetMsg" class="mt-3 text-xs p-2 rounded-lg" :class="resetOk ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'">{{ resetMsg }}</div>
      <div v-if="showReset && !resetSent" class="mt-3 space-y-2">
        <input v-model="resetEmail" placeholder="Email или username" class="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm" />
        <button @click="doReset" class="w-full py-2 bg-amber-500 hover:bg-amber-600 text-white rounded-lg text-sm transition-colors">Сбросить пароль</button>
      </div>
    </div>
  </div>

  <!-- MAIN APP -->
  <div v-else class="flex h-screen overflow-hidden">
    <!-- SIDEBAR -->
    <aside class="w-64 bg-slate-900 text-slate-200 flex flex-col flex-shrink-0">
      <div class="px-5 py-5 border-b border-slate-800">
        <div class="flex items-center gap-2">
          <div class="w-8 h-8 rounded-lg bg-orange-500 flex items-center justify-center font-bold text-white">A</div>
          <div>
            <div class="font-semibold text-white">ATPP System</div>
            <div class="text-xs text-slate-400">v14.0</div>
          </div>
        </div>
      </div>
      <nav class="flex-1 overflow-y-auto py-3">
        <a v-for="p in pages" :key="p.id" href="#" @click.prevent="switchPage(p.id)"
          :class="['sidebar-link flex items-center gap-3 px-5 py-2.5 text-sm hover:bg-slate-800', page===p.id ? 'active' : 'text-slate-400']">
          <span>{{ p.icon }}</span>
          <span>{{ p.label }}</span>
          <span v-if="p.badge" class="ml-auto text-xs px-2 py-0.5 rounded-full bg-orange-500 text-white">{{ p.badge }}</span>
        </a>
      </nav>
      <div class="border-t border-slate-800 p-4">
        <div class="flex items-center gap-3">
          <div class="w-9 h-9 rounded-full bg-slate-700 flex items-center justify-center font-medium text-sm">{{ (user.full_name || user.username || '?').charAt(0).toUpperCase() }}</div>
          <div class="flex-1 min-w-0">
            <div class="text-sm font-medium text-white truncate">{{ user.full_name || user.username }}</div>
            <div class="text-xs text-slate-400">{{ user.role || 'user' }}</div>
          </div>
          <button @click="logout" class="text-slate-400 hover:text-white" title="Выход">⎋</button>
        </div>
      </div>
    </aside>

    <!-- MAIN -->
    <main class="flex-1 overflow-hidden flex flex-col">
      <header class="bg-white border-b border-slate-200 px-6 py-3 flex items-center gap-4">
        <h1 class="text-lg font-semibold text-slate-800">{{ currentTitle }}</h1>
        <div class="flex-1"></div>
        <button @click="toggleTheme" class="px-2 py-1 text-slate-400 hover:text-slate-600 text-sm" :title="theme==='light'?'Тёмная':'Светлая'">{{ theme==='light' ? '🌙' : '☀️' }}</button>
      </header>

      <div v-if="error" class="bg-red-50 border-b border-red-200 text-red-700 px-6 py-2.5 text-sm flex justify-between items-center">
        <span>{{ error }}</span>
        <button @click="error=''" class="text-red-500 hover:text-red-700">&times;</button>
      </div>

      <div class="flex-1 overflow-auto bg-slate-100 p-6">
        <DashboardPage v-if="page==='dashboard'" :key="'dash-'+token" :api="api" :showError="showError" />
        <ProductsPage v-if="page==='products'" :key="'prod-'+token" :api="api" :showError="showError" />
        <TPsPage v-if="page==='tps'" :key="'tps-'+token" :api="api" :showError="showError" />
        <PDOPage v-if="page==='pdo'" :key="'pdo-'+token" :api="api" :showError="showError" />
        <ProductionPage v-if="page==='production'" :key="'prod2-'+token" :api="api" :showError="showError" />
        <QAPage v-if="page==='qa'" :key="'qa-'+token" :api="api" :showError="showError" />
        <ToolingPage v-if="page==='tooling'" :key="'tool-'+token" :api="api" :showError="showError" />
        <OrdersPage v-if="page==='orders'" :key="'ord-'+token" :api="api" :showError="showError" />
        <AuditPage v-if="page==='audit'" :key="'audit-'+token" :api="api" :showError="showError" />
        <BatchOpsPage v-if="page==='batch'" :key="'batch-'+token" :api="api" :showError="showError" />
        <EditorPage v-if="page==='editor'" :key="'editor-'+token" :api="api" :showError="showError" />
        <DocumentsPage v-if="page==='documents'" :key="'docs-'+token" :api="api" :showError="showError" />
        <ECNPage v-if="page==='ecn'" :key="'ecn-'+token" :api="api" :showError="showError" />
        <CostPage v-if="page==='cost'" :key="'cost-'+token" :api="api" :showError="showError" />
        <MaterialPage v-if="page==='materials'" :key="'mat-'+token" :api="api" :showError="showError" />
      </div>
    </main>
  </div>
</template>

<script>
import DashboardPage from './components/DashboardPage.vue'
import ProductsPage from './components/ProductsPage.vue'
import TPsPage from './components/TPsPage.vue'
import PDOPage from './components/PDOPage.vue'
import ProductionPage from './components/ProductionPage.vue'
import QAPage from './components/QAPage.vue'
import ToolingPage from './components/ToolingPage.vue'
import OrdersPage from './components/OrdersPage.vue'
import AuditPage from './components/AuditPage.vue'
import BatchOpsPage from './components/BatchOpsPage.vue'
import EditorPage from './components/EditorPage.vue'
import DocumentsPage from './components/DocumentsPage.vue'
import ECNPage from './components/ECNPage.vue'
import CostPage from './components/CostPage.vue'
import MaterialPage from './components/MaterialPage.vue'

export default {
  name: 'App',
  components: { DashboardPage, ProductsPage, TPsPage, PDOPage, ProductionPage, QAPage, ToolingPage, OrdersPage, AuditPage, BatchOpsPage, EditorPage, DocumentsPage, ECNPage, CostPage, MaterialPage },
  data() {
    return {
      token: localStorage.getItem('atpp_token'),
      user: JSON.parse(localStorage.getItem('atpp_user') || '{}'),
      login: { username: '', password: '' },
      loginError: '', page: 'dashboard', error: '',
      theme: localStorage.getItem('atpp_theme') || 'light',
      showReset: false, resetEmail: '', resetMsg: '', resetOk: false, resetSent: false,
      pages: [
        { id: 'dashboard', label: 'Дашборд', icon: '📊' },
        { id: 'orders', label: 'Производственные заказы', icon: '📋', badge: '' },
        { id: 'production', label: 'Маршрутный лист', icon: '🗺️' },
        { id: 'qa', label: 'QA-терминал', icon: '✓' },
        { id: 'tooling', label: 'Оснастка и инструмент', icon: '🔧' },
        { id: 'products', label: 'Изделия и ТП', icon: '📦' },
        { id: 'pdo', label: 'Заказы ПДО', icon: '📋' },
        { id: 'audit', label: 'Аудит', icon: '📋' },
        { id: 'batch', label: 'Batch-операции', icon: '⚡' },
        { id: 'editor', label: 'Редактор', icon: '✏️' },
        { id: 'documents', label: 'ГОСТ-документы', icon: '📄' },
        { id: 'ecn', label: 'ECN / Извещения', icon: '🔁' },
        { id: 'cost', label: 'Себестоимость', icon: '💰' },
        { id: 'materials', label: 'Нормирование', icon: '📐' },
      ],
    }
  },
  computed: {
    currentTitle() {
      const m = { dashboard:'Дашборд', orders:'Производственные заказы', production:'Маршрутный лист', qa:'QA-терминал', tooling:'Оснастка и инструмент', products:'Изделия и ТП', pdo:'Заказы ПДО', tps:'Техпроцессы', audit:'Аудит', batch:'Batch-операции', editor:'Редактор', documents:'ГОСТ-документы', ecn:'ECN / Извещения', cost:'Себестоимость', materials:'Нормирование' }
      return m[this.page] || ''
    },
  },
  methods: {
    async api(path, opts = {}) {
      const h = { 'Content-Type': 'application/json' }
      if (this.token) h['Authorization'] = 'Bearer ' + this.token
      const r = await fetch(path, { headers: h, ...opts })
      return r.status === 204 ? null : r.json()
    },
    async doLogin() {
      this.loginError = ''
      try {
        const pwd = this.login.password.trim()
        const isApiKey = pwd.startsWith('sk-') || pwd.startsWith('atpp_')
        const body = isApiKey
          ? { api_key: pwd }
          : { username: this.login.username, password: pwd }
        const d = await this.api('/api/auth/login', { method: 'POST', body: JSON.stringify(body) })
        if (!d?.access_token) { this.loginError = 'Неверный логин/пароль'; return }
        this.token = d.access_token; this.user = d.user
        localStorage.setItem('atpp_token', this.token)
        localStorage.setItem('atpp_user', JSON.stringify(this.user))
      } catch (e) { this.loginError = 'Ошибка подключения' }
    },
    logout() { localStorage.removeItem('atpp_token'); localStorage.removeItem('atpp_user'); this.token = ''; this.user = {} },
    showError(msg) { this.error = msg; setTimeout(() => this.error = '', 8000) },
    switchPage(p) { this.page = p },
    toggleTheme() {
      this.theme = this.theme === 'light' ? 'dark' : 'light'
      localStorage.setItem('atpp_theme', this.theme)
      document.documentElement.classList.toggle('dark', this.theme === 'dark')
    },
    async doReset() {
      this.resetMsg = ''; this.resetOk = false
      try {
        const r = await this.api('/api/auth/reset-password', { method: 'POST', body: JSON.stringify({ login: this.resetEmail }) })
        this.resetMsg = r?.message || 'Инструкции отправлены'
        this.resetOk = true; this.resetSent = true
      } catch (e) { this.resetMsg = 'Пользователь не найден'; this.resetOk = false }
    },
  },
}
</script>
