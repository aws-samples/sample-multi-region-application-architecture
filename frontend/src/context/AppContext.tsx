import { createContext, useContext, useState, useEffect } from 'react';
import type { ReactNode } from 'react';
import { api } from '../utils/api';
import type { RegionInfo } from '../utils/api';

interface AppContextType {
  regionInfo: RegionInfo | null;
  loading: boolean;
  error: string | null;
  refreshRegionInfo: () => Promise<void>;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

export const AppProvider = ({ children }: { children: ReactNode }) => {
  const [regionInfo, setRegionInfo] = useState<RegionInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refreshRegionInfo = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getRegionInfo();
      setRegionInfo(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load region info');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refreshRegionInfo();
  }, []);

  return (
    <AppContext.Provider value={{ regionInfo, loading, error, refreshRegionInfo }}>
      {children}
    </AppContext.Provider>
  );
};

export const useApp = () => {
  const context = useContext(AppContext);
  if (!context) throw new Error('useApp must be used within AppProvider');
  return context;
};
