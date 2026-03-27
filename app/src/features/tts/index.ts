import { lazy } from 'react'

export const manifest = {
  name: 'tts',
  routes: [
    {
      path: '/tts',
      component: lazy(() => import('./TTSPage')),
      permission: 'tts.read',
    },
    {
      path: '/tts/voices',
      component: lazy(() => import('./VoicesPage')),
      permission: 'tts.manage_voices',
    },
  ],
  navItems: [
    {
      label: 'Synthese vocale',
      labelKey: 'tts:nav_tts',
      path: '/tts',
      icon: 'mic',
      section: 'sidebar',
      permission: 'tts.read',
      order: 45,
      exact: true,
    },
  ],
}
