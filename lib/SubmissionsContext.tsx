import React, { createContext, useCallback, useContext, useMemo, useState } from 'react';

import type { Submission } from '@/types/submission';

type SubmissionsContextValue = {
  submissions: Submission[];
  addSubmission: (s: Omit<Submission, 'id' | 'createdAt'>) => string;
  getById: (id: string) => Submission | undefined;
  updateSubmission: (id: string, patch: Partial<Submission>) => void;
};

const SubmissionsContext = createContext<SubmissionsContextValue | null>(null);

function createId() {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 9)}`;
}

export function SubmissionsProvider({ children }: { children: React.ReactNode }) {
  const [submissions, setSubmissions] = useState<Submission[]>([]);

  const addSubmission = useCallback((s: Omit<Submission, 'id' | 'createdAt'>) => {
    const id = createId();
    const row: Submission = { ...s, id, createdAt: Date.now() };
    setSubmissions((prev) => [row, ...prev]);
    return id;
  }, []);

  const getById = useCallback(
    (id: string) => submissions.find((x) => x.id === id),
    [submissions],
  );

  const updateSubmission = useCallback((id: string, patch: Partial<Submission>) => {
    setSubmissions((prev) =>
      prev.map((row) => (row.id === id ? { ...row, ...patch } : row)),
    );
  }, []);

  const value = useMemo(
    () => ({ submissions, addSubmission, getById, updateSubmission }),
    [submissions, addSubmission, getById, updateSubmission],
  );

  return <SubmissionsContext.Provider value={value}>{children}</SubmissionsContext.Provider>;
}

export function useSubmissions() {
  const ctx = useContext(SubmissionsContext);
  if (!ctx) throw new Error('useSubmissions must be used within SubmissionsProvider');
  return ctx;
}
