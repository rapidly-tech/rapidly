/**
 * Vertical list of navigable link rows inside a card container.
 *
 * Each row shows a title, optional metadata text, and a chevron icon.
 * Rows are separated by a hairline border except for the last item.
 */
import { Box } from '@/components/Shared/Box'
import { Text } from '@/components/Shared/Text'
import { useTheme } from '@/design-system/useTheme'
import { Href, Link } from 'expo-router'
import { Iconify } from 'react-native-iconify'

interface LinkItem {
  title: string
  meta?: string
  link: Href
}

interface LinkListProps {
  items: LinkItem[]
}

export const LinkList = ({ items }: LinkListProps) => {
  const theme = useTheme()
  const lastIndex = items.length - 1

  return (
    <Box flexDirection="column" gap="spacing-12">
      <Box
        flexDirection="column"
        backgroundColor="card"
        borderRadius="border-radius-12"
        overflow="hidden"
      >
        {items.map((item, idx) => (
          <Link href={item.link} key={item.title}>
            <Box
              key={item.title}
              flexDirection="row"
              justifyContent="space-between"
              alignItems="center"
              padding="spacing-12"
              borderBottomWidth={idx < lastIndex ? 1 : 0}
              borderColor="border"
            >
              <Box
                flex={1}
                flexDirection="row"
                alignItems="center"
                justifyContent="space-between"
                gap="spacing-4"
              >
                <Text variant="body">{item.title}</Text>
                <Box flexDirection="row" alignItems="center" gap="spacing-8">
                  <Text variant="body" color="subtext">
                    {item.meta}
                  </Text>
                  <Iconify
                    icon="solar:alt-arrow-right-linear"
                    size={20}
                    color={theme.colors.subtext}
                  />
                </Box>
              </Box>
            </Box>
          </Link>
        ))}
      </Box>
    </Box>
  )
}
