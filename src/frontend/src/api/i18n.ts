import { useQuery } from '@tanstack/react-query'
import { apiFetch } from './client'

interface I18nResponse {
  lang: string
  supported_languages: string[]
  translations: Record<string, string>
}

const browserLang = navigator.language.startsWith('de') ? 'de' : 'en'

export function useTranslations(lang = browserLang) {
  return useQuery({
    queryKey: ['i18n', lang],
    queryFn: () => apiFetch<I18nResponse>(`/api/i18n/translations?lang=${lang}`),
    staleTime: Infinity,
  })
}
