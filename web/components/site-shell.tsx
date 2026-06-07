'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { LocaleProvider } from './locale-context';
import {
  DEFAULT_LOCALE,
  HTML_LANG,
  LANGUAGE_NAMES,
  LANGUAGE_SELECTOR_LABELS,
  NAV_LABELS,
  type Locale,
  type LocalizedText,
  localize,
  normalizeLocale,
  withLocale,
} from '../lib/i18n';

const NAV = [
  { href: '/', key: 'overview' },
  { href: '/simulator', key: 'simulator' },
  { href: '/results', key: 'results' },
  { href: '/methodology', key: 'methodology' },
  { href: '/hardware', key: 'hardware' },
  { href: '/reproducibility', key: 'reproducibility' },
];

export function SiteShell({
  eyebrow,
  title,
  intro,
  shellCopy,
  children,
}: {
  eyebrow: string;
  title: string;
  intro: string;
  shellCopy?: {
    eyebrow?: LocalizedText;
    title?: LocalizedText;
    intro?: LocalizedText;
  };
  children: ReactNode;
}) {
  const [locale, setLocaleState] = useState<Locale>(DEFAULT_LOCALE);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const queryLocale = normalizeLocale(params.get('lang'));
    window.setTimeout(() => setLocaleState(queryLocale), 0);
  }, []);

  useEffect(() => {
    document.documentElement.lang = HTML_LANG[locale];
  }, [locale]);

  const setLocale = (nextLocale: Locale) => {
    setLocaleState(nextLocale);
    const url = new URL(window.location.href);
    if (nextLocale === DEFAULT_LOCALE) {
      url.searchParams.delete('lang');
    } else {
      url.searchParams.set('lang', nextLocale);
    }
    window.history.replaceState(null, '', `${url.pathname}${url.search}${url.hash}`);
  };

  const localizedShell = useMemo(
    () => ({
      eyebrow: localize(shellCopy?.eyebrow, locale, eyebrow),
      title: localize(shellCopy?.title, locale, title),
      intro: localize(shellCopy?.intro, locale, intro),
    }),
    [eyebrow, intro, locale, shellCopy, title],
  );

  return (
    <LocaleProvider value={{ locale, setLocale }}>
      <div className="min-h-screen bg-[linear-gradient(180deg,#f7faf7_0%,#eef6f3_48%,#f8f7f2_100%)] text-stone-900">
        <header className="border-b border-stone-900/10 backdrop-blur-sm">
          <div className="mx-auto flex max-w-7xl flex-col gap-6 px-6 py-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl space-y-3">
              <p className="eyebrow">{localizedShell.eyebrow}</p>
              <h1 className="text-3xl font-semibold leading-tight text-stone-950 sm:text-4xl lg:text-5xl">
                {localizedShell.title}
              </h1>
              <p className="max-w-2xl text-base leading-7 text-stone-700 lg:text-lg">
                {localizedShell.intro}
              </p>
            </div>
            <div className="flex flex-col gap-3 lg:items-end">
              <LanguageSwitcher locale={locale} setLocale={setLocale} />
              <nav className="flex flex-wrap gap-2">
                {NAV.map((item) => (
                  <Link key={item.href} href={withLocale(item.href, locale)} className="nav-pill">
                    {NAV_LABELS[locale][item.key]}
                  </Link>
                ))}
              </nav>
            </div>
          </div>
        </header>
        <main className="mx-auto flex max-w-7xl flex-col gap-8 px-6 py-10">{children}</main>
      </div>
    </LocaleProvider>
  );
}

function LanguageSwitcher({
  locale,
  setLocale,
}: {
  locale: Locale;
  setLocale: (locale: Locale) => void;
}) {
  return (
    <div className="language-switcher" aria-label={LANGUAGE_SELECTOR_LABELS[locale]}>
      {Object.entries(LANGUAGE_NAMES).map(([key, label]) => {
        const nextLocale = key as Locale;
        return (
          <button
            key={key}
            type="button"
            className={nextLocale === locale ? 'language-pill active' : 'language-pill'}
            onClick={() => setLocale(nextLocale)}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}

export function Panel({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    <section className="panel">
      <div className="mb-6 flex flex-col gap-2">
        <h2 className="text-2xl font-semibold text-stone-950">{title}</h2>
        {description ? <p className="text-sm leading-6 text-stone-600">{description}</p> : null}
      </div>
      {children}
    </section>
  );
}
