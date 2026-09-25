import {
  Ban,
  Building2,
  CircleAlert,
  Lightbulb,
  MessageSquare,
  SendHorizontal,
  Sparkles,
  SquareTerminal,
  UserRound,
  type LucideIcon,
} from "lucide-react";

export type NavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
};

export type NavGroup = {
  /** Visible group heading; omit for an unlabelled group. */
  label?: string;
  items: NavItem[];
};

/** Sidebar structure shared by the desktop sidebar and the mobile sheet. */
export const NAV_GROUPS: NavGroup[] = [
  {
    label: "Inbox",
    items: [
      { href: "/inbox/recommended", label: "Recommended", icon: Sparkles },
      { href: "/inbox/applied", label: "Applied", icon: SendHorizontal },
      { href: "/inbox/ignored", label: "Ignored", icon: Ban },
      {
        href: "/inbox/need-attention",
        label: "Need Attention",
        icon: CircleAlert,
      },
    ],
  },
  {
    items: [
      { href: "/companies", label: "Companies", icon: Building2 },
      { href: "/profile", label: "Profile / Preferences", icon: UserRound },
      { href: "/prompts", label: "Prompts", icon: SquareTerminal },
      { href: "/interview-tips", label: "Interview Tips", icon: Lightbulb },
      { href: "/feedback", label: "Feedback", icon: MessageSquare },
    ],
  },
];

export function isActivePath(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}
