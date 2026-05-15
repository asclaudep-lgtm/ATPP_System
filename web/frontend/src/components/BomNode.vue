<template>
  <div :style="{marginLeft:'20px',padding:'4px 0'}">
    <span :style="{fontWeight:node.has_tp?'bold':'normal'}">📦 {{ node.designation }} — {{ node.name }}</span>
    <span class="text-slate-600 text-xs ml-2">{{ node.level }} ×{{ node.quantity }}<span v-if="node.position">({{ node.position }})</span>
    <span class="tag ml-1" :class="node.has_tp?'tag-green':'tag-yellow'">{{ node.has_tp?'ТП есть':'Нет ТП'}}</span></span>
    <BomNode v-for="c in node.children" :key="c.id" :node="c" />
  </div>
</template>
<script>
export default { name: 'BomNode', props: ['node'] }
</script>
