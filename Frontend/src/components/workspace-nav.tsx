"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import {
  BookOpenText,
  FileStack,
  Layers3,
  LogOut,
  SearchCheck,
  Sparkles,
  Users,
} from "lucide-react";

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import type { User } from "@/lib/api";
import { ThemeToggle } from "@/components/theme-toggle";

export type WorkspaceSection =
  | "dashboard"
  | "documents"
  | "drafts"
  | "verification"
  | "curricula"
  | "users";

type NavItem = {
  href: string;
  label: string;
  key: WorkspaceSection;
  Icon: typeof BookOpenText;
};

const NAV_ITEMS: NavItem[] = [
  { href: "/dashboard", label: "Overview", key: "dashboard", Icon: BookOpenText },
  { href: "/documents", label: "Documents", key: "documents", Icon: FileStack },
  { href: "/curricula", label: "Curricula", key: "curricula", Icon: Layers3 },
  { href: "/verification", label: "Verification", key: "verification", Icon: SearchCheck },
];

const USERS_NAV_ITEM: NavItem = {
  href: "/users",
  label: "Users",
  key: "users",
  Icon: Users,
};

const DRAFTS_NAV_ITEM: NavItem = {
  href: "/curriculum-drafts/new",
  label: "Draft studio",
  key: "drafts",
  Icon: Sparkles,
};

const SECTION_LABELS: Record<WorkspaceSection, string> = {
  dashboard: "Overview",
  documents: "Documents",
  drafts: "Draft studio",
  verification: "Verification",
  curricula: "Curricula",
  users: "Users",
};

export function WorkspaceNav({
  active,
  user,
  onSignOut,
  onGenerate,
  children,
}: {
  active: WorkspaceSection;
  user: User;
  onSignOut: () => void;
  onGenerate?: () => void;
  children: ReactNode;
}) {
  const navItems = [...NAV_ITEMS];
  if (user.roles.includes("ADMIN")) {
    navItems.push(USERS_NAV_ITEM);
  }
  if (onGenerate) {
    navItems.push(DRAFTS_NAV_ITEM);
  }

  return (
    <SidebarProvider className="workspace-provider">
      <Sidebar collapsible="icon" className="app-sidebar">
        <SidebarHeader role="region" aria-label="Workspace home" className="workspace-sidebar-header group-data-[collapsible=icon]:items-center group-data-[collapsible=icon]:px-2">
          <Link className="workspace-brand" href="/dashboard" aria-label="Curriculum Intelligence home">
            <span className="workspace-brand-mark">C</span>
            <span className="workspace-brand-copy group-data-[collapsible=icon]:hidden">Curriculum <b>Intelligence</b></span>
          </Link>
        </SidebarHeader>
        <SidebarContent>
          <nav aria-label="Workspace navigation">
          <SidebarGroup>
            <SidebarGroupLabel>Workspace</SidebarGroupLabel>
            <SidebarMenu>
              {navItems.map(({ href, label, key, Icon }) => (
                <SidebarMenuItem key={key}>
                  <SidebarMenuButton
                    render={<Link href={href} />}
                    isActive={active === key}
                    tooltip={label}
                  >
                    <Icon aria-hidden="true" />
                    <span className="group-data-[collapsible=icon]:hidden">{label}</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroup>
          </nav>
        </SidebarContent>
        <SidebarFooter role="region" aria-label="Account" className="workspace-sidebar-footer group-data-[collapsible=icon]:p-2">
          <div className="sidebar-user group-data-[collapsible=icon]:hidden" title={user.email}>
            <span className="account-avatar" aria-hidden="true">
              {user.full_name.trim().charAt(0).toUpperCase()}
            </span>
            <span className="sidebar-user-copy">
              <b>{user.full_name}</b>
              <small>{user.roles[0]?.replaceAll("_", " ").toLowerCase() ?? "Member"}</small>
            </span>
          </div>
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton onClick={onSignOut} tooltip="Sign out">
                <LogOut aria-hidden="true" />
                <span className="group-data-[collapsible=icon]:hidden">Sign out</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarFooter>
      </Sidebar>
      <SidebarInset className="workspace-inset">
        <header className="workspace-topbar">
          <div className="topbar-context">
            <SidebarTrigger className="topbar-sidebar-trigger" />
            <div className="workspace-crumb"><span>Workspace</span><i>/</i>{SECTION_LABELS[active]}</div>
          </div>
          <div className="topbar-actions">
            <ThemeToggle />
            {onGenerate ? (
            <button className="topbar-generate" onClick={onGenerate} type="button" aria-label="Open curriculum draft studio">
              <Sparkles size={16} strokeWidth={1.9} />
              <span className="text-primary-foreground/80">Open draft studio</span>
            </button>
            ) : null}
          </div>
        </header>
        <div className="workspace-content">{children}</div>
      </SidebarInset>
    </SidebarProvider>
  );
}
