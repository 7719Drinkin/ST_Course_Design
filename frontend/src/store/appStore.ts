import { create } from 'zustand'

type AppState = {
  currentStep: number
  setCurrentStep: (step: number) => void
}

export const useAppStore = create<AppState>((set) => ({
  currentStep: 0,
  setCurrentStep: (step) => set({ currentStep: step }),
}))
