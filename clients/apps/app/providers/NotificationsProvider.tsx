/**
 * Push notification lifecycle provider for the Rapidly mobile app.
 *
 * Requests permission, obtains an Expo push token when a session is
 * active, and listens for incoming notifications. Notification taps
 * with a deepLink data payload trigger in-app navigation.
 */
import Constants from 'expo-constants'
import * as Device from 'expo-device'
import * as Linking from 'expo-linking'
import * as Notifications from 'expo-notifications'
import { createContext, useContext, useEffect, useRef, useState } from 'react'
import { Platform } from 'react-native'
import { useSession } from './SessionProvider'

// Configure foreground notification display
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: true,
    shouldShowBanner: true,
    shouldShowList: true,
  }),
})

function reportRegistrationError(msg: string) {
  throw new Error(msg)
}

/** Requests notification permissions and returns the Expo push token. */
async function obtainPushToken(): Promise<string | undefined> {
  // Android requires an explicit notification channel
  if (Platform.OS === 'android') {
    Notifications.setNotificationChannelAsync('default', {
      name: 'default',
      importance: Notifications.AndroidImportance.MAX,
      vibrationPattern: [0, 250, 250, 250],
      lightColor: '#FF231F7C',
    })
  }

  const { status: existing } = await Notifications.getPermissionsAsync()
  let finalStatus = existing
  if (existing !== 'granted') {
    const { status } = await Notifications.requestPermissionsAsync()
    finalStatus = status
  }

  if (finalStatus !== 'granted') return undefined
  if (!Device.isDevice) return undefined

  const projectId =
    Constants?.expoConfig?.extra?.eas?.projectId ??
    Constants?.easConfig?.projectId
  if (!projectId) reportRegistrationError('Project ID not found')

  try {
    const result = await Notifications.getExpoPushTokenAsync({ projectId })
    return result.data
  } catch (e: unknown) {
    reportRegistrationError(`${e}`)
    return undefined
  }
}

interface NotificationsState {
  expoPushToken: string
  notification: Notifications.Notification | undefined
}

const NotificationsCtx = createContext<NotificationsState>({
  expoPushToken: '',
  notification: undefined,
})

export const useNotifications = () => useContext(NotificationsCtx)

export default function NotificationsProvider({
  children,
}: {
  children: React.ReactNode
}) {
  const [pushToken, setPushToken] = useState('')
  const [latestNotification, setLatestNotification] = useState<
    Notifications.Notification | undefined
  >(undefined)

  const receiveSub = useRef<Notifications.EventSubscription>(null)
  const responseSub = useRef<Notifications.EventSubscription>(null)
  const { session } = useSession()

  useEffect(() => {
    if (!session) return

    obtainPushToken().then((token) => setPushToken(token ?? ''))

    receiveSub.current = Notifications.addNotificationReceivedListener(
      (notification) => setLatestNotification(notification),
    )

    responseSub.current = Notifications.addNotificationResponseReceivedListener(
      (response) => {
        const data = response.notification.request.content.data
        if (data?.deepLink && typeof data.deepLink === 'string') {
          Linking.openURL(data.deepLink)
        }
      },
    )

    return () => {
      receiveSub.current?.remove()
      responseSub.current?.remove()
    }
  }, [session])

  return (
    <NotificationsCtx.Provider
      value={{ expoPushToken: pushToken, notification: latestNotification }}
    >
      {children}
    </NotificationsCtx.Provider>
  )
}
