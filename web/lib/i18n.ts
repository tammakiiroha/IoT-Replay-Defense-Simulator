export const LOCALES = ['en', 'ja', 'zh'] as const;

export type Locale = (typeof LOCALES)[number];
export type LocalizedText = Record<Locale, string>;

export const DEFAULT_LOCALE: Locale = 'en';

export const LANGUAGE_NAMES: Record<Locale, string> = {
  en: 'English',
  ja: '日本語',
  zh: '中文',
};

export const HTML_LANG: Record<Locale, string> = {
  en: 'en',
  ja: 'ja',
  zh: 'zh-CN',
};

export const LANGUAGE_SELECTOR_LABELS: Record<Locale, string> = {
  en: 'Language selector',
  ja: '言語セレクター',
  zh: '语言选择器',
};

export const NAV_LABELS: Record<Locale, Record<string, string>> = {
  en: {
    overview: 'Overview',
    simulator: 'Simulator',
    results: 'Results',
    methodology: 'Methodology',
    hardware: 'Hardware',
    reproducibility: 'Reproducibility',
  },
  ja: {
    overview: '概要',
    simulator: 'シミュレータ',
    results: '結果',
    methodology: '手法',
    hardware: 'ハードウェア',
    reproducibility: '再現性',
  },
  zh: {
    overview: '概览',
    simulator: '模拟器',
    results: '结果',
    methodology: '方法',
    hardware: '硬件',
    reproducibility: '可复现性',
  },
};

export function normalizeLocale(value: string | null | undefined): Locale {
  if (value === 'ja' || value === 'zh' || value === 'en') {
    return value;
  }
  return DEFAULT_LOCALE;
}

export function localize(text: LocalizedText | undefined, locale: Locale, fallback: string): string {
  return text?.[locale] ?? fallback;
}

export function withLocale(path: string, locale: Locale): string {
  const hashIndex = path.indexOf('#');
  const pathWithoutHash = hashIndex >= 0 ? path.slice(0, hashIndex) : path;
  const hash = hashIndex >= 0 ? path.slice(hashIndex) : '';
  const queryIndex = pathWithoutHash.indexOf('?');
  const pathname = queryIndex >= 0 ? pathWithoutHash.slice(0, queryIndex) : pathWithoutHash;
  const query = queryIndex >= 0 ? pathWithoutHash.slice(queryIndex + 1) : '';
  const params = new URLSearchParams(query);

  if (locale === DEFAULT_LOCALE) {
    params.delete('lang');
  } else {
    params.set('lang', locale);
  }

  const nextQuery = params.toString();
  return `${pathname}${nextQuery ? `?${nextQuery}` : ''}${hash}`;
}
