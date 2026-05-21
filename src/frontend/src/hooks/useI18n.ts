import { useTranslations } from '../api/i18n'

export function useI18n() {
  const { data } = useTranslations()
  const t = (key: string, fallback?: string): string => {
    return data?.translations[key] ?? fallback ?? key
  }
  return { t }
}
