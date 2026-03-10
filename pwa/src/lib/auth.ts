import type { NextAuthOptions } from "next-auth";
import GitHubProvider from "next-auth/providers/github";

const ALLOWED_EMAIL = process.env.ALLOWED_EMAIL!; // ton email GitHub

export const authOptions: NextAuthOptions = {
  providers: [
    GitHubProvider({
      clientId: process.env.GITHUB_ID!,
      clientSecret: process.env.GITHUB_SECRET!,
    }),
  ],
  callbacks: {
    async signIn({ user }) {
      return user.email === ALLOWED_EMAIL;
    },
    async session({ session }) {
      return session;
    },
  },
  pages: {
    signIn: "/login",
    error: "/login",
  },
};
