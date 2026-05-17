import { DispatchClient } from "./DispatchClient";

export const metadata = {
  title: "Dispatch Room · CrewLoop",
};

export default async function DispatchPage({
  params,
}: {
  params: Promise<{ jobId: string }>;
}) {
  const { jobId } = await params;
  return <DispatchClient jobId={jobId} />;
}
