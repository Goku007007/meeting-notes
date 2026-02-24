import { Skeleton } from "@/components/ui/skeleton";

export default function AppLoading() {
  return (
    <main className="space-y-4 p-4 md:p-6">
      <Skeleton className="h-10 w-64" />
      <Skeleton className="h-96 w-full" />
    </main>
  );
}
