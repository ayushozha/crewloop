import { PasswordGate } from "@/components/PasswordGate";

import { BoardClient } from "./BoardClient";

export const metadata = {
  title: "Fill board · CrewLoop",
};

export default async function ShiftBoardPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <PasswordGate>
      <BoardClient shiftId={id} />
    </PasswordGate>
  );
}
