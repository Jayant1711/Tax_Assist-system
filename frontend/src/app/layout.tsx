import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "TaxAssist AI | Deep Tax Intelligence",
  description: "High-performance AI tax filing and optimization assistant for India FY 2024-25.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      </head>
      <body>{children}</body>
    </html>
  );
}
