/**
 * Rapidly — Shiki syntax highlighting configuration.
 * Restricts loaded grammars to languages actually rendered in the app.
 */
export const USED_LANGUAGES = ['javascript', 'bash']

export const themeConfig = {
  light: 'catppuccin-latte',
  dark: 'poimandres',
}

export const themesList = Object.values(themeConfig)
