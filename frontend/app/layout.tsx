import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { ThemeProvider } from "@/components/theme-provider";
import { ThemeToggle } from "@/components/theme-toggle";
import { CommandPalette } from "@/components/command-palette";
import { IntroAnimation } from "@/components/intro-animation";
import { Starfield } from "@/components/starfield";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import Link from "next/link";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Adobe Artemis",
  description: "Turn any BRD into a traceable AEP implementation plan.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <body className="min-h-full flex flex-col">
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
          <TooltipProvider>
            <Starfield />
            <IntroAnimation />
            <header className="relative z-10 flex items-center justify-between border-b px-6 py-3">
              <Link href="/" className="flex items-center gap-1.5 text-sm font-semibold tracking-tight">
                <span className="inline-block h-2 w-2 rounded-[2px] bg-adobe-red" aria-hidden />
                Adobe Artemis
              </Link>
              <ThemeToggle />
            </header>
            <main className="relative z-10 flex flex-1 flex-col">{children}</main>
            <CommandPalette />
            <Toaster />
          </TooltipProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
