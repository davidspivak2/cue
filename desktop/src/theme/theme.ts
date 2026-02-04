import { createTheme } from "@mui/material/styles";

export const theme = createTheme({
  palette: {
    mode: "dark",
    primary: {
      main: "#7A5CFF"
    },
    background: {
      default: "#0F1115",
      paper: "#151922"
    },
    text: {
      primary: "#E6EAF2",
      secondary: "#B7BFCC"
    },
    divider: "#2A2F3A",
    success: {
      main: "#3DDC84"
    },
    error: {
      main: "#FF5D5D"
    }
  },
  typography: {
    fontFamily: "'Inter', 'Segoe UI', sans-serif",
    h5: {
      fontWeight: 600
    }
  },
  shape: {
    borderRadius: 10
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          backgroundColor: "#0F1115"
        }
      }
    },
    MuiButton: {
      defaultProps: {
        size: "medium"
      }
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 10,
          border: "1px solid #2A2F3A",
          boxShadow: "none",
          backgroundImage: "none"
        }
      }
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: "none"
        }
      }
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundColor: "#151922",
          borderBottom: "1px solid #2A2F3A"
        }
      }
    }
  }
});
