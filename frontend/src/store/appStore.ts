import { create } from 'zustand'

type AppState = {
  activeModule: string
  setActiveModule: (moduleKey: string) => void
}

export const useAppStore = create<AppState>((set) => ({
  activeModule: 'overview',
  setActiveModule: (moduleKey) => set({ activeModule: moduleKey }),
}))
