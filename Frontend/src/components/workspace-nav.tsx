"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import {
  BookOpenText,
  FileStack,
  LogOut,
  Sparkles,
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

const NAV_ITEMS = [
  { href: "/dashboard", label: "Overview", key: "dashboard", Icon: BookOpenText },
  { href: "/documents", label: "Documents", key: "documents", Icon: FileStack },
] as const;

export function WorkspaceNav({
  active,
  user,
  onSignOut,
  onGenerate,
  children,
}: {
  active: "dashboard" | "documents" | "drafts";
  user: User;
  onSignOut: () => void;
  onGenerate?: () => void;
  children: ReactNode;
}) {
  const navItems = onGenerate
    ? [...NAV_ITEMS, { href: "/curriculum-drafts/new", label: "Draft studio", key: "drafts", Icon: Sparkles }]
    : NAV_ITEMS;

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
            <div className="workspace-crumb"><span>Workspace</span><i>/</i>{active === "dashboard" ? "Overview" : active === "documents" ? "Documents" : "Draft studio"}</div>
          </div>
          <div className="topbar-actions">
            <ThemeToggle />
            {onGenerate ? (
            <button className="topbar-generate" onClick={onGenerate} type="button" aria-label="Open curriculum draft studio">
              <Sparkles size={16} strokeWidth={1.9} />
              <span>Open draft studio</span>
            </button>
            ) : null}
          </div>
        </header>
        <div className="workspace-content">{children}</div>
      </SidebarInset>
    </SidebarProvider>
  );
}
