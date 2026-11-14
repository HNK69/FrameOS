import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "FRAMEOPS — Client Intelligence",
  description: "Remember Every Client. Perfect Every Project.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
