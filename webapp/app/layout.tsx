import type { Metadata } from 'next';
import './globals.css';

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? 'https://shabajoba.vercel.app';

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: '2027 EE Jobs — Electrical Engineering Internships & Co-ops',
  description:
    'Curated list of Summer 2027 electrical engineering internships, off-cycle co-ops, and fall/spring EE roles. Hardware, RF, analog, power, VLSI, ASIC, FPGA, PCB, and test engineering positions in the US, Canada, and remote. Updated hourly.',
  keywords: [
    'electrical engineering internship 2027',
    'hardware engineering internship 2027',
    'EE internship summer 2027',
    'RF engineering internship',
    'analog engineer intern',
    'VLSI internship',
    'ASIC internship',
    'FPGA internship',
    'PCB design internship',
    'power electronics internship',
    'semiconductor internship 2027',
    'signal processing internship',
    'test engineer internship',
    'embedded hardware internship',
    'co-op electrical engineering',
    'hardware co-op 2027',
    'aerospace engineering internship',
    'defense engineering internship',
    'photonics internship',
    'mixed signal internship',
  ],
  alternates: {
    canonical: SITE_URL,
  },
  openGraph: {
    title: '2027 EE Jobs — Electrical Engineering Internships & Co-ops',
    description:
      'Curated EE internships and co-ops for 2027 — hardware, RF, analog, power, VLSI, ASIC, FPGA, PCB, and more. Updated hourly.',
    url: SITE_URL,
    siteName: '2027 EE Jobs',
    type: 'website',
    locale: 'en_US',
  },
  twitter: {
    card: 'summary',
    title: '2027 EE Jobs — Electrical Engineering Internships & Co-ops',
    description: 'Electrical engineering internships and co-ops for 2027. Updated hourly.',
  },
  robots: {
    index: true,
    follow: true,
    googleBot: { index: true, follow: true },
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
