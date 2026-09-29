import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  base: './', // imprescindible: Electron carga el build desde file://, no desde raíz de dominio
  build: {
    outDir: 'dist',
  },
})
