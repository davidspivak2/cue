import {
  Box,
  FormControl,
  FormControlLabel,
  InputLabel,
  MenuItem,
  Select,
  Slider,
  Stack,
  Switch,
  Typography
} from "@mui/material";
import { useState } from "react";

const Settings = () => {
  const [gpuEnabled, setGpuEnabled] = useState(false);
  const [fontSize, setFontSize] = useState(16);
  const [density, setDensity] = useState("comfortable");

  return (
    <Stack spacing={4} maxWidth={520}>
      <Box>
        <Typography variant="h5" gutterBottom>
          Settings
        </Typography>
        <Typography color="text.secondary">
          Placeholder controls to preview the UI theme.
        </Typography>
      </Box>
      <FormControlLabel
        control={
          <Switch
            checked={gpuEnabled}
            onChange={(event) => setGpuEnabled(event.target.checked)}
          />
        }
        label="Enable GPU (placeholder)"
      />
      <Box>
        <Typography gutterBottom>Subtitle font size (placeholder)</Typography>
        <Slider
          value={fontSize}
          min={12}
          max={28}
          step={1}
          valueLabelDisplay="auto"
          onChange={(_, value) => setFontSize(value as number)}
        />
      </Box>
      <FormControl fullWidth>
        <InputLabel id="theme-density-label">Theme density (placeholder)</InputLabel>
        <Select
          labelId="theme-density-label"
          value={density}
          label="Theme density (placeholder)"
          onChange={(event) => setDensity(event.target.value)}
        >
          <MenuItem value="comfortable">Comfortable</MenuItem>
          <MenuItem value="compact">Compact</MenuItem>
          <MenuItem value="spacious">Spacious</MenuItem>
        </Select>
      </FormControl>
    </Stack>
  );
};

export default Settings;
