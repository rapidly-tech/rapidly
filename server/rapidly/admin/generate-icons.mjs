#!/usr/bin/env node
/**
 * Generates a CSS file with Solar Linear icon classes for the admin panel.
 * Each class uses mask-image so icons inherit currentColor.
 *
 * Usage: node generate-icons.mjs
 */

import { readFileSync, writeFileSync } from 'node:fs'
import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)
const solarData = JSON.parse(
  readFileSync(require.resolve('@iconify-json/solar/icons.json'), 'utf-8'),
)

// Map: CSS class name -> Solar icon name
const ICONS = {
  'icon-clipboard': 'clipboard-linear',
  'icon-clipboard-check': 'clipboard-check-linear',
  'icon-close': 'close-circle-linear',
  'icon-check': 'check-read-linear',
  'icon-menu': 'hamburger-menu-linear',
  'icon-search': 'magnifer-linear',
  'icon-external-link': 'square-arrow-right-up-linear',
  'icon-ellipsis-vertical': 'menu-dots-linear',
  'icon-sort-asc': 'sort-from-bottom-to-top-linear',
  'icon-sort-desc': 'sort-from-top-to-bottom-linear',
  'icon-download': 'download-linear',
  'icon-globe': 'global-linear',
}

const defaultWidth = solarData.width || 24
const defaultHeight = solarData.height || 24

const rules = []
for (const [className, iconName] of Object.entries(ICONS)) {
  const icon = solarData.icons[iconName]
  if (!icon) {
    console.error(`Missing icon: ${iconName}`)
    process.exit(1)
  }
  const w = icon.width || defaultWidth
  const h = icon.height || defaultHeight
  const svg = `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 ${w} ${h}'>${icon.body}</svg>`
  const encoded = `url("data:image/svg+xml,${encodeURIComponent(svg)}")`

  rules.push(`.${className} {
  display: inline-block;
  width: 1em;
  height: 1em;
  background-color: currentColor;
  -webkit-mask-image: ${encoded};
  mask-image: ${encoded};
  -webkit-mask-repeat: no-repeat;
  mask-repeat: no-repeat;
  -webkit-mask-size: 100% 100%;
  mask-size: 100% 100%;
}`)
}

const output = `/* AUTO-GENERATED — do not edit. Run: node generate-icons.mjs */\n${rules.join('\n')}\n`

writeFileSync('./static/solar-icons.css', output, 'utf-8')
console.log(`Generated static/solar-icons.css (${Object.keys(ICONS).length} icons)`)
