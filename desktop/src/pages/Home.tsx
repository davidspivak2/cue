import { Box, Button, Card, CardContent, Stack, Typography } from "@mui/material";

const Home = () => (
  <Stack spacing={3}>
    <Card elevation={3}>
      <CardContent>
        <Stack spacing={2}>
          <Box>
            <Typography variant="h5" gutterBottom>
              Ready
            </Typography>
            <Typography color="text.secondary">
              The desktop shell is running. Backend wiring lands in a future PR.
            </Typography>
          </Box>
          <Button variant="contained" disabled>
            Start
          </Button>
        </Stack>
      </CardContent>
    </Card>
    <Card variant="outlined">
      <CardContent>
        <Typography variant="subtitle1" gutterBottom>
          Backend not connected (stub)
        </Typography>
        <Typography variant="body2" color="text.secondary">
          This is the phase 1 UI shell. No Python integration is enabled yet.
        </Typography>
      </CardContent>
    </Card>
  </Stack>
);

export default Home;
