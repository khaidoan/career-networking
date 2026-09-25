"use client";

import { useEffect, useEffectEvent, useState } from "react";
import { LogOut, UserRound } from "lucide-react";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useLogout } from "@/hooks/use-logout";
import { fetchCurrentUser, type CurrentUser } from "@/lib/auth/client";

/** Avatar with the signed-in user's initials and a menu holding Logout. */
export function UserMenu() {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const logout = useLogout();
  // The API rejected the session (e.g. credentials changed): end it cleanly.
  const onSessionRejected = useEffectEvent(() => void logout());

  useEffect(() => {
    const controller = new AbortController();
    fetchCurrentUser(controller.signal)
      .then((currentUser) => {
        if (currentUser) {
          setUser(currentUser);
        } else {
          onSessionRejected();
        }
      })
      .catch(() => {
        // Loading or network failure: keep the neutral fallback avatar.
      });
    return () => controller.abort();
  }, []);

  const fullName = user
    ? `${user.first_name} ${user.last_name}`.trim() || user.username
    : null;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="rounded-full"
          aria-label={
            fullName ? `Account menu for ${fullName}` : "Account menu"
          }
        >
          <Avatar>
            <AvatarFallback
              className={
                user ? undefined : "bg-surface-alt text-muted-foreground"
              }
            >
              {user ? (
                user.initials
              ) : (
                <UserRound aria-hidden="true" className="size-4" />
              )}
            </AvatarFallback>
          </Avatar>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent>
        {user && (
          <>
            <DropdownMenuLabel className="flex flex-col gap-1">
              <span className="font-semibold">{fullName}</span>
              {user.email && (
                <span className="text-xs font-normal text-muted-foreground">
                  {user.email}
                </span>
              )}
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
          </>
        )}
        <DropdownMenuItem onSelect={() => void logout()}>
          <LogOut aria-hidden="true" />
          Logout
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
