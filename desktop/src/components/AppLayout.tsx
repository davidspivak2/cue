import {
  AppBar,
  Box,
  Drawer,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Toolbar,
  Typography
} from "@mui/material";
import HomeIcon from "@mui/icons-material/Home";
import SettingsIcon from "@mui/icons-material/Settings";
import { NavLink, Outlet } from "react-router-dom";

const drawerWidth = 240;

const navItems = [
  { label: "Home", to: "/", icon: <HomeIcon /> },
  { label: "Settings", to: "/settings", icon: <SettingsIcon /> }
];

const AppLayout = () => (
  <Box sx={{ display: "flex", minHeight: "100vh" }}>
    <AppBar
      position="fixed"
      sx={{ zIndex: (theme) => theme.zIndex.drawer + 1 }}
    >
      <Toolbar>
        <Typography variant="h6" component="div">
          Cue
        </Typography>
      </Toolbar>
    </AppBar>
    <Drawer
      variant="permanent"
      sx={{
        width: drawerWidth,
        flexShrink: 0,
        [`& .MuiDrawer-paper`]: {
          width: drawerWidth,
          boxSizing: "border-box"
        }
      }}
    >
      <Toolbar />
      <List>
        {navItems.map((item) => (
          <ListItemButton
            key={item.label}
            component={NavLink}
            to={item.to}
            sx={{
              mx: 1,
              mb: 0.5,
              borderRadius: 1,
              "&.active": {
                backgroundColor: "action.selected",
                "& .MuiListItemIcon-root": {
                  color: "primary.main"
                }
              }
            }}
          >
            <ListItemIcon>{item.icon}</ListItemIcon>
            <ListItemText primary={item.label} />
          </ListItemButton>
        ))}
      </List>
    </Drawer>
    <Box
      component="main"
      sx={{
        flexGrow: 1,
        px: 4,
        py: 3,
        mt: 8,
        backgroundColor: "background.default"
      }}
    >
      <Outlet />
    </Box>
  </Box>
);

export default AppLayout;
