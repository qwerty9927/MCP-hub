import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
    title: "MCP Hub — Multi-Server Management Dashboard",
    description: "Centralized administration dashboard for Model Context Protocol (MCP) servers and tools",
};

export default function RootLayout({
    children,
}: Readonly<{
    children: React.ReactNode;
}>) {
    return (
        <html lang="en" suppressHydrationWarning>
            {/* Browser extensions (e.g. Grammarly) add attributes to <body> before hydration */}
            <body className={inter.className} suppressHydrationWarning>
                <Providers>{children}</Providers>
            </body>
        </html>
    );
}
