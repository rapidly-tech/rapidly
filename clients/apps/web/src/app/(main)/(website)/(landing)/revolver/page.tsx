import type { Metadata } from 'next'

import { RevolverLanding } from '@/components/Revolver/RevolverLanding'

export const metadata: Metadata = {
  title: 'Rapidly — 6 chambers, one platform',
  description:
    'Files, Secret, Screen, Watch, Call, Collab. Rapidly is a 6-chamber platform for encrypted peer-to-peer collaboration.',
}

export default function RevolverPage() {
  return <RevolverLanding />
}
