import { SuppliesClient } from "./SuppliesClient";

export const metadata = {
  title: "Supplies · CrewLoop",
};

export default async function SuppliesPage({
  params,
}: {
  params: Promise<{ eventId: string }>;
}) {
  const { eventId } = await params;
  return <SuppliesClient eventId={eventId} />;
}
