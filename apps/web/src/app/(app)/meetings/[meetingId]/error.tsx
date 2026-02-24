"use client";

import { useEffect } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function MeetingError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <main className="p-4 md:p-6">
      <Card className="max-w-xl border-red-200">
        <CardHeader>
          <CardTitle className="text-red-700">Meeting route failed</CardTitle>
          <CardDescription>{error.message || "Could not load this meeting view."}</CardDescription>
        </CardHeader>
        <CardContent>
          <Button type="button" onClick={reset}>
            Retry
          </Button>
        </CardContent>
      </Card>
    </main>
  );
}
