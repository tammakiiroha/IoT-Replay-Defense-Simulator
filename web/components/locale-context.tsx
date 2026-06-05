'use client';

import { createContext, useContext } from 'react';
import type { Locale } from '../lib/i18n';

export type LocaleContextValue = {
  locale: Locale;
  setLocale: (locale: Locale) => void;
};

const LocaleContext = createContext<LocaleContextValue>({
  locale: 'en',
  setLocale: () => {},
});

export function LocaleProvider({
  value,
  children,
}: {
  value: LocaleContextValue;
  children: React.ReactNode;
}) {
  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useLocale() {
  return useContext(LocaleContext);
}
