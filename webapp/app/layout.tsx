import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: '2027 EE Jobs — Electrical Engineering Internships & Co-ops',
  description:
    'Curated list of Summer 2027 electrical engineering internships, off-cycle co-ops, and fall/spring EE roles. Hardware, RF, analog, power, VLSI, ASIC, FPGA, PCB, and test engineering positions in the US, Canada, and remote. Updated hourly.',
  keywords: [
    'electrical engineering internship 2027',
    'hardware engineering internship',
    'EE internship summer 2027',
    'RF engineering internship',
    'analog engineer intern',
    'VLSI internship',
    'ASIC internship',
    'FPGA internship',
    'PCB design internship',
    'power electronics internship',
    'semiconductor internship',
    'signal processing internship',
    'test engineer internship',
    'embedded hardware internship',
    'co-op electrical engineering',
  ],
  openGraph: {
    title: '2027 EE Jobs — Electrical Engineering Internships & Co-ops',
    description:
      'Curated EE internships and co-ops for 2027 — hardware, RF, analog, power, VLSI, ASIC, FPGA, PCB, and more. Updated hourly.',
    type: 'website',
  },
  twitter: {
    card: 'summary',
    title: '2027 EE Jobs',
    description: 'Electrical engineering internships and co-ops for 2027. Updated hourly.',
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
