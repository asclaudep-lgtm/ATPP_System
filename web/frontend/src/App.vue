<template>
  <div id="app-root" :class="theme">
    <!-- Login -->
    <div v-if="!token" class="login-form">
      <h2>ATPP System v14</h2>
      <input v-model="login.username" placeholder="Логин" @keyup.enter="doLogin" />
      <input v-model="login.password" type="password" placeholder="Пароль" @keyup.enter="doLogin" />
      <div style="font-size:11px;color:#666;margin-bottom:4px">
        API-ключ: вставьте ключ в поле пароля для входа без логина
      </div>
      <div class="error" v-if="loginError">{{ loginError }}</div>
      <button @click="doLogin">Войти</button>
      <div style="margin-top:8px;text-align:center">
        <a href="#" @click.prevent="showReset=true" style="font-size:12px;color:#1976d2">Забыли пароль?</a>
      </div>
      <div v-if="showReset && resetMsg" :class="resetOk ? 'status-approved' : 'error'" style="margin-top:8px;padding:8px;border-radius:4px;font-size:12px">{{ resetMsg }}</div>
      <div v-if="showReset && !resetSent" style="margin-top:8px">
        <input v-model="resetEmail" placeholder="Email или username" style="width:100%;padding:8px;margin-bottom:4px" />
        <button @click="doReset" style="width:100%;padding:8px;background:#e67e22;color:#fff;border:none;border-radius:4px;cursor:pointer">Сбросить пароль</button>
      </div>
    </div>

    <!-- Main app -->
    <div v-else>
      <header class="header">
        <h1>ATPP Web v14</h1>
        <div style="display:flex;align-items:center;gap:12px">
          <button class="theme-btn" @click="toggleTheme" :title="theme==='light'?'Тёмная тема':'Светлая тема'">
            {{ theme === 'light' ? '🌙' : '☀️' }}
          </button>
          <span>{{ user.full_name || user.username }}</span>
          <button class="logout-btn" @click="logout">Выход</button>
        </div>
      </header>

      <div v-if="error" class="error-bar">
        <span>{{ error }}</span>
        <button @click="error=''">&times;</button>
      </div>

      <nav class="nav">
        <button v-for="p in pages" :key="p.id"
          :class="{ active: page === p.id }"
          @click="switchPage(p.id)">{{ p.label }}</button>
      </nav>

      <DashboardPage v-if="page==='dashboard'" :key="'dash-'+token" :api="api" :showError="showError" />
      <ProductsPage v-if="page==='products'" :key="'prod-'+token" :api="api" :showError="showError" />
      <TPsPage v-if="page==='tps'" :key="'tps-'+token" :api="api" :showError="showError" />
      <PDOPage v-if="page==='pdo'" :key="'pdo-'+token" :api="api" :showError="showError" />
      <ProductionPage v-if="page==='production'" :key="'prod-'+token" :api="api" :showError="showError" />
      <QAPage v-if="page==='qa'" :key="'qa-'+token" :api="api" :showError="showError" />
      <ToolingPage v-if="page==='tooling'" :key="'tool-'+token" :api="api" :showError="showError" />
      <OrdersPage v-if="page==='orders'" :key="'ord-'+token" :api="api" :showError="showError" />
      <AuditPage v-if="page==='audit'" :key="'audit-'+token" :api="api" :showError="showError" />
      <BatchOpsPage v-if="page==='batch'" :key="'batch-'+token" :api="api" :showError="showError" />
    </div>
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

export default {
  name: 'App',
  components: { DashboardPage, ProductsPage, TPsPage, PDOPage, ProductionPage, QAPage, ToolingPage, OrdersPage, AuditPage, BatchOpsPage },
  data() {
    return {
      token: localStorage.getItem('atpp_token'),
      user: JSON.parse(localStorage.getItem('atpp_user') || '{}'),
      login: { username: '', password: '' },
      loginError: '', page: 'dashboard', error: '',
      theme: localStorage.getItem('atpp_theme') || 'light',
      showReset: false, resetEmail: '', resetMsg: '', resetOk: false, resetSent: false,
      pages: [
        { id: 'dashboard', label: '📊 Дашборд' },
        { id: 'products', label: '📦 Изделия' },
        { id: 'tps', label: '📋 Техпроцессы' },
        { id: 'pdo', label: '📋 ПДО' },
        { id: 'production', label: '🏭 Производство' },
        { id: 'qa', label: '🔍 ОТК' },
        { id: 'tooling', label: '🧰 Оснастка' },
        { id: 'orders', label: '📋 Наряды' },
        { id: 'audit', label: '📋 Аудит' },
        { id: 'batch', label: '⚡ Batch-операции' },
      ],
    }
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
    },
    async doReset() {
      this.resetMsg = ''; this.resetOk = false
      try {
        const r = await this.api('/api/auth/reset-password', {
          method: 'POST', body: JSON.stringify({ login: this.resetEmail })
        })
        this.resetMsg = r?.message || 'Инструкции отправлены'
        this.resetOk = true; this.resetSent = true
      } catch (e) { this.resetMsg = 'Пользователь не найден'; this.resetOk = false }
    },
  },
}
</script>

<style>
/* Light theme (default) */
:root, #app-root.light {
  --bg: #f0f2f5;
  --card-bg: #fff;
  --text: #333;
  --text-secondary: #666;
  --border: #eee;
  --shadow: rgba(0,0,0,.08);
  --header-shadow: rgba(0,0,0,.1);
  --nav-bg: #e3e8ef;
  --th-bg: #f8f9fa;
  --input-border: #ddd;
  --login-shadow: rgba(0,0,0,.15);
}
/* Dark theme */
#app-root.dark {
  --bg: #1a1a2e;
  --card-bg: #16213e;
  --text: #e0e0e0;
  --text-secondary: #aaa;
  --border: #2a2a4a;
  --shadow: rgba(0,0,0,.3);
  --header-shadow: rgba(0,0,0,.4);
  --nav-bg: #0f3460;
  --th-bg: #1a1a3e;
  --input-border: #333;
  --login-shadow: rgba(0,0,0,.4);
}

* { box-sizing: border-box; margin: 0; padding: 0 }
body { font-family: system-ui, sans-serif; background: var(--bg); color: var(--text) }
#app-root { max-width: 1200px; margin: 0 auto; padding: 16px }
.header { display: flex; justify-content: space-between; align-items: center;
  background: var(--card-bg); padding: 12px 20px; border-radius: 8px; margin-bottom: 16px;
  box-shadow: 0 1px 3px var(--header-shadow) }
.header h1 { font-size: 20px; color: #1976d2 }
.nav { display: flex; gap: 4px; margin-bottom: 16px; flex-wrap: wrap }
.nav button { padding: 8px 14px; border: none; border-radius: 6px; cursor: pointer;
  background: var(--nav-bg); font-size: 12px; white-space: nowrap; color: var(--text) }
.nav button.active { background: #1976d2; color: #fff }
.card { background: var(--card-bg); border-radius: 8px; padding: 20px; margin-bottom: 12px;
  box-shadow: 0 1px 3px var(--shadow); color: var(--text) }
.login-form { max-width: 400px; margin: 100px auto; padding: 32px; background: var(--card-bg);
  border-radius: 8px; box-shadow: 0 2px 8px var(--login-shadow); color: var(--text) }
.login-form input { width: 100%; padding: 10px; margin: 8px 0; border: 1px solid var(--input-border);
  border-radius: 4px; font-size: 14px; background: var(--card-bg); color: var(--text) }
.login-form button { width: 100%; padding: 10px; background: #1976d2; color: #fff;
  border: none; border-radius: 4px; font-size: 16px; cursor: pointer; margin-top: 12px }
.error { color: #d32f2f; font-size: 12px; margin-top: 4px }
.error-bar { background: #ffebee; color: #c62828; padding: 10px 16px; margin-bottom: 12px;
  border-radius: 4px; display: flex; justify-content: space-between; align-items: center }
.logout-btn { padding: 4px 12px; cursor: pointer }
.theme-btn { background: none; border: 1px solid var(--border); border-radius: 4px; cursor: pointer; padding: 4px 8px; font-size: 14px }
.stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px }
.stat { padding: 16px; text-align: center; border-radius: 8px;
  background: linear-gradient(135deg, #667eea, #764ba2); color: #fff }
.stat .num { font-size: 28px; font-weight: bold }
.stat .lbl { font-size: 12px; opacity: .85; margin-top: 4px }
table { width: 100%; border-collapse: collapse; margin-top: 12px }
th, td { padding: 8px 12px; text-align: left; border-bottom: 1px solid var(--border); font-size: 13px }
th { background: var(--th-bg); font-weight: 600; color: var(--text-secondary) }
.status { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600 }
.status-draft { background: #fff3cd; color: #856404 }
.status-approved { background: #d4edda; color: #155724 }
.status-in-progress { background: #d1ecf1; color: #0c5460 }
.chart-box { width: 100%; height: 280px; margin-top: 12px }
.barcode-input { font-size: 24px; padding: 12px; width: 100%; border: 2px solid #1976d2;
  border-radius: 8px; text-align: center; letter-spacing: 2px; margin-bottom: 16px }
input, select, textarea { background: var(--card-bg); color: var(--text); border: 1px solid var(--input-border) }
</style>
