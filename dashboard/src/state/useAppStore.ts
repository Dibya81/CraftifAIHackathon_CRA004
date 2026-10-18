import { create } from "zustand";

export type Theme = "light" | "dark";

interface AppState {
  theme: Theme;
  presentMode: boolean;
  navCollapsed: boolean;
  selectedIncidentId: string | null;
  commandPaletteOpen: boolean;
  soundEnabled: boolean;
  unreadCount: number;
  previousTheme: Theme;

  // Actions
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
  setPresentMode: (present: boolean) => void;
  togglePresentMode: () => void;
  setNavCollapsed: (collapsed: boolean) => void;
  toggleNavCollapsed: () => void;
  setSelectedIncidentId: (id: string | null) => void;
  setCommandPaletteOpen: (open: boolean) => void;
  toggleCommandPalette: () => void;
  setSoundEnabled: (enabled: boolean) => void;
  setUnreadCount: (count: number) => void;
  incrementUnreadCount: () => void;
  resetUnreadCount: () => void;
}

const getInitialTheme = (): Theme => {
  if (typeof window === "undefined") return "light";
  const saved = localStorage.getItem("sitesentinel_theme") as Theme;
  if (saved && (saved === "light" || saved === "dark")) return saved;
  return "light";
};

const getInitialSoundEnabled = (): boolean => {
  if (typeof window === "undefined") return false;
  return localStorage.getItem("sitesentinel_sound") === "true";
};

export const useAppStore = create<AppState>((set, get) => ({
  theme: getInitialTheme(),
  presentMode: false,
  navCollapsed: false,
  selectedIncidentId: null,
  commandPaletteOpen: false,
  soundEnabled: getInitialSoundEnabled(),
  unreadCount: 0,
  previousTheme: getInitialTheme(),

  setTheme: (theme) => {
    if (typeof document !== "undefined") {
      document.documentElement.setAttribute("data-theme", theme);
      localStorage.setItem("sitesentinel_theme", theme);
    }
    set({ theme });
  },

  toggleTheme: () => {
    const next = get().theme === "light" ? "dark" : "light";
    get().setTheme(next);
  },

  setPresentMode: (present) => {
    const currentTheme = get().theme;
    if (present) {
      // In Present mode, default to dark "control room" theme
      get().setTheme("dark");
      set({ presentMode: true, previousTheme: currentTheme, navCollapsed: true });
    } else {
      // Restore previous theme
      get().setTheme(get().previousTheme);
      set({ presentMode: false, navCollapsed: false });
    }
  },

  togglePresentMode: () => {
    get().setPresentMode(!get().presentMode);
  },

  setNavCollapsed: (navCollapsed) => set({ navCollapsed }),
  toggleNavCollapsed: () => set((state) => ({ navCollapsed: !state.navCollapsed })),

  setSelectedIncidentId: (selectedIncidentId) => set({ selectedIncidentId }),

  setCommandPaletteOpen: (commandPaletteOpen) => set({ commandPaletteOpen }),
  toggleCommandPalette: () => set((state) => ({ commandPaletteOpen: !state.commandPaletteOpen })),

  setSoundEnabled: (soundEnabled) => {
    if (typeof window !== "undefined") {
      localStorage.setItem("sitesentinel_sound", soundEnabled ? "true" : "false");
    }
    set({ soundEnabled });
  },

  setUnreadCount: (unreadCount) => {
    if (typeof document !== "undefined") {
      document.title = unreadCount > 0 ? `(${unreadCount}) SiteSentinel` : "SiteSentinel";
    }
    set({ unreadCount });
  },

  incrementUnreadCount: () => {
    const next = get().unreadCount + 1;
    get().setUnreadCount(next);
  },

  resetUnreadCount: () => {
    get().setUnreadCount(0);
  },
}));
