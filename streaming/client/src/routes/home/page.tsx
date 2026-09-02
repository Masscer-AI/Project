import React from "react";
import { Loader, Stack } from "@mantine/core";

export default function HomeRedirectPage() {
  return (
    <Stack align="center" justify="center" style={{ height: "100vh" }}>
      <Loader color="violet" />
    </Stack>
  );
}
