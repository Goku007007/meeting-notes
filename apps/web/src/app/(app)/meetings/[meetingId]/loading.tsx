import { Skeleton } from "@/components/ui/skeleton";

export default function MeetingLoading() {
  return (
    <main className="space-y-4 p-4 md:p-6">
      <Skeleton className="h-10 w-72" />
      <Skeleton className="h-[620px] w-full" />
    </main>
  );
}
