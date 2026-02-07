import { Home, Settings } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";

import { cn } from "@/lib/utils";

const navItems = [
  { label: "Home", to: "/", icon: Home },
  { label: "Settings", to: "/settings", icon: Settings }
];

const AppLayout = () => (
  <div className="min-h-screen bg-background text-foreground">
    <div className="flex min-h-screen">
      <aside className="w-60 border-r border-border bg-card">
        <div className="flex h-16 items-center px-4 text-lg font-semibold">Cue</div>
        <nav className="space-y-1 px-2 pb-4">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.label}
                to={item.to}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors",
                    isActive
                      ? "bg-secondary text-foreground"
                      : "text-muted-foreground hover:bg-secondary/70 hover:text-foreground"
                  )
                }
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </NavLink>
            );
          })}
        </nav>
      </aside>
      <main className="flex-1 px-6 py-6">
        <Outlet />
      </main>
    </div>
  </div>
);

export default AppLayout;
