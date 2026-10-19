<script setup lang="ts">
import DefaultTheme from 'vitepress/theme';
import { ref, onMounted, onUnmounted } from 'vue';

const { Layout } = DefaultTheme;

const isCollapsed = ref(false);

const toggleSidebar = () => {
  isCollapsed.value = !isCollapsed.value;
  if (typeof document !== 'undefined') {
    if (isCollapsed.value) {
      document.documentElement.classList.add('sidebar-collapsed');
      localStorage.setItem('ryouu_sidebar_collapsed', 'true');
    } else {
      document.documentElement.classList.remove('sidebar-collapsed');
      localStorage.setItem('ryouu_sidebar_collapsed', 'false');
    }
  }
};

const handleKeyDown = (e: KeyboardEvent) => {
  // Support Ctrl+B or Cmd+B to toggle sidebar panel
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'b') {
    e.preventDefault();
    toggleSidebar();
  }
};

onMounted(() => {
  const saved = localStorage.getItem('ryouu_sidebar_collapsed');
  if (saved === 'true') {
    isCollapsed.value = true;
    document.documentElement.classList.add('sidebar-collapsed');
  }
  window.addEventListener('keydown', handleKeyDown);
});

onUnmounted(() => {
  if (typeof window !== 'undefined') {
    window.removeEventListener('keydown', handleKeyDown);
  }
});
</script>

<template>
  <Layout>
    <!-- Collapsible toggle button right inside the side panel -->
    <template #sidebar-nav-before>
      <div class="sidebar-collapse-wrapper">
        <button 
          class="sidebar-collapse-btn" 
          @click="toggleSidebar" 
          type="button"
          title="Collapse side panel (Ctrl+B)"
          id="collapse-sidebar-btn"
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
            <line x1="9" y1="3" x2="9" y2="21"/>
            <path d="m14 9-3 3 3 3"/>
          </svg>
          <span class="btn-text">Collapse panel</span>
          <kbd class="kbd-shortcut">Ctrl+B</kbd>
        </button>
      </div>
    </template>
    
    <!-- Floating button to expand side panel when collapsed -->
    <template #layout-bottom>
      <button 
        v-if="isCollapsed" 
        class="sidebar-expand-pill" 
        @click="toggleSidebar" 
        type="button"
        title="Open side panel (Ctrl+B)"
        id="expand-sidebar-btn"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
          <line x1="9" y1="3" x2="9" y2="21"/>
          <path d="m10 9 3 3-3 3"/>
        </svg>
        <span>Open Side Panel</span>
        <kbd class="kbd-pill-shortcut">Ctrl+B</kbd>
      </button>
    </template>
  </Layout>
</template>
