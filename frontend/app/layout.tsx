import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Arooohi — Safe Student Rides",
  description: "An exclusive student-to-student ride-sharing network for BRACU. Safe rides, smart matches, student-powered.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
