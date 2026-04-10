import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Human Life Scenario Simulator',
  description: 'A Multi-Agent Simulation framework that stress-tests real-life decisions before they happen.',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="scanlines">{children}</body>
    </html>
  )
}
