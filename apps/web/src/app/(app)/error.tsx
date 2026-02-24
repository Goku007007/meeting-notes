"use client";

import { useEffect } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function AppError({
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
      <Card className="max-w-xl rounded-2xl border-red-200 bg-red-50/90 shadow-sm">
        <CardHeader>
          <CardTitle className="text-red-700">Something went wrong</CardTitle>
          <CardDescription>{error.message || "Unexpected error in app shell."}</CardDescription>
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
