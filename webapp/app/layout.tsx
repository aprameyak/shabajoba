import type { Metadata } from 'next';
import './globals.css';

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? 'https://shabajoba.vercel.app';

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: '2027 EE Internships & Co-ops — US & Canada | Shabajoba',
  description:
    'Free hourly-updated list of electrical engineering internships and co-ops in the United States and Canada. Hardware, RF, analog, power, VLSI, ASIC, FPGA, PCB, and test roles for Summer 2027 and off-cycle terms.',
  keywords: [
    'electrical engineering internship 2027',
    'EE internship US Canada',
    'hardware engineering internship 2027',
    'electrical engineering co-op',
    'FPGA internship',
    'ASIC internship',
    'VLSI internship',
    'analog design intern',
    'RF engineering internship',
    'power systems internship',
    'PCB design internship',
    'semiconductor internship 2027',
    'test engineer internship',
    'Summer 2027 EE intern',
  ],
  alternates: {
    canonical: SITE_URL,
  },
  openGraph: {
    title: '2027 EE Internships & Co-ops — US & Canada',
    description:
      'Hourly-updated electrical engineering internships and co-ops. Hardware, RF, analog, power, VLSI/ASIC, FPGA, PCB, and more.',
    url: SITE_URL,
    siteName: 'Shabajoba — 2027 EE Jobs',
    type: 'website',
    locale: 'en_US',
  },
  twitter: {
    card: 'summary_large_image',
    title: '2027 EE Internships & Co-ops — US & Canada',
    description: 'Free hourly-updated EE internship list for the US and Canada.',
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
