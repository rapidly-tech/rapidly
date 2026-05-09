/**
 * Themed bottom sheet wrapper built on @gorhom/bottom-sheet.
 *
 * Applies Rapidly theme colors for the background and handle indicator,
 * renders a dimming backdrop, and injects bottom safe-area padding so
 * content never sits under the home indicator.
 */
import { useTheme } from '@/design-system/useTheme'
import GorhomBottomSheet, {
  BottomSheetBackdrop as GorhomBackdrop,
  BottomSheetProps as GorhomSheetProps,
  BottomSheetView as GorhomView,
} from '@gorhom/bottom-sheet'
import React, { useRef } from 'react'
import { StyleSheet } from 'react-native'
import { useSafeAreaInsets } from 'react-native-safe-area-context'

export interface BottomSheetProps
  extends React.PropsWithChildren, Omit<GorhomSheetProps, 'children'> {
  onDismiss?: () => void
}

export const BottomSheet = ({
  children,
  onDismiss,
  ...rest
}: BottomSheetProps) => {
  const sheetRef = useRef<GorhomBottomSheet>(null)
  const theme = useTheme()
  const insets = useSafeAreaInsets()

  return (
    <GorhomBottomSheet
      ref={sheetRef}
      onClose={onDismiss}
      enablePanDownToClose
      backgroundStyle={{
        backgroundColor: theme.colors.background,
        borderRadius: theme.borderRadii['border-radius-32'],
      }}
      handleIndicatorStyle={{ backgroundColor: theme.colors.subtext }}
      {...rest}
      backdropComponent={(backdropProps) => (
        <GorhomBackdrop
          {...backdropProps}
          enableTouchThrough={false}
          appearsOnIndex={0}
          disappearsOnIndex={-1}
          style={[
            { flex: 1, backgroundColor: theme.colors.overlay },
            StyleSheet.absoluteFillObject,
          ]}
        />
      )}
    >
      <GorhomView
        style={{
          flex: 1,
          padding: theme.spacing['spacing-24'],
          gap: theme.spacing['spacing-12'],
          paddingBottom: insets.bottom + 12,
        }}
      >
        {children}
      </GorhomView>
    </GorhomBottomSheet>
  )
}
