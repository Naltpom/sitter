import {
    createContext,
    ReactNode,
    useCallback,
    useContext,
    useEffect,
    useMemo,
    useState,
} from "react";
import api from "../api";

export interface SSOProvider {
  name: string;
  label: string;
  enabled: boolean;
}

interface PublicAppSettings {
  app_name: string;
  app_description: string;
  app_logo: string;
  app_favicon: string;
  primary_color: string;
  header_show_logo: string;
  header_show_name: string;
  providers: SSOProvider[];
}

const DEFAULTS: PublicAppSettings = {
  app_name: "Sitter",
  app_description: "",
  app_logo: "/logo_full.svg",
  app_favicon: "/favicon.svg",
  primary_color: "#1E40AF",
  header_show_logo: "true",
  header_show_name: "true",
  providers: [],
};

interface AppSettingsContextType {
  settings: PublicAppSettings;
  loading: boolean;
  settled: boolean;
  refreshSettings: () => Promise<void>;
}

const AppSettingsContext = createContext<AppSettingsContextType | undefined>(
  undefined,
);

export function AppSettingsProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<PublicAppSettings>(DEFAULTS);
  const [loading, setLoading] = useState(false);
  const [settled, setSettled] = useState(false);

  const fetchSettings = useCallback(async () => {
    try {
      const res = await api.get("/settings/public");
      setSettings({ ...DEFAULTS, ...res.data });
    } catch {
      setSettings(DEFAULTS);
    } finally {
      setLoading(false);
      setSettled(true);
    }
  }, []);

  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  const contextValue = useMemo(
    () => ({ settings, loading, settled, refreshSettings: fetchSettings }),
    [settings, loading, settled, fetchSettings],
  );

  return (
    <AppSettingsContext.Provider value={contextValue}>
      {children}
    </AppSettingsContext.Provider>
  );
}

export function useAppSettings() {
  const context = useContext(AppSettingsContext);
  if (context === undefined) {
    throw new Error(
      "useAppSettings must be used within an AppSettingsProvider",
    );
  }
  return context;
}
