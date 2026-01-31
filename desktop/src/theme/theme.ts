import { createTheme } from "@mui/material/styles";

export const theme = createTheme({
  palette: {
    mode: "light",
    primary: {
      main: "#4a5fff"
    },
    secondary: {
      main: "#7b3fe4"
    },
    background: {
      default: "#f6f7fb",
      paper: "#ffffff"
    }
  },
  typography: {
    fontFamily: "'Inter', 'Segoe UI', sans-serif",
    h5: {
      fontWeight: 600
    }
  },
  shape: {
    borderRadius: 12
  },
  components: {
    MuiButton: {
      defaultProps: {
        size: "medium"
      }
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 16
        }
      }
    }
  }
});
