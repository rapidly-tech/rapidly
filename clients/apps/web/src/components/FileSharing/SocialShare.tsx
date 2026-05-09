'use client'

import { JSX, ReactNode, useCallback } from 'react'

// ── Icon Components ──

/** SVG icon component for the Viber messaging platform. */
export const ViberIcon = () => (
  <svg
    className="h-5 w-5"
    viewBox="0 0 24 24"
    fill="currentColor"
    aria-hidden="true"
  >
    <path d="M11.4 0C9.473.028 5.333.344 3.02 2.467 1.302 4.187.696 6.7.633 9.817.57 12.933.488 18.776 6.12 20.36h.003l-.004 2.416s-.037.977.61 1.177c.777.242 1.234-.5 1.98-1.302.407-.44.972-1.084 1.397-1.58 3.85.326 6.812-.416 7.15-.525.776-.252 5.176-.816 5.892-6.657.74-6.02-.36-9.83-2.34-11.546-.596-.55-3.006-2.3-8.375-2.323 0 0-.395-.025-1.037-.017zm.058 1.693c.545-.004.88.017.88.017 4.542.02 6.717 1.388 7.222 1.846 1.675 1.435 2.53 4.868 1.906 9.897v.002c-.604 4.878-4.174 5.184-4.832 5.395-.28.09-2.882.737-6.153.524 0 0-2.436 2.94-3.197 3.704-.12.12-.26.167-.352.144-.13-.033-.166-.188-.165-.414l.02-4.018c-4.762-1.32-4.485-6.292-4.43-8.895.054-2.604.543-4.738 1.996-6.173 1.96-1.773 5.474-2.018 7.11-2.03zm.38 2.602c-.167 0-.303.135-.304.302 0 .167.133.303.3.305 1.624.01 2.946.537 4.028 1.592 1.073 1.046 1.62 2.468 1.633 4.334.002.167.14.3.307.3.166-.002.3-.138.3-.304-.014-1.984-.618-3.596-1.816-4.764-1.19-1.16-2.692-1.753-4.447-1.765zm-3.96.695c-.19-.032-.4.005-.616.117l-.01.002c-.43.247-.816.562-1.146.932-.002.004-.006.004-.008.008-.267.323-.42.638-.46.948-.008.046-.01.093-.007.14 0 .136.022.27.065.4l.013.01c.135.48.473 1.276 1.205 2.604.42.768.903 1.5 1.446 2.186.27.344.56.673.87.984l.132.132c.31.308.64.6.984.87.686.543 1.418 1.027 2.186 1.447 1.328.733 2.126 1.07 2.604 1.206l.01.014c.13.042.265.064.402.063.046.002.092 0 .138-.008.31-.036.627-.19.948-.46.004 0 .003-.002.008-.005.37-.33.683-.72.93-1.148l.003-.01c.225-.432.15-.842-.18-1.12-.004 0-.698-.58-1.037-.83-.36-.255-.73-.492-1.113-.71-.51-.285-1.032-.106-1.248.174l-.447.564c-.23.283-.657.246-.657.246-3.12-.796-3.955-3.955-3.955-3.955s-.037-.426.248-.656l.563-.448c.277-.215.456-.737.17-1.248-.217-.383-.454-.756-.71-1.115-.25-.34-.826-1.033-.83-1.035-.137-.165-.31-.265-.502-.297zm4.49.88c-.158.002-.29.124-.3.282-.01.167.115.312.282.324 1.16.085 2.017.466 2.645 1.15.63.688.93 1.524.906 2.57-.002.168.13.306.3.31.166.003.305-.13.31-.297.025-1.175-.334-2.193-1.067-2.994-.74-.81-1.777-1.253-3.05-1.346h-.024zm.463 1.63c-.16.002-.29.127-.3.287-.008.167.12.31.288.32.523.028.875.175 1.113.422.24.245.388.62.416 1.164.01.167.15.295.318.287.167-.008.295-.15.287-.317-.03-.644-.215-1.178-.58-1.557-.367-.378-.893-.574-1.52-.607h-.018z" />
  </svg>
)

/** SVG icon component for the Signal messaging platform. */
export const SignalIcon = () => (
  <svg
    className="h-5 w-5"
    viewBox="0 0 24 24"
    fill="currentColor"
    aria-hidden="true"
  >
    <path d="M12 0q-.934 0-1.83.139l.17 1.111a11 11 0 0 1 3.32 0l.172-1.111A12 12 0 0 0 12 0M9.152.34A12 12 0 0 0 5.77 1.742l.584.961a10.8 10.8 0 0 1 3.066-1.27zm5.696 0-.268 1.094a10.8 10.8 0 0 1 3.066 1.27l.584-.962A12 12 0 0 0 14.848.34M12 2.25a9.75 9.75 0 0 0-8.539 14.459c.074.134.1.292.064.441l-1.013 4.338 4.338-1.013a.62.62 0 0 1 .441.064A9.7 9.7 0 0 0 12 21.75c5.385 0 9.75-4.365 9.75-9.75S17.385 2.25 12 2.25m-7.092.068a12 12 0 0 0-2.59 2.59l.909.664a11 11 0 0 1 2.345-2.345zm14.184 0-.664.909a11 11 0 0 1 2.345 2.345l.909-.664a12 12 0 0 0-2.59-2.59M1.742 5.77A12 12 0 0 0 .34 9.152l1.094.268a10.8 10.8 0 0 1 1.269-3.066zm20.516 0-.961.584a10.8 10.8 0 0 1 1.27 3.066l1.093-.268a12 12 0 0 0-1.402-3.383M.138 10.168A12 12 0 0 0 0 12q0 .934.139 1.83l1.111-.17A11 11 0 0 1 1.125 12q0-.848.125-1.66zm23.723.002-1.111.17q.125.812.125 1.66c0 .848-.042 1.12-.125 1.66l1.111.172a12.1 12.1 0 0 0 0-3.662M1.434 14.58l-1.094.268a12 12 0 0 0 .96 2.591l-.265 1.14 1.096.255.36-1.539-.188-.365a10.8 10.8 0 0 1-.87-2.35m21.133 0a10.8 10.8 0 0 1-1.27 3.067l.962.584a12 12 0 0 0 1.402-3.383zm-1.793 3.848a11 11 0 0 1-2.345 2.345l.664.909a12 12 0 0 0 2.59-2.59zm-19.959 1.1L.357 21.48a1.8 1.8 0 0 0 2.162 2.161l1.954-.455-.256-1.095-1.953.455a.675.675 0 0 1-.81-.81l.454-1.954zm16.832 1.769a10.8 10.8 0 0 1-3.066 1.27l.268 1.093a12 12 0 0 0 3.382-1.402zm-10.94.213-1.54.36.256 1.095 1.139-.266c.814.415 1.683.74 2.591.961l.268-1.094a10.8 10.8 0 0 1-2.35-.869zm3.634 1.24-.172 1.111a12.1 12.1 0 0 0 3.662 0l-.17-1.111q-.812.125-1.66.125a11 11 0 0 1-1.66-.125" />
  </svg>
)

/** SVG icon component for Apple iMessage. */
export const IMessageIcon = () => (
  <svg
    className="h-5 w-5"
    viewBox="0 0 24 24"
    fill="currentColor"
    aria-hidden="true"
  >
    <path d="M12 2C6.477 2 2 5.813 2 10.5c0 2.61 1.41 4.94 3.61 6.47-.2.86-.68 2.25-1.56 3.43 0 0 2.67-.47 4.67-1.84.86.16 1.72.24 2.58.44h.7c5.523 0 10-3.813 10-8.5S17.523 2 12 2z" />
  </svg>
)

/** SVG icon component for the Telegram messaging platform. */
export const TelegramIcon = () => (
  <svg
    className="h-5 w-5"
    viewBox="0 0 24 24"
    fill="currentColor"
    aria-hidden="true"
  >
    <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z" />
  </svg>
)

/** SVG icon component for WhatsApp. */
export const WhatsAppIcon = () => (
  <svg
    className="h-5 w-5"
    viewBox="0 0 24 24"
    fill="currentColor"
    aria-hidden="true"
  >
    <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
  </svg>
)

/** SVG icon component for Microsoft Teams. */
export const TeamsIcon = () => (
  <svg
    className="h-5 w-5"
    viewBox="0 0 24 24"
    fill="currentColor"
    aria-hidden="true"
  >
    <path d="M19.404 4.5a2.1 2.1 0 1 0 0 4.2 2.1 2.1 0 0 0 0-4.2zm2.4 5.4h-3.9a1.2 1.2 0 0 0-1.2 1.2v4.5a3.3 3.3 0 0 0 2.7 3.24V18a.6.6 0 0 0 .6.6h2.4a.6.6 0 0 0 .6-.6v-6.9a1.2 1.2 0 0 0-1.2-1.2zM14.1 3.6a2.7 2.7 0 1 0 0 5.4 2.7 2.7 0 0 0 0-5.4zm2.4 6.6H9.9a1.2 1.2 0 0 0-1.2 1.2v5.4A4.2 4.2 0 0 0 12.9 21h2.4a4.2 4.2 0 0 0 4.2-4.2v-5.4a1.2 1.2 0 0 0-1.2-1.2zM7.5 7.5H3.6a1.2 1.2 0 0 0-1.2 1.2v6h1.8v3.6a.6.6 0 0 0 .6.6h1.8a.6.6 0 0 0 .6-.6v-3.6h1.8v-6a1.2 1.2 0 0 0-1.2-1.2zM5.55 6.6a1.8 1.8 0 1 0 0-3.6 1.8 1.8 0 0 0 0 3.6z" />
  </svg>
)

/** SVG icon component for Slack. */
export const SlackIcon = () => (
  <svg
    className="h-5 w-5"
    viewBox="0 0 24 24"
    fill="currentColor"
    aria-hidden="true"
  >
    <path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zM6.313 15.165a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313zM8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834zM8.834 6.313a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312zM18.956 8.834a2.528 2.528 0 0 1 2.522-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.522V8.834zM17.688 8.834a2.528 2.528 0 0 1-2.523 2.521 2.527 2.527 0 0 1-2.52-2.521V2.522A2.527 2.527 0 0 1 15.165 0a2.528 2.528 0 0 1 2.523 2.522v6.312zM15.165 18.956a2.528 2.528 0 0 1 2.523 2.522A2.528 2.528 0 0 1 15.165 24a2.527 2.527 0 0 1-2.52-2.522v-2.522h2.52zM15.165 17.688a2.527 2.527 0 0 1-2.52-2.523 2.526 2.526 0 0 1 2.52-2.52h6.313A2.527 2.527 0 0 1 24 15.165a2.528 2.528 0 0 1-2.522 2.523h-6.313z" />
  </svg>
)

/** SVG icon component for Discord. */
export const DiscordIcon = () => (
  <svg
    className="h-5 w-5"
    viewBox="0 0 24 24"
    fill="currentColor"
    aria-hidden="true"
  >
    <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028c.462-.63.874-1.295 1.226-1.994a.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z" />
  </svg>
)

/** SVG icon component for Twitch. */
export const TwitchIcon = () => (
  <svg
    className="h-5 w-5"
    viewBox="0 0 24 24"
    fill="currentColor"
    aria-hidden="true"
  >
    <path d="M11.571 4.714h1.715v5.143H11.57zm4.715 0H18v5.143h-1.714zM6 0L1.714 4.286v15.428h5.143V24l4.286-4.286h3.428L22.286 12V0zm14.571 11.143l-3.428 3.428h-3.429l-3 3v-3H6.857V1.714h13.714z" />
  </svg>
)

/** SVG icon component for email sharing. */
export const EmailIcon = () => (
  <svg
    className="h-5 w-5"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <circle cx="18" cy="5" r="3" />
    <circle cx="6" cy="12" r="3" />
    <circle cx="18" cy="19" r="3" />
    <line x1="8.59" y1="13.51" x2="15.42" y2="17.49" />
    <line x1="15.41" y1="6.51" x2="8.59" y2="10.49" />
  </svg>
)

// ── SocialShareButton Component ──

interface SocialShareButtonProps {
  icon: ReactNode
  label: string
  onClick: () => void
  color: string
}

/** Renders a styled button with an icon and label for sharing via a social platform. */
export function SocialShareButton({
  icon,
  label,
  onClick,
  color,
}: SocialShareButtonProps): JSX.Element {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex flex-col items-center gap-0.5 rounded-xl p-2 transition-all hover:scale-105 ${color}`}
      title={`Share via ${label}`}
      aria-label={`Share via ${label}`}
    >
      {icon}
      <span className="text-xs font-medium">{label}</span>
    </button>
  )
}

// ── useSocialShare Hook ──

interface SocialShareConfig {
  url: string
  emailSubject: string
  emailBody: string
  shareText: string
}

/** Hook that returns share handler functions for ten social platforms. */
export function useSocialShare({
  url,
  emailSubject,
  emailBody,
  shareText,
}: SocialShareConfig) {
  const shareViaEmail = useCallback(() => {
    window.open(
      `mailto:?subject=${encodeURIComponent(emailSubject)}&body=${encodeURIComponent(emailBody)}`,
      '_blank',
      'noopener,noreferrer',
    )
  }, [emailSubject, emailBody])

  const shareViaIMessage = useCallback(() => {
    window.open(
      `sms:&body=${encodeURIComponent(url)}`,
      '_blank',
      'noopener,noreferrer',
    )
  }, [url])

  const shareViaViber = useCallback(() => {
    window.open(
      `viber://forward?text=${encodeURIComponent(url)}`,
      '_blank',
      'noopener,noreferrer',
    )
  }, [url])

  const shareViaSignal = useCallback(() => {
    navigator.clipboard.writeText(url).catch(() => {}) // Clipboard may be unavailable
    window.open('https://signal.me', '_blank', 'noopener,noreferrer')
  }, [url])

  const shareViaTelegram = useCallback(() => {
    window.open(
      `https://t.me/share/url?url=${encodeURIComponent(url)}&text=${encodeURIComponent(shareText)}`,
      '_blank',
      'noopener,noreferrer',
    )
  }, [url, shareText])

  const shareViaWhatsApp = useCallback(() => {
    window.open(
      `https://wa.me/?text=${encodeURIComponent(url)}`,
      '_blank',
      'noopener,noreferrer',
    )
  }, [url])

  const shareViaTeams = useCallback(() => {
    window.open(
      `https://teams.microsoft.com/share?href=${encodeURIComponent(url)}&msgText=${encodeURIComponent(shareText)}`,
      '_blank',
      'noopener,noreferrer',
    )
  }, [url, shareText])

  const shareViaSlack = useCallback(() => {
    navigator.clipboard.writeText(url).catch(() => {}) // Clipboard may be unavailable
    window.open('https://app.slack.com', '_blank', 'noopener,noreferrer')
  }, [url])

  const shareViaDiscord = useCallback(() => {
    navigator.clipboard.writeText(url).catch(() => {}) // Clipboard may be unavailable
    window.open(
      'https://discord.com/channels/@me',
      '_blank',
      'noopener,noreferrer',
    )
  }, [url])

  const shareViaTwitch = useCallback(() => {
    navigator.clipboard.writeText(url).catch(() => {}) // Clipboard may be unavailable
    window.open('https://www.twitch.tv', '_blank', 'noopener,noreferrer')
  }, [url])

  return {
    shareViaEmail,
    shareViaIMessage,
    shareViaViber,
    shareViaSignal,
    shareViaTelegram,
    shareViaWhatsApp,
    shareViaTeams,
    shareViaSlack,
    shareViaDiscord,
    shareViaTwitch,
  }
}

// ── SocialShareGrid Component ──

/** Renders a "Share via" divider and a grid of social share buttons. */
export function SocialShareGrid({
  handlers,
}: {
  handlers: ReturnType<typeof useSocialShare>
}): JSX.Element {
  return (
    <>
      <div className="flex items-center gap-4">
        <div className="h-px flex-1 bg-slate-200 dark:bg-slate-800" />
        <span className="text-sm text-slate-400 dark:text-slate-500">
          Share via
        </span>
        <div className="h-px flex-1 bg-slate-200 dark:bg-slate-800" />
      </div>
      <div className="grid grid-cols-5 gap-1">
        <SocialShareButton
          icon={<EmailIcon />}
          label="Email"
          onClick={handlers.shareViaEmail}
          color="text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-900"
        />
        <SocialShareButton
          icon={<TeamsIcon />}
          label="Teams"
          onClick={handlers.shareViaTeams}
          color="text-teal-600 hover:bg-teal-50 dark:hover:bg-teal-900/20"
        />
        <SocialShareButton
          icon={<SlackIcon />}
          label="Slack"
          onClick={handlers.shareViaSlack}
          color="text-teal-600 hover:bg-teal-50 dark:hover:bg-teal-900/20"
        />
        <SocialShareButton
          icon={<DiscordIcon />}
          label="Discord"
          onClick={handlers.shareViaDiscord}
          color="text-teal-500 hover:bg-teal-50 dark:hover:bg-teal-900/20"
        />
        <SocialShareButton
          icon={<TwitchIcon />}
          label="Twitch"
          onClick={handlers.shareViaTwitch}
          color="text-teal-500 hover:bg-teal-50 dark:hover:bg-teal-900/20"
        />
        <SocialShareButton
          icon={<IMessageIcon />}
          label="iMessage"
          onClick={handlers.shareViaIMessage}
          color="text-emerald-500 hover:bg-emerald-50 dark:hover:bg-emerald-900/20"
        />
        <SocialShareButton
          icon={<WhatsAppIcon />}
          label="WhatsApp"
          onClick={handlers.shareViaWhatsApp}
          color="text-emerald-500 hover:bg-emerald-50 dark:hover:bg-emerald-900/20"
        />
        <SocialShareButton
          icon={<TelegramIcon />}
          label="Telegram"
          onClick={handlers.shareViaTelegram}
          color="text-slate-600 hover:bg-slate-100 dark:hover:bg-slate-800/20"
        />
        <SocialShareButton
          icon={<ViberIcon />}
          label="Viber"
          onClick={handlers.shareViaViber}
          color="text-teal-600 hover:bg-teal-50 dark:hover:bg-teal-900/20"
        />
        <SocialShareButton
          icon={<SignalIcon />}
          label="Signal"
          onClick={handlers.shareViaSignal}
          color="text-slate-600 hover:bg-slate-100 dark:hover:bg-slate-800/20"
        />
      </div>
    </>
  )
}
