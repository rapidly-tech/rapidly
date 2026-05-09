'use client'

import { Icon } from '@iconify/react'
import Button from '@rapidly-tech/ui/components/forms/Button'
import ItemGroup from '@rapidly-tech/ui/components/navigation/ItemGroup'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@rapidly-tech/ui/components/primitives/dropdown-menu'
import { useTheme } from 'next-themes'
import Spinner from '../Shared/Spinner'

export type Theme = 'system' | 'light' | 'dark'

/**
 * Workspace-level general settings.
 * Currently exposes a theme switcher (system / light / dark).
 */
const GeneralSettings = () => {
  const { theme, setTheme } = useTheme()

  return (
    <ItemGroup>
      <ItemGroup.Item>
        <div className="flex flex-row items-start justify-between">
          <div className="flex flex-col gap-y-1">
            <h3>Theme</h3>
            <p className="text-sm text-slate-400">
              Override your browser&apos;s preferred color scheme
            </p>
          </div>
          {theme === undefined ? (
            <Spinner />
          ) : (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button className="justify-between" variant="secondary">
                  <span className="capitalize">{theme}</span>
                  <Icon
                    icon="solar:alt-arrow-down-linear"
                    className="ml-2 h-4 w-4"
                  />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                className="bg-slate-50 shadow-lg dark:bg-slate-800"
                align="end"
              >
                <DropdownMenuItem onClick={() => setTheme('system')}>
                  System
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => setTheme('light')}>
                  Light
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => setTheme('dark')}>
                  Dark
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </div>
      </ItemGroup.Item>
    </ItemGroup>
  )
}

export default GeneralSettings
